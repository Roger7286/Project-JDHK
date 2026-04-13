"""
load_transinbill_to_pg.py
=========================
职责：接收外部传入的原始 rows，拆分主表/明细并批量 upsert 到 PostgreSQL。
      【增减字段只需修改此文件中的映射函数】

对外暴露：
    upsert_rows(conn, rows) → tuple[int, int]
        返回 (upserted_bills, upserted_entries)
"""

import datetime
import psycopg2
import psycopg2.extras

TABLE_BILL  = "jdhk.kingdee_transinbill"
TABLE_ENTRY = "jdhk.kingdee_transinbill_entry"


# =========================================================
# 辅助转换函数
# =========================================================

def _to_dt(val):
    if not val:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(val, fmt)
        except ValueError:
            continue
    return None


def _to_date(val):
    if not val:
        return None
    try:
        return datetime.datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _str(val):
    return str(val) if val is not None else None


# =========================================================
# 主表字段映射
# =========================================================

def _bill_to_pg(row: dict) -> dict:
    g = row.get
    return {
        "id":                       _str(g("id")),
        "billno":                   g("billno"),
        "billstatus":               g("billstatus"),
        "biztime":                  _to_date(g("biztime")),
        "bookdate":                 _to_date(g("bookdate")),
        "transtype":                g("transtype"),
        "transit":                  g("transit"),
        "org_number":               g("org_number"),
        "outorg_number":            g("outorg_number"),
        "billtype_number":          g("billtype_number"),
        "biztype_number":           g("biztype_number"),
        "biztype_name":             g("biztype_name"),
        "invscheme_number":         g("invscheme_number"),
        "invscheme_name":           g("invscheme_name"),
        "settlescurrency_number":   g("settlescurrency_number"),
        "settlescurrency_name":     g("settlescurrency_name"),
    }


# =========================================================
# 明细行字段映射
# =========================================================

def _entry_to_pg(entry: dict, bill_id) -> dict:
    g = entry.get
    return {
        "id":                     _str(g("id")),
        "bill_id":                _str(bill_id),

        # 物料
        "material_number":        g("material_number"),
        "material_name":          g("material_name"),

        # 调入仓库
        "warehouse_number":       g("warehouse_number"),
        "warehouse_name":         g("warehouse_name"),
        "location_number":        g("location_number"),
        "location_name":          g("location_name"),

        # 调出仓库
        "outwarehouse_number":    g("outwarehouse_number"),
        "outwarehouse_name":      g("outwarehouse_name"),
        "outlocation_number":     g("outlocation_number"),
        "outlocation_name":       g("outlocation_name"),

        # 数量
        "qty":                    g("qty"),
        "qtyunit3rd":             g("qtyunit3rd"),

        # 批次（该 API 可能不含 lotnumber，字段留空安全）
        "lotnumber":              g("lotnumber"),

        # 调入方
        "ownertype":              g("ownertype"),
        "owner_number":           g("owner_number"),
        "owner_name":             g("owner_name"),
        "keepertype":             g("keepertype"),
        "keeper_number":          g("keeper_number"),
        "keeper_name":            g("keeper_name"),
        "invstatus_number":       g("invstatus_number"),
        "invstatus_name":         g("invstatus_name"),
        "invtype_number":         g("invtype_number"),
        "invtype_name":           g("invtype_name"),

        # 调出方
        "outownertype":           g("outownertype"),
        "outowner_number":        g("outowner_number"),
        "outowner_name":          g("outowner_name"),
        "outkeepertype":          g("outkeepertype"),
        "outkeeper_number":       g("outkeeper_number"),
        "outkeeper_name":         g("outkeeper_name"),
        "outinvstatus_number":    g("outinvstatus_number"),
        "outinvstatus_name":      g("outinvstatus_name"),
        "outinvtype_number":      g("outinvtype_number"),
        "outinvtype_name":        g("outinvtype_name"),

        # 在途货主
        "transitownertype":       g("transitownertype"),
        "transitowner_number":    g("transitowner_number"),
        "transitowner_name":      g("transitowner_name"),

        # 项目
        "project_number":         g("project_number"),
        "project_name":           g("project_name"),

        # 单位
        "unit_number":            g("unit_number"),
        "unit_name":              g("unit_name"),
        "unit2nd_number":         g("unit2nd_number"),
        "unit2nd_name":           g("unit2nd_name"),
        "unit3rd_number":         g("unit3rd_number"),
        "unit3rd_name":           g("unit3rd_name"),
        "baseunit_number":        g("baseunit_number"),
        "baseunit_name":          g("baseunit_name"),

        # 物料版本
        "mversion_number":        g("mversion_number"),
        "mversion_name":          g("mversion_name"),

        # 行类型 / 跟踪号 / 配置号
        "linetype_number":        g("linetype_number"),
        "linetype_name":          g("linetype_name"),
        "tracknumber_number":     g("tracknumber_number"),
        "tracknumber_name":       g("tracknumber_name"),
        "configuredcode_number":  g("configuredcode_number"),
        "configuredcode_name":    g("configuredcode_name"),
    }


# =========================================================
# 动态生成 Upsert SQL
# =========================================================

def _build_upsert_sql(table: str, columns: list) -> str:
    col_list   = ", ".join(columns)
    val_list   = ", ".join([f"%({c})s" for c in columns])
    update_set = ", ".join([f"{c} = EXCLUDED.{c}" for c in columns if c != "id"])
    return f"""
        INSERT INTO {table} ({col_list}, sync_time)
        VALUES ({val_list}, NOW())
        ON CONFLICT (id) DO UPDATE
        SET {update_set},
            sync_time = NOW()
    """


# =========================================================
# 批量 Upsert（对外接口）
# =========================================================

def upsert_rows(conn, rows: list) -> tuple:
    """
    将 rows 批量 upsert 到主表和明细表。
    返回：(int, int)  (写入主表行数, 写入明细行数)
    """
    if not rows:
        print("[PG] 无数据需要写入。")
        return 0, 0

    bill_rows  = []
    entry_rows = []

    for row in rows:
        bill_id = row.get("id")
        bill_rows.append(_bill_to_pg(row))
        for entry in (row.get("billentry") or []):
            entry_rows.append(_entry_to_pg(entry, bill_id))

    # Upsert 主表
    bill_columns = list(bill_rows[0].keys())
    bill_sql     = _build_upsert_sql(TABLE_BILL, bill_columns)
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, bill_sql, bill_rows, page_size=500)
    conn.commit()
    print(f"[PG] 主表 upsert {len(bill_rows)} 条。")

    # Upsert 明细
    entry_count = 0
    if entry_rows:
        entry_columns = list(entry_rows[0].keys())
        entry_sql     = _build_upsert_sql(TABLE_ENTRY, entry_columns)
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, entry_sql, entry_rows, page_size=500)
        conn.commit()
        entry_count = len(entry_rows)
        print(f"[PG] 明细表 upsert {entry_count} 条。")
    else:
        print("[PG] 本批次无明细行数据。")

    return len(bill_rows), entry_count
