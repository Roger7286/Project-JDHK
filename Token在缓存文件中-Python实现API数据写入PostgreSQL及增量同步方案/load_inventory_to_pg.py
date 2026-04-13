"""
load_inventory_to_pg.py
=======================
职责：接收外部传入的原始 rows，转换字段后批量 upsert 到 PostgreSQL。
      【增减字段只需修改此文件】

对外暴露：
    upsert_rows(conn, rows) → int   批量写入，返回写入行数

字段维护说明：
    - 新增字段：在 _row_to_pg() 的 return dict 中添加一行即可
    - 删除字段：在 _row_to_pg() 的 return dict 中删除对应行即可
    - 无需修改 fetch_inventory_detail.py 或 main.py

依赖：
    - psycopg2（数据库驱动）
    - config.py（PG_CONFIG，由 main.py 传入连接，此文件不直接读取）
"""

import datetime
import psycopg2
import psycopg2.extras

# ---------- 目标表名（按需修改）----------
TARGET_TABLE = "kingdee_inventory_detail"


# =========================================================
# 字段映射：API 原始 row → PG 表字段 dict
#
# ✏️  【增减字段在这里操作】
#     - 新增字段：加一行  "pg列名": _get("api字段名"),
#     - 删除字段：删除对应行
#     - 注意：pg列名 须与建表语句中的列名一致
# =========================================================

def _row_to_pg(row: dict) -> dict:
    """将接口返回的单条 row 转换成与 PG 表列名完全对应的 dict。"""

    def _get(key, default=None):
        return row.get(key, default)

    def _to_dt(val):
        """字符串 → datetime，None 安全。"""
        if not val:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.datetime.strptime(val, fmt)
            except ValueError:
                continue
        return None

    def _to_date(val):
        """字符串 → date，None 安全。"""
        if not val:
            return None
        try:
            return datetime.datetime.strptime(val[:10], "%Y-%m-%d").date()
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # ✏️ 字段映射表（增减字段只改这里，格式："pg列名": _get("api字段名")）
    # ------------------------------------------------------------------
    return {
        "id":                    str(_get("id")),
        # 组织
        "org":                   _get("org"),
        "org_number":            _get("org.number"),
        "org_name":              _get("org.name"),
        # 物料
        "material":              _get("material"),
        "material_number":       _get("material.number"),
        "material_name":         _get("material.name"),
        "material_modelnum":     _get("material.modelnum"),
        "material_helpcode":     _get("material.helpcode"),
        # 辅助属性 / 批次
        "auxpty":                _get("auxpty"),
        "lotnum":                _get("lotnum"),
        "producedate":           _to_date(_get("producedate")),
        "expirydate":            _to_date(_get("expirydate")),
        # 库存单位
        "unit":                  _get("unit"),
        "unit_number":           _get("unit.number"),
        "unit_name":             _get("unit.name"),
        "qty":                   _get("qty"),
        # 基本单位
        "baseunit":              _get("baseunit"),
        "baseunit_number":       _get("baseunit.number"),
        "baseunit_name":         _get("baseunit.name"),
        "baseqty":               _get("baseqty"),
        # 第二计量单位
        "unit2nd":               _get("unit2nd"),
        "unit2nd_number":        _get("unit2nd.number"),
        "unit2nd_name":          _get("unit2nd.name"),
        "qty2nd":                _get("qty2nd"),
        # 第三计量单位
        "unit3rd":               _get("unit3rd"),
        "unit3rd_number":        _get("unit3rd.number"),
        "unit3rd_name":          _get("unit3rd.name"),
        "qty3rd":                _get("qty3rd"),
        # 仓库
        "warehouse":             _get("warehouse"),
        "warehouse_number":      _get("warehouse.number"),
        "warehouse_name":        _get("warehouse.name"),
        # 货位
        "location":              _get("location"),
        "location_number":       _get("location.number"),
        "location_name":         _get("location.name"),
        # 库存状态
        "invstatus":             _get("invstatus"),
        "invstatus_number":      _get("invstatus.number"),
        "invstatus_name":        _get("invstatus.name"),
        # 库存类型
        "invtype":               _get("invtype"),
        "invtype_number":        _get("invtype.number"),
        "invtype_name":          _get("invtype.name"),
        # 货主
        "ownertype":             _get("ownertype"),
        "owner":                 _get("owner"),
        "owner_number":          _get("owner.number"),
        "owner_name":            _get("owner.name"),
        # 保管方
        "keepertype":            _get("keepertype"),
        "keeper":                _get("keeper"),
        "keeper_number":         _get("keeper.number"),
        "keeper_name":           _get("keeper.name"),
        # 跟踪号
        "tracknumber":           _get("tracknumber"),
        "tracknumber_number":    _get("tracknumber.number"),
        "tracknumber_name":      _get("tracknumber.name"),
        # 配置码
        "configuredcode":        _get("configuredcode"),
        "configuredcode_number": _get("configuredcode.number"),
        "configuredcode_name":   _get("configuredcode.name"),
        # 项目
        "project":               _get("project"),
        "project_number":        _get("project.number"),
        "project_name":          _get("project.name"),
        # 版本
        "mversion":              _get("mversion"),
        "mversion_number":       _get("mversion.number"),
        "mversion_name":         _get("mversion.name"),
        # 可用数量
        "avbbaseqty":            _get("avbbaseqty"),
        "avbqty":                _get("avbqty"),
        "avbqty2nd":             _get("avbqty2nd"),
        "avbqty3rd":             _get("avbqty3rd"),
        # 锁定/预留数量
        "baseqty_lock":          _get("baseqty_lock"),
        "qty_lock":              _get("qty_lock"),
        "qty2nd_lock":           _get("qty2nd_lock"),
        "qty3rd_lock":           _get("qty3rd_lock"),
        "lockbaseqty":           _get("lockbaseqty"),
        "lockqty":               _get("lockqty"),
        "lockqty2nd":            _get("lockqty2nd"),
        "lockqty3rd":            _get("lockqty3rd"),
        # 修改时间
        "modifytime":            _to_dt(_get("modifytime")),
        # ✏️ 新增字段示例（取消注释并填写实际 api 字段名）：
        # "new_pg_column": _get("api.field.name"),
    }


