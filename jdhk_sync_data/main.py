"""
main.py
=======
职责：同步流程总入口，串联 API 拉取 → 数据库写入两个步骤。

执行方式：
    # 全量同步（使用 SYNC_PARAMS 默认参数）
    python main.py

    # 只传开始时间（结束时间用默认值）
    python main.py --modifytime_start "2024-06-01 00:00:00"

    # 只传结束时间（开始时间用默认值）
    python main.py --modifytime_end "2024-06-30 23:59:59"

    # 同时传两个时间（增量同步）
    python main.py --modifytime_start "2024-06-01 00:00:00" --modifytime_end "2024-06-30 23:59:59"

参数优先级：命令行参数 > SYNC_PARAMS 默认值
"""

import argparse
import datetime
import psycopg2

from config                 import PG_CONFIG
from fetch_inventory_detail import fetch_all_pages
from load_inventory_to_pg   import upsert_rows

# =========================================================
# 常量：API 名称 & 目标表名（与 sync_state 对应）
# =========================================================

API_NAME    = "/v2/im/getInventoryDetail"
TABLE_NAME  = "jdhk.kingdee_inventory_detail"

# =========================================================
# ✏️ 默认同步参数（命令行未传参时使用这里的值）
# =========================================================

SYNC_PARAMS = {
    # 增量同步时间区间（全量同步时保持 None）
    "modifytime_start": None,   # 例如 "2024-06-01 00:00:00"
    "modifytime_end":   None,   # 例如 "2024-06-30 23:59:59"

    # 组织过滤（None = 不过滤）
    "org":              "3200614",
    "org_number":       None,

    # 物料/仓库/批次过滤（None = 不过滤）
    "material_number":  None,
    "warehouse_number": None,
    "lot_number":       None,

    # 分页设置
    "pageSize":         100,    # 每页条数，建议 100~500
    "max_pages":        None,   # 最多拉取页数，None = 不限制
    "sleep_sec":        0.3,    # 翻页间隔（秒），防止接口限流
}

# 每批写入 PG 的行数
WRITE_BATCH_SIZE = 500


# =========================================================
# sync_state 状态表操作
# =========================================================

def upsert_sync_state(
    conn,
    api_name: str,
    table_name: str,
    last_sync_time: datetime.datetime,
    sync_rows: int,
    modifytime_start: str = None,
    modifytime_end: str = None,
):
    """
    将本次同步结果写入 sync_state 表。
    若该 (api_name, table_name) 记录已存在则更新，否则插入。
    """
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
    """解析命令行参数，两个时间参数均为可选，可单独传。"""
    parser = argparse.ArgumentParser(
        description="金蝶即时库存明细 → PostgreSQL 增量/全量同步",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--modifytime_start",
        type=str,
        default=None,
        metavar="DATETIME",
        help="增量同步起始时间，格式：'2024-06-01 00:00:00'\n（不传则使用 SYNC_PARAMS 中的默认值）",
    )
    parser.add_argument(
        "--modifytime_end",
        type=str,
        default=None,
        metavar="DATETIME",
        help="增量同步结束时间，格式：'2024-06-30 23:59:59'\n（不传则使用 SYNC_PARAMS 中的默认值）",
    )
    return parser.parse_args()


# =========================================================
# 主流程
# =========================================================

def main():
    print("=" * 60)
    print("金蝶即时库存明细 → PostgreSQL 同步")
    print("=" * 60)

    # ----------------------------------------------------------
    # 解析命令行参数，命令行参数优先于 SYNC_PARAMS 默认值
    # ----------------------------------------------------------
    args = parse_args()

    # 两个时间参数：命令行传了就用命令行，否则用 SYNC_PARAMS 默认
    modifytime_start = args.modifytime_start if args.modifytime_start is not None \
                       else SYNC_PARAMS.get("modifytime_start")
    modifytime_end   = args.modifytime_end   if args.modifytime_end   is not None \
                       else SYNC_PARAMS.get("modifytime_end")

    # 打印本次同步参数
    print(f"\n同步参数：")
    print(f"  modifytime_start : {modifytime_start or '（未设置，全量）'}")
    print(f"  modifytime_end   : {modifytime_end   or '（未设置，全量）'}")
    print(f"  org              : {SYNC_PARAMS.get('org')}")
    print(f"  pageSize         : {SYNC_PARAMS.get('pageSize')}")

    # ----------------------------------------------------------
    # Step 1: 从 API 拉取数据
    # ----------------------------------------------------------
    print("\n【Step 1】从 API 拉取数据...")
    all_rows = fetch_all_pages(
        modifytime_start = modifytime_start,
        modifytime_end   = modifytime_end,
        org              = SYNC_PARAMS.get("org"),
        org_number       = SYNC_PARAMS.get("org_number"),
        material_number  = SYNC_PARAMS.get("material_number"),
        warehouse_number = SYNC_PARAMS.get("warehouse_number"),
        lot_number       = SYNC_PARAMS.get("lot_number"),
        pageSize         = SYNC_PARAMS.get("pageSize"),
        max_pages        = SYNC_PARAMS.get("max_pages"),
        sleep_sec        = SYNC_PARAMS.get("sleep_sec"),
    )
    print(f"【Step 1 完成】共拉取 {len(all_rows)} 条原始记录。")

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

    total_upserted = 0

    try:
        # ----------------------------------------------------------
        # Step 3: 分批写入 PG（无数据时跳过）
        # ----------------------------------------------------------
        if all_rows:
            print(f"\n【Step 3】写入 PostgreSQL（每批 {WRITE_BATCH_SIZE} 条）...")
            for i in range(0, len(all_rows), WRITE_BATCH_SIZE):
                batch          = all_rows[i : i + WRITE_BATCH_SIZE]
                upserted       = upsert_rows(conn, batch)
                total_upserted += upserted
                print(f"[PG] 已写入 {total_upserted} / {len(all_rows)} 条")
        else:
            print("\n【Step 3】无数据需要写入，跳过。")

        # ----------------------------------------------------------
        # Step 4: 更新 sync_state 状态表
        # ----------------------------------------------------------
        print("\n【Step 4】更新 sync_state 状态记录...")
        upsert_sync_state(
            conn             = conn,
            api_name         = API_NAME,
            table_name       = TABLE_NAME,
            last_sync_time   = datetime.datetime.now(),
            sync_rows        = total_upserted,
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
    print(f"同步完成，共 upsert {total_upserted} 条即时库存明细记录。")
    print("=" * 60)


if __name__ == "__main__":
    main()
