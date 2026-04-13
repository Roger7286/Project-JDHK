"""
main.py
=======
职责：调拨申请单同步流程总入口，串联 API 拉取 → 数据库写入两个步骤。

执行方式：
    # 默认同步（start_biztime=今天-30天，end_biztime=今天）
    python main.py

    # 按业务日期同步
    python main.py --start_biztime "2024-06-01" --end_biztime "2024-06-30"

    # 按审核时间增量同步
    python main.py --start_auditdate "2024-06-01 00:00:00" --end_auditdate "2024-06-30 23:59:59"

    # 只同步某单据状态（A=暂存 B=已提交 C=已审核，多个用逗号分隔）
    python main.py --billstatus A,B,C

    # 指定申请组织
    python main.py --org_number "BU-001,BU-002"

    # 指定单据编号
    python main.py --billno "DBSQ-260405-000001"

    # 跳过删除同步（只做新增/更新，不检测已删除记录）
    python main.py --skip_delete_sync

参数优先级：命令行参数 > SYNC_PARAMS 默认值
默认 biztime 范围：今天往前 30 天 ~ 今天（每次运行时动态计算）

删除同步说明：
    - 仅在无选择性过滤参数（billno/billstatus/org_number 均为空）时自动触发
    - 比对逻辑：API 返回的 ID 集合 vs PG 中相同 biztime 范围内的非删除记录 ID 集合
    - 差集（PG有但API无）即为已在金蝶删除的记录，执行软删除（is_deleted=TRUE）
    - 明细表不需单独软删除，通过 JOIN 主表过滤 is_deleted=FALSE 即可
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import datetime
import psycopg2

from config                     import PG_CONFIG
from fetch_transapply           import fetch_all_pages
from load_transapply_to_pg      import upsert_rows

# =========================================================
# 常量
# =========================================================

API_NAME    = "/v2/im/im_transapply/getList"
TABLE_BILL  = "jdhk.kingdee_transapply"
TABLE_ENTRY = "jdhk.kingdee_transapply_entry"

# =========================================================
# 默认同步参数（biztime 动态计算）
# =========================================================

def _default_biztime():
    today = datetime.date.today()
    start = today - datetime.timedelta(days=30)
    return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")


_BIZ_START_DEFAULT, _BIZ_END_DEFAULT = _default_biztime()

SYNC_PARAMS = {
    "start_auditdate":  None,
    "end_auditdate":    None,
    "start_biztime":    _BIZ_START_DEFAULT,
    "end_biztime":      _BIZ_END_DEFAULT,
    "billno":           None,
    "billstatus":       None,
    "org_number":       None,
    "pageSize":         100,
    "max_pages":        None,
    "sleep_sec":        0.3,
}

WRITE_BATCH_SIZE = 200


# =========================================================
# sync_state 状态表操作
# =========================================================

def upsert_sync_state(conn, api_name, table_name, last_sync_time, sync_rows):
    sql = """
        INSERT INTO jdhk.sync_state
            (api_name, table_name, last_sync_time, sync_rows, created_at, updated_at)
        VALUES
            (%(api_name)s, %(table_name)s, %(last_sync_time)s, %(sync_rows)s, NOW(), NOW())
        ON CONFLICT (api_name, table_name) DO UPDATE
        SET last_sync_time = EXCLUDED.last_sync_time,
            sync_rows      = EXCLUDED.sync_rows,
            updated_at     = NOW()
    """
    with conn.cursor() as cur:
        cur.execute(sql, {
            "api_name":       api_name,
            "table_name":     table_name,
            "last_sync_time": last_sync_time,
            "sync_rows":      sync_rows,
        })
    conn.commit()
    print(f"[sync_state] 已更新: api={api_name}, rows={sync_rows}")


# =========================================================
# 删除同步：比对 API 与 PG，软删除已消失的记录
# =========================================================

def sync_deletes(conn, api_ids: set, start_biztime: str, end_biztime: str) -> int:
    """
    将 PG 中 biztime 在 [start_biztime, end_biztime] 范围内、
    但不在本次 API 返回 ID 集合里的记录标记为软删除（主表 + 明细联动）。

    前提：调用方已确认本次查询未使用选择性过滤（billno/billstatus/org_number），
          否则 API 返回的是子集，不能用来判断删除。

    返回：本次软删除的主表记录条数。
    """
    # 1. 查出 PG 中该范围内所有「未删除」主表记录的 id
    sql_select = """
        SELECT id
        FROM jdhk.kingdee_transapply
        WHERE biztime BETWEEN %(start)s AND %(end)s
          AND is_deleted = FALSE
    """
    with conn.cursor() as cur:
        cur.execute(sql_select, {"start": start_biztime, "end": end_biztime})
        pg_ids = {str(row[0]) for row in cur.fetchall()}

    if not pg_ids:
        print("[删除同步] PG 中该范围内无记录，跳过。")
        return 0

    # 2. 差集 = 在 PG 有、但 API 没有返回的记录 → 已在金蝶被删除
    deleted_ids = pg_ids - api_ids

    print(f"[删除同步] 范围 {start_biztime} ~ {end_biztime}："
          f"PG {len(pg_ids)} 条，API {len(api_ids)} 条，"
          f"待软删除 {len(deleted_ids)} 条。")

    if not deleted_ids:
        return 0

    deleted_list = list(deleted_ids)

    # 打印部分被删除的单据 id，方便排查
    sample = sorted(deleted_ids)[:10]
    print(f"[删除同步] 待软删除单据 id 示例: {sample}"
          f"{'（...）' if len(deleted_ids) > 10 else ''}")

    # 3. 软删除主表
    sql_del_bill = """
        UPDATE jdhk.kingdee_transapply
        SET is_deleted = TRUE,
            deleted_at = NOW()
        WHERE id = ANY(%(ids)s)
          AND is_deleted = FALSE
    """
    with conn.cursor() as cur:
        cur.execute(sql_del_bill, {"ids": deleted_list})
        bill_affected = cur.rowcount
    print(f"[删除同步] 主表软删除 {bill_affected} 条。")

    # 4. 联动软删除明细表（bill_id 关联）
    sql_del_entry = """
        UPDATE jdhk.kingdee_transapply_entry
        SET is_deleted = TRUE,
            deleted_at = NOW()
        WHERE bill_id = ANY(%(ids)s)
          AND is_deleted = FALSE
    """
    with conn.cursor() as cur:
        cur.execute(sql_del_entry, {"ids": deleted_list})
        entry_affected = cur.rowcount
    print(f"[删除同步] 明细表软删除 {entry_affected} 条。")

    conn.commit()
    return bill_affected


# =========================================================
# 命令行参数解析
# =========================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="金蝶调拨申请单 → PostgreSQL 增量/全量同步",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--start_auditdate", type=str, default=None, metavar="DATETIME",
                        help="审核起始时间，格式：'2024-06-01 00:00:00'")
    parser.add_argument("--end_auditdate",   type=str, default=None, metavar="DATETIME",
                        help="审核截止时间，格式：'2024-06-30 23:59:59'")
    parser.add_argument("--start_biztime",   type=str, default=None, metavar="DATE",
                        help="业务起始日期，格式：'2024-06-01'")
    parser.add_argument("--end_biztime",     type=str, default=None, metavar="DATE",
                        help="业务截止日期，格式：'2024-06-30'")
    parser.add_argument("--billstatus",      type=str, default=None, metavar="STATUS",
                        help="单据状态：A/B/C（多个用逗号分隔）")
    parser.add_argument("--org_number",      type=str, default=None, metavar="ORG",
                        help="申请组织编码（多个用逗号分隔）")
    parser.add_argument("--billno",          type=str, default=None, metavar="BILLNO",
                        help="单据编号（多个用逗号分隔）")
    parser.add_argument("--skip_delete_sync", action="store_true", default=False,
                        help="跳过删除同步（不检测 PG 中已被金蝶删除的记录）")
    return parser.parse_args()


# =========================================================
# 主流程
# =========================================================

def main():
    print("=" * 60)
    print("金蝶调拨申请单 → PostgreSQL 同步")
    print("=" * 60)

    args = parse_args()

    def _pick(cli_val, default_key):
        return cli_val if cli_val is not None else SYNC_PARAMS.get(default_key)

    def _to_list(val):
        if val is None:
            return None
        return [x.strip() for x in val.split(",")]

    start_auditdate = _pick(args.start_auditdate, "start_auditdate")
    end_auditdate   = _pick(args.end_auditdate,   "end_auditdate")
    start_biztime   = _pick(args.start_biztime,   "start_biztime")
    end_biztime     = _pick(args.end_biztime,     "end_biztime")
    billstatus      = _to_list(_pick(args.billstatus,  "billstatus"))
    org_number      = _to_list(_pick(args.org_number,  "org_number"))
    billno          = _to_list(_pick(args.billno,      "billno"))
    skip_delete_sync = args.skip_delete_sync

    print(f"\n同步参数：")
    print(f"  start_biztime   : {start_biztime   or '（不过滤）'}")
    print(f"  end_biztime     : {end_biztime     or '（不过滤）'}")
    print(f"  start_auditdate : {start_auditdate or '（不过滤）'}")
    print(f"  end_auditdate   : {end_auditdate   or '（不过滤）'}")
    print(f"  billstatus      : {billstatus      or '（不过滤）'}")
    print(f"  org_number      : {org_number      or '（不过滤）'}")
    print(f"  billno          : {billno          or '（不过滤）'}")
    print(f"  pageSize        : {SYNC_PARAMS.get('pageSize')}")
    print(f"  skip_delete_sync: {skip_delete_sync}")

    # Step 1: 拉取数据
    print("\n【Step 1】从 API 拉取数据...")
    all_rows = fetch_all_pages(
        start_biztime=start_biztime,
        end_biztime=end_biztime,
        start_auditdate=start_auditdate,
        end_auditdate=end_auditdate,
        billno=billno,
        billstatus=billstatus,
        org_number=org_number,
        pageSize=SYNC_PARAMS.get("pageSize"),
        max_pages=SYNC_PARAMS.get("max_pages"),
        sleep_sec=SYNC_PARAMS.get("sleep_sec"),
    )
    print(f"【Step 1 完成】共拉取 {len(all_rows)} 张单据。")

    # Step 2: 连接 PG
    print("\n【Step 2】连接 PostgreSQL...")
    conn = psycopg2.connect(
        host=PG_CONFIG["host"], port=PG_CONFIG["port"],
        dbname=PG_CONFIG["database"], user=PG_CONFIG["user"],
        password=PG_CONFIG["password"],
    )
    print(f"[PG] 已连接: {PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['database']}")

    total_bills   = 0
    total_entries = 0

    try:
        # Step 3: 分批写入
        if all_rows:
            print(f"\n【Step 3】写入 PostgreSQL（每批 {WRITE_BATCH_SIZE} 张单据）...")
            for i in range(0, len(all_rows), WRITE_BATCH_SIZE):
                batch = all_rows[i : i + WRITE_BATCH_SIZE]
                upserted_b, upserted_e = upsert_rows(conn, batch)
                total_bills   += upserted_b
                total_entries += upserted_e
                print(f"[PG] 累计 主表={total_bills}/{len(all_rows)}，明细={total_entries}")
        else:
            print("\n【Step 3】无数据需要写入，跳过。")

        # Step 4: 删除同步
        # 仅在以下条件全部满足时执行：
        #   1. 未被 --skip_delete_sync 跳过
        #   2. 未使用选择性过滤参数（billno/billstatus/org_number 任一非空则跳过）
        #   3. biztime 范围有效（start 和 end 均不为 None）
        print("\n【Step 4】删除同步...")
        total_deleted = 0
        selective_filter_used = any([billno, billstatus, org_number])
        if skip_delete_sync:
            print("[删除同步] 已通过 --skip_delete_sync 跳过。")
        elif selective_filter_used:
            print("[删除同步] 检测到选择性过滤参数（billno/billstatus/org_number），"
                  "API 返回为子集，跳过删除比对以避免误删。")
        elif not (start_biztime and end_biztime):
            print("[删除同步] biztime 范围未指定，跳过。")
        else:
            api_ids = {str(row.get("id")) for row in all_rows}
            total_deleted = sync_deletes(conn, api_ids, start_biztime, end_biztime)

        # Step 5: 更新 sync_state
        print("\n【Step 5】更新 sync_state 状态记录...")
        upsert_sync_state(conn, API_NAME, TABLE_BILL,
                          datetime.datetime.now(), total_bills)

    finally:
        conn.close()
        print("[PG] 连接已关闭。")

    print("\n" + "=" * 60)
    print(f"同步完成：主表 upsert {total_bills} 条，明细 upsert {total_entries} 条，软删除 {total_deleted} 条。")
    print("=" * 60)


if __name__ == "__main__":
    main()