# =========================================================
# 动态生成 Upsert SQL（勿改）
# =========================================================

def _build_upsert_sql(columns: list) -> str:
    """根据字段列表动态生成 INSERT ... ON CONFLICT (id) DO UPDATE 语句。"""
    col_list   = ", ".join(columns)
    val_list   = ", ".join([f"%({c})s" for c in columns])
    update_set = ", ".join([f"{c} = EXCLUDED.{c}" for c in columns if c != "id"])
    return f"""
        INSERT INTO {TARGET_TABLE} ({col_list}, sync_time)
        VALUES ({val_list}, NOW())
        ON CONFLICT (id) DO UPDATE
        SET {update_set},
            sync_time = NOW()
    """


# =========================================================
# 批量 Upsert（对外接口）
# =========================================================

def upsert_rows(conn, rows: list) -> int:
    """
    将 rows 批量 upsert 到 PG 表。
    rows 为接口原始数据，内部自动调用 _row_to_pg() 转换字段。

    参数：
        conn  psycopg2 连接对象（由 main.py 传入）
        rows  list[dict]，fetch_inventory_detail.fetch_all_pages() 的返回值

    返回：
        int  实际写入行数
    """
    if not rows:
        print("[PG] 无数据需要写入。")
        return 0

    pg_rows = [_row_to_pg(r) for r in rows]
    columns = list(pg_rows[0].keys())
    sql     = _build_upsert_sql(columns)

    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, pg_rows, page_size=500)
    conn.commit()
    return len(pg_rows)
