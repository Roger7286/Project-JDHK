"""
main.py
=======
职责：收料通知单同步流程总入口，串联 API 拉取 → 数据库写入两个步骤。

执行方式：
    # 全量同步（无时间过滤）
    python main.py

    # 按修改时间增量同步
    python main.py --modifytime_start "2024-06-01 00:00:00" --modifytime_end "2024-06-30 23:59:59"

    # 按业务日期同步
    python main.py --biztime_start "2024-06-01" --biztime_end "2024-06-30"

    # 只同步某单据状态（A=暂存 B=已提交 C=已审核）
    python main.py --billstatus C

参数优先级：命令行参数 > SYNC_PARAMS 默认值
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import datetime
import psycopg2

from config                         import PG_CONFIG
from fetch_purreceivebill           import fetch_all_pages
from load_purreceivebill_to_pg      import upsert_rows

# =========================================================
# 常量：API 名称 & 目标表名（与 sync_state 对应）
# =========================================================

API_NAME        = "/v2/im/im_purreceivebill/query"
TABLE_BILL      = "jdhk.kingdee_purreceivebill"
TABLE_ENTRY     = "jdhk.kingdee_purreceivebill_entry"

# =========================================================
# ✏️  默认同步参数（命令行未传参时使用这里的值）
# =========================================================

SYNC_PARAMS = {
    # 按修改时间增量（全量时保持 None，但至少要传 biztime 或 modifytime 其中一对）
    "modifytime_start": None,   # 例如 "2024-06-01 00:00:00"
    "modifytime_end":   None,   # 例如 "2024-06-30 23:59:59"

    # 按业务日期过滤（API 要求至少提供一个过滤条件，建议填写日期范围）
    "biztime_start":    "2025-01-01",   # ✏️ 按需调整起始日期
    "biztime_end":      "2026-12-31",   # ✏️ 按需调整截止日期

    # 其他过滤（None = 不过滤）
    "billno":           None,   # 单据编号精确查询（传了则只查该单据）
    "billstatus":       None,   # 单据状态：A / B / C
    "supplier_number":  None,   # 供应商编码

    # 分页设置
    "pageSize":         100,    # 每页条数，建议 100
    "max_pages":        None,   # 最多拉取页数，None = 不限制
    "sleep_sec":        0.3,    # 翻页间隔（秒）
}

# 每批写入 PG 的单据数量
WRITE_BATCH_SIZE = 200


# =========================================================
# sync_state 状态表操作
# =========================================================

def upsert_sync_state(
    conn,
    api_name:           str,
    table_name:         str,
    last_sync_time:     datetime.datetime,
    sync_rows:          int,
    modifytime_start:   str = None,
    modifytime_end:     str = None,
):
    """将本次同步结果写入 sync_state 表。"""
    sql = """
        INSERT INTO jdhk.sync_state
            (api_name, table_name, last_sync_time, sync_rows,
             modifytime_start, modifytime_end, created_at, updated_at)
        VALUES
            (%(api_name)s, %(table_name)s, %(last_sync_time)s, %(sync_rows)s,
             %(modifytime_start)s, %(modifytime_end)s, NOW(), NOW())
        ON CONFLICT (api_name, table_name) DO UPDATE
        SET last_sync_time   = EXCLUDED.last_sync_time,
            sync_rows        = EXCLUDED.sync_rows,
            modifytime_start = EXCLUDED.modifytime_start,
            modifytime_end   = EXCLUDED.modifytime_end,
            updated_at       = NOW()
    """
    params = {
        "api_name":         api_name,
        "table_name":       table_name,
        "last_sync_time":   last_sync_time,
        "sync_rows":        sync_rows,
        "modifytime_start": modifytime_start,
        "modifytime_end":   modifytime_end,
    }
    with conn.cursor() as cur:
        cur.execute(sql, params)
    conn.commit()
    print(f"[sync_state] 已更新: api={api_name}, table={table_name}, "
          f"last_sync_time={last_sync_time}, rows={sync_rows}")


# =========================================================
# 命令行参数解析
# =========================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="金蝶收料通知单 → PostgreSQL 增量/全量同步",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--modifytime_start", type=str, default=None, metavar="DATETIME",
        help="修改时间起，格式：'2024-06-01 00:00:00'",
    )
    parser.add_argument(
        "--modifytime_end", type=str, default=None, metavar="DATETIME",
        help="修改时间止，格式：'2024-06-30 23:59:59'",
    )
    parser.add_argument(
        "--biztime_start", type=str, default=None, metavar="DATE",
        help="业务日期起，格式：'2024-06-01'",
    )
    parser.add_argument(
        "--biztime_end", type=str, default=None, metavar="DATE",
        help="业务日期止，格式：'2024-06-30'",
    )
    parser.add_argument(
        "--billstatus", type=str, default=None, metavar="STATUS",
        help="单据状态：A=暂存 / B=已提交 / C=已审核",
    )
    parser.add_argument(
        "--supplier_number", type=str, default=None, metavar="CODE",
        help="供应商编码",
    )
    parser.add_argument(
        "--billno", type=str, default=None, metavar="BILLNO",
        help="单据编号（精确查询单张单据）",
    )
    return parser.parse_args()


# =========================================================
# 主流程
# =========================================================

def main():
    print("=" * 60)
    print("金蝶收料通知单 → PostgreSQL 同步")
    print("=" * 60)

    args = parse_args()

    # 命令行参数优先；未传则用 SYNC_PARAMS 默认值
    def _pick(cli_val, default_key):
        return cli_val if cli_val is not None else SYNC_PARAMS.get(default_key)

    modifytime_start = _pick(args.modifytime_start, "modifytime_start")
    modifytime_end   = _pick(args.modifytime_end,   "modifytime_end")
    biztime_start    = _pick(args.biztime_start,    "biztime_start")
    biztime_end      = _pick(args.biztime_end,      "biztime_end")
    billstatus       = _pick(args.billstatus,       "billstatus")
    supplier_number  = _pick(args.supplier_number,  "supplier_number")
    billno           = _pick(args.billno,           "billno")

    print(f"\n同步参数：")
    print(f"  modifytime_start : {modifytime_start or '（不过滤）'}")
    print(f"  modifytime_end   : {modifytime_end   or '（不过滤）'}")
    print(f"  biztime_start    : {biztime_start    or '（不过滤）'}")
    print(f"  biztime_end      : {biztime_end      or '（不过滤）'}")
    print(f"  billstatus       : {billstatus       or '（不过滤）'}")
    print(f"  supplier_number  : {supplier_number  or '（不过滤）'}")
    print(f"  billno           : {billno           or '（不过滤）'}")
    print(f"  pageSize         : {SYNC_PARAMS.get('pageSize')}")

    # ----------------------------------------------------------
    # Step 1: 从 API 拉取数据
    # ----------------------------------------------------------
    print("\n【Step 1】从 API 拉取数据...")
    all_rows = fetch_all_pages(
        modifytime_start=modifytime_start,
        modifytime_end=modifytime_end,
        biztime_start=biztime_start,
        biztime_end=biztime_end,
        billno=billno,
        billstatus=billstatus,
        supplier_number=supplier_number,
        pageSize=SYNC_PARAMS.get("pageSize"),
        max_pages=SYNC_PARAMS.get("max_pages"),
        sleep_sec=SYNC_PARAMS.get("sleep_sec"),
    )
    print(f"【Step 1 完成】共拉取 {len(all_rows)} 张单据。")

    # ----------------------------------------------------------
    # Step 2: 建立 PG 连接
    # ----------------------------------------------------------
    print("\n【Step 2】连接 PostgreSQL...")
    conn = psycopg2.connect(
        host     = PG_CONFIG["host"],
        port     = PG_CONFIG["port"],
        dbname   = PG_CONFIG["database"],
        user     = PG_CONFIG["user"],
        password = PG_CONFIG["password"],
    )
    print(f"[PG] 已连接: {PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['database']}")

    total_bills   = 0
    total_entries = 0

    try:
        # ----------------------------------------------------------
        # Step 3: 分批写入 PG
        # ----------------------------------------------------------
        if all_rows:
            print(f"\n【Step 3】写入 PostgreSQL（每批 {WRITE_BATCH_SIZE} 张单据）...")
            for i in range(0, len(all_rows), WRITE_BATCH_SIZE):
                batch              = all_rows[i : i + WRITE_BATCH_SIZE]
                upserted_b, upserted_e = upsert_rows(conn, batch)
                total_bills        += upserted_b
                total_entries      += upserted_e
                print(f"[PG] 累计 主表={total_bills} / {len(all_rows)}，"
                      f"明细={total_entries}")
        else:
            print("\n【Step 3】无数据需要写入，跳过。")

        # ----------------------------------------------------------
        # Step 4: 更新 sync_state 状态表（以主表为代表记录）
        # ----------------------------------------------------------
        print("\n【Step 4】更新 sync_state 状态记录...")
        upsert_sync_state(
            conn             = conn,
            api_name         = API_NAME,
            table_name       = TABLE_BILL,
            last_sync_time   = datetime.datetime.now(),
            sync_rows        = total_bills,
            modifytime_start = modifytime_start,
            modifytime_end   = modifytime_end,
        )

    finally:
        conn.close()
        print("[PG] 连接已关闭。")

    # ----------------------------------------------------------
    # 汇总
    # ----------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"同步完成：主表 upsert {total_bills} 条，明细 upsert {total_entries} 条。")
    print("=" * 60)


if __name__ == "__main__":
    main()
