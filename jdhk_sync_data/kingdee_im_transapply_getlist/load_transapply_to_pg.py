"""
load_transapply_to_pg.py
========================
职责：接收外部传入的原始 rows，拆分主表/明细并批量 upsert 到 PostgreSQL。
      【增减字段只需修改此文件中的映射函数】

对外暴露：
    upsert_rows(conn, rows) → tuple[int, int]
        返回 (upserted_bills, upserted_entries)

拆分逻辑：
    每条 API row 包含：
      - 主表字段（billno, billstatus 等）
      - billentry：list[dict]，明细行列表

写入策略：
    - 主表  ON CONFLICT (id) → 全字段覆盖更新
    - 明细  ON CONFLICT (id) → 全字段覆盖更新
"""

import datetime
import psycopg2
import psycopg2.extras

TABLE_BILL  = "jdhk.kingdee_transapply"
TABLE_ENTRY = "jdhk.kingdee_transapply_entry"


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
        "id":                     _str(g("id")),
        "billno":                 g("billno"),
        "billstatus":             g("billstatus"),
        "auditdate":              _to_dt(g("auditdate")),
        "modifytime":             _to_dt(g("modifytime")),
        "createtime":             _to_dt(g("createtime")),
        "biztime":                _to_date(g("biztime")),
        "comment":                g("comment"),
        "closedate":              _to_dt(g("closedate")),
        "closestatus":            g("closestatus"),
        "handcloseflag":          g("handcloseflag"),
        "transtype":              g("transtype"),
        "biztype_number":         g("biztype_number"),
        "biztype_name":           g("biztype_name"),
        "billtype_number":        g("billtype_number"),
        "billtype_name":          g("billtype_name"),
        "org_number":             g("org_number"),
        "org_name":               g("org_name"),
        "applydept_number":       g("applydept_number"),
        "applyuser_number":       g("applyuser_number"),
        "settlecurrency_number":  g("settlecurrency_number"),
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

        # 调出仓库
        "warehouse_number":       g("warehouse_number"),
        "warehouse_name":         g("warehouse_name"),
        "location_number":        g("location_number"),
        "location_name":          g("location_name"),

        # 调入仓库
        "inwarehouse_number":     g("inwarehouse_number"),
        "inwarehouse_name":       g("inwarehouse_name"),
        "inlocation_number":      g("inlocation_number"),
        "inlocation_name":        g("inlocation_name"),

        # 数量
        "qty":                    g("qty"),
        "qtyunit2nd":             g("qtyunit2nd"),
        "qtyunit3rd":             g("qtyunit3rd"),

        # 调拨数量
        "transinqty":             g("transinqty"),
        "transoutqty":            g("transoutqty"),
        "remaintransoutqty":      g("remaintransoutqty"),

        # 日期
        "producedate":            _to_date(g("producedate")),
        "expirydate":             _to_date(g("expirydate")),

        # 批次 / 属性
        "lotnumber":              g("lotnumber"),
        "auxpty":                 _str(g("auxpty")),

        # 调出方
        "ownertype":              g("ownertype"),
        "owner_number":           g("owner_number"),
        "owner_name":             g("owner_name"),
        "keepertype":             g("keepertype"),
        "keeper_number":          g("keeper_number"),
        "keeper_name":            g("keeper_name"),

        # 调入方
        "inownertype":            g("inownertype"),
        "inowner_number":         g("inowner_number"),
        "inowner_name":           g("inowner_name"),
        "inkeepertype":           g("inkeepertype"),
        "inkeeper_number":        g("inkeeper_number"),
        "inkeeper_name":          g("inkeeper_name"),

        # 库存状态/类型（调出）
        "invstatus_number":       g("invstatus_number"),
        "invstatus_name":         g("invstatus_name"),
        "invtype_number":         g("invtype_number"),
        "invtype_name":           g("invtype_name"),

        # 库存状态/类型（调入）
        "ininvstatus_number":     g("ininvstatus_number"),
        "ininvstatus_name":       g("ininvstatus_name"),
        "ininvtype_number":       g("ininvtype_number"),
        "ininvtype_name":         g("ininvtype_name"),

        # 组织
        "outorg_number":          g("outorg_number"),
        "outorg_name":            g("outorg_name"),
        "inorg_number":           g("inorg_number"),
        "inorg_name":             g("inorg_name"),

        # 项目
        "project_number":         g("project_number"),
        "project_name":           g("project_name"),
        "inproject_number":       g("inproject_number"),
        "inproject_name":         g("inproject_name"),

        # 比率
        "transrateup":            g("transrateup"),
        "transratedown":          g("transratedown"),

        # 单位
        "unit_number":            g("unit_number"),
        "unit_name":              g("unit_name"),
        "unit2nd_number":         g("unit2nd_number"),
        "unit2nd_name":           g("unit2nd_name"),
        "unit3rd_number":         g("unit3rd_number"),
        "unit3rd_name":           g("unit3rd_name"),

        # 物料版本
        "mversion_number":        g("mversion_number"),
        "mversion_name":          g("mversion_name"),

        # 行类型 / 跟踪号 / 配置号
        "linetype_number":        g("linetype_number"),
        "linetype_name":          g("linetype_name"),
        "tracknumber_number":     g("tracknumber_number"),
        "configuredcode_number":  g("configuredcode_number"),
        "configuredcode_name":    g("configuredcode_name"),

        # 备注
        "entrycomment":           g("entrycomment"),
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
