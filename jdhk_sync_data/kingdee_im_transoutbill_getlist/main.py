"""
main.py
=======
职责：分步调出单同步流程总入口，串联 API 拉取 → 数据库写入两个步骤。

执行方式：
    # 默认同步（start_biztime=今天-30天，end_biztime=今天）
    python main.py

    # 按业务日期同步
    python main.py --start_biztime "2024-06-01" --end_biztime "2024-06-30"

    # 按审核时间增量同步
    python main.py --start_auditdate "2024-06-01 00:00:00" --end_auditdate "2024-06-30 23:59:59"

    # 只同步某单据状态（A=暂存 B=已提交 C=已审核，多个用逗号分隔）
    python main.py --billstatus A,B,C

    # 指定调出组织
    python main.py --org_number "BU-001,BU-002"

    # 指定单据编号
    python main.py --billno "DBCK-260405-000001"

参数优先级：命令行参数 > SYNC_PARAMS 默认值
默认 biztime 范围：今天往前 30 天 ~ 今天（每次运行时动态计算）
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import datetime
import psycopg2

from config                     import PG_CONFIG
from fetch_transoutbill         import fetch_all_pages
from load_transoutbill_to_pg    import upsert_rows

# =========================================================
# 常量
# =========================================================

API_NAME    = "/v2/im/im_transoutbill/getList"
TABLE_BILL  = "jdhk.kingdee_transoutbill"
TABLE_ENTRY = "jdhk.kingdee_transoutbill_entry"

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
# 命令行参数解析
# =========================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="金蝶分步调出单 → PostgreSQL 增量/全量同步",
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
                        help="调出组织编码（多个用逗号分隔）")
    parser.add_argument("--billno",          type=str, default=None, metavar="BILLNO",
                        help="单据编号（多个用逗号分隔）")
    return parser.parse_args()


# =========================================================
# 主流程
# =========================================================

def main():
    print("=" * 60)
    print("金蝶分步调出单 → PostgreSQL 同步")
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

    print(f"\n同步参数：")
    print(f"  start_biztime   : {start_biztime   or '（不过滤）'}")
    print(f"  end_biztime     : {end_biztime     or '（不过滤）'}")
    print(f"  start_auditdate : {start_auditdate or '（不过滤）'}")
    print(f"  end_auditdate   : {end_auditdate   or '（不过滤）'}")
    print(f"  billstatus      : {billstatus      or '（不过滤）'}")
    print(f"  org_number      : {org_number      or '（不过滤）'}")
    print(f"  billno          : {billno          or '（不过滤）'}")
    print(f"  pageSize        : {SYNC_PARAMS.get('pageSize')}")

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

        # Step 4: 更新 sync_state
        print("\n【Step 4】更新 sync_state 状态记录...")
        upsert_sync_state(conn, API_NAME, TABLE_BILL,
                          datetime.datetime.now(), total_bills)

    finally:
        conn.close()
        print("[PG] 连接已关闭。")

    print("\n" + "=" * 60)
    print(f"同步完成：主表 upsert {total_bills} 条，明细 upsert {total_entries} 条。")
    print("=" * 60)


if __name__ == "__main__":
    main()
