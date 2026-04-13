"""
main_purreceivebill.py
======================
职责：采购收料单同步流程总入口，串联 API 拉取 -> 数据库写入两个步骤。

执行方式：
    # 全量同步（使用 SYNC_PARAMS 默认参数）
    python main_purreceivebill.py

    # 按修改时间增量同步
    python main_purreceivebill.py --modifytime_start "2024-06-01 00:00:00" --modifytime_end "2024-06-30 23:59:59"

    # 按单据日期范围同步
    python main_purreceivebill.py --date_start "2024-06-01" --date_end "2024-06-30"

    # 只同步已审核单据
    python main_purreceivebill.py --billstatus 3

参数优先级：命令行参数 > SYNC_PARAMS 默认值
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import datetime
import psycopg2

from config                    import PG_CONFIG
from fetch_purreceivebill      import fetch_all_pages
from load_purreceivebill_to_pg import upsert_bills

# =========================================================
# 常量：API 名称 & 目标表名（与 sync_state 对应）
# =========================================================

API_NAME         = "/v2/im/im_purreceivebill/query"
TABLE_NAME_BILL  = "jdhk.kingdee_pur_receivebill"
TABLE_NAME_ENTRY = "jdhk.kingdee_pur_receivebill_entry"

# =========================================================
# 默认同步参数（命令行未传参时使用这里的值）
# =========================================================

SYNC_PARAMS = {
    # 单据状态过滤（None = 不过滤；常用值：3 = 已审核）
    "billstatus":        None,

    # 增量同步时间区间（全量时保持 None）
    "modifytime_start":  None,   # 例如 "2024-06-01 00:00:00"
    "modifytime_end":    None,

    # 单据日期范围（None = 不过滤）
    "date_start":        None,   # 例如 "2024-06-01"
    "date_end":          None,

    # 业务组织 / 供应商 / 物料 / 仓库过滤（None = 不过滤）
    "org_number":        None,
    "supplier_number":   None,
    "material_number":   None,
    "warehouse_number":  None,

    # 分页设置
    "pageSize":          100,
    "max_pages":         None,   # None = 不限制
    "sleep_sec":         0.3,
}

# 每批写入 PG 的单据数
WRITE_BATCH_SIZE = 200


# =========================================================
# sync_state 状态表操作
# =========================================================

def upsert_sync_state(
    conn,
    api_name:         str,
    table_name:       str,
    last_sync_time:   datetime.datetime,
    sync_rows:        int,
    modifytime_start: str = None,
    modifytime_end:   str = None,
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
        description="金蝶苍穹采购收料单 -> PostgreSQL 增量/全量同步",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--modifytime_start", type=str, default=None,
                        metavar="DATETIME", help="修改时间起，格式：'2024-06-01 00:00:00'")
    parser.add_argument("--modifytime_end",   type=str, default=None,
                        metavar="DATETIME", help="修改时间止，格式：'2024-06-30 23:59:59'")
    parser.add_argument("--date_start",       type=str, default=None,
                        metavar="DATE",     help="单据日期起，格式：'2024-06-01'")
    parser.add_argument("--date_end",         type=str, default=None,
                        metavar="DATE",     help="单据日期止，格式：'2024-06-30'")
    parser.add_argument("--billstatus",       type=str, default=None,
                        metavar="STATUS",   help="单据状态：1=暂存 2=已提交 3=已审核 4=已关闭")
    return parser.parse_args()


# =========================================================
# 主流程
# =========================================================

def main():
    print("=" * 60)
    print("金蝶苍穹采购收料单 -> PostgreSQL 同步")
    print("=" * 60)

    args = parse_args()

    # 命令行参数优先于 SYNC_PARAMS 默认值
    modifytime_start = args.modifytime_start or SYNC_PARAMS.get("modifytime_start")
    modifytime_end   = args.modifytime_end   or SYNC_PARAMS.get("modifytime_end")
    date_start       = args.date_start       or SYNC_PARAMS.get("date_start")
    date_end         = args.date_end         or SYNC_PARAMS.get("date_end")
    billstatus       = args.billstatus       or SYNC_PARAMS.get("billstatus")

    print(f"\n同步参数：")
    print(f"  modifytime_start : {modifytime_start or '（未设置）'}")
    print(f"  modifytime_end   : {modifytime_end   or '（未设置）'}")
    print(f"  date_start       : {date_start       or '（未设置）'}")
    print(f"  date_end         : {date_end         or '（未设置）'}")
    print(f"  billstatus       : {billstatus        or '（不过滤）'}")
    print(f"  org_number       : {SYNC_PARAMS.get('org_number') or '（不过滤）'}")
    print(f"  pageSize         : {SYNC_PARAMS.get('pageSize')}")

    # ----------------------------------------------------------
    # Step 1: 从 API 拉取数据
    # ----------------------------------------------------------
    print("\n【Step 1】从 API 拉取采购收料单...")
    all_bills = fetch_all_pages(
        billstatus       = billstatus,
        org_number       = SYNC_PARAMS.get("org_number"),
        supplier_number  = SYNC_PARAMS.get("supplier_number"),
        material_number  = SYNC_PARAMS.get("material_number"),
        warehouse_number = SYNC_PARAMS.get("warehouse_number"),
        date_start       = date_start,
        date_end         = date_end,
        modifytime_start = modifytime_start,
        modifytime_end   = modifytime_end,
        pageSize         = SYNC_PARAMS.get("pageSize"),
        max_pages        = SYNC_PARAMS.get("max_pages"),
        sleep_sec        = SYNC_PARAMS.get("sleep_sec"),
    )
    total_entries = sum(len(b.get("entry", []) or []) for b in all_bills)
    print(f"【Step 1 完成】共拉取 {len(all_bills)} 张单据，{total_entries} 条明细行。")

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

    total_bill_upserted  = 0
    total_entry_upserted = 0

    try:
        # ----------------------------------------------------------
        # Step 3: 分批写入 PG
        # ----------------------------------------------------------
        if all_bills:
            print(f"\n【Step 3】写入 PostgreSQL（每批 {WRITE_BATCH_SIZE} 张单据）...")
            for i in range(0, len(all_bills), WRITE_BATCH_SIZE):
                batch          = all_bills[i : i + WRITE_BATCH_SIZE]
                n_bills, n_ent = upsert_bills(conn, batch)
                total_bill_upserted  += n_bills
                total_entry_upserted += n_ent
                print(f"[PG] 已写入单据头 {total_bill_upserted}/{len(all_bills)}，"
                      f"明细行 {total_entry_upserted}/{total_entries}")
        else:
            print("\n【Step 3】无数据需要写入，跳过。")

        # ----------------------------------------------------------
        # Step 4: 更新 sync_state 状态表
        # ----------------------------------------------------------
        print("\n【Step 4】更新 sync_state 状态记录...")
        upsert_sync_state(
            conn             = conn,
            api_name         = API_NAME,
            table_name       = f"{TABLE_NAME_BILL} + {TABLE_NAME_ENTRY}",
            last_sync_time   = datetime.datetime.now(),
            sync_rows        = total_bill_upserted,
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
    print(f"同步完成：单据头 {total_bill_upserted} 条，明细行 {total_entry_upserted} 条。")
    print("=" * 60)


if __name__ == "__main__":
    main()
