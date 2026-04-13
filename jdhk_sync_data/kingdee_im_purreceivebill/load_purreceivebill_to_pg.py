"""
load_purreceivebill_to_pg.py
============================
职责：接收外部传入的原始 bills，拆分为「单据头」和「明细行」，
      分别转换字段后批量 upsert 到 PostgreSQL 两张表。

      【增减字段只需修改此文件】

对外暴露：
    upsert_bills(conn, bills) -> (int, int)   写入 (头表行数, 明细行数)

字段维护说明：
    - 新增字段：在 _bill_to_pg() 或 _entry_to_pg() 的 return dict 中添加一行
    - 删除字段：删除对应行
    - 无需修改 fetch_purreceivebill.py 或 main_purreceivebill.py

表结构：
    jdhk.kingdee_pur_receivebill        -- 单据头（一张单据一行）
    jdhk.kingdee_pur_receivebill_entry  -- 明细行（一张单据多行，通过 bill_id 关联）

依赖：
    - psycopg2（数据库驱动）
"""

import datetime
import psycopg2
import psycopg2.extras


# ---------- 目标表名 ----------
TABLE_BILL  = "jdhk.kingdee_pur_receivebill"
TABLE_ENTRY = "jdhk.kingdee_pur_receivebill_entry"


# =========================================================
# 通用工具函数
# =========================================================

def _to_dt(val):
    """字符串 -> datetime，None 安全。"""
    if not val:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(val, fmt)
        except ValueError:
            continue
    return None


def _to_date(val):
    """字符串 -> date，None 安全。"""
    if not val:
        return None
    try:
        return datetime.datetime.strptime(val[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _to_decimal(val):
    """字符串/数字 -> float，None 安全。"""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# =========================================================
# 单据头字段映射
#
# 增减单据头字段在这里操作：
#   - 新增字段：加一行  "pg列名": _get("api字段名"),
#   - 删除字段：删除对应行
#   - 注意：pg列名 须与建表语句中的列名一致
# =========================================================

def _bill_to_pg(bill: dict) -> dict:
    """将接口返回的单条 bill（单据头）转换成 PG 表字段 dict。"""

    def _get(key, default=None):
        return bill.get(key, default)

    return {
        # 主键
        "id":                       str(_get("id")),
        # 单据基本信息
        "billno":                   _get("billno"),
        "billtype":                 _get("billtype"),
        "billtype_number":          _get("billtype.number"),
        "billtype_name":            _get("billtype.name"),
        "billstatus":               _get("billstatus"),
        "billstatus_name":          _get("billstatus.name"),
        # 日期
        "date":                     _to_date(_get("date")),
        "approvedate":              _to_date(_get("approvedate")),
        # 业务组织
        "org":                      _get("org"),
        "org_number":               _get("org.number"),
        "org_name":                 _get("org.name"),
        # 仓储组织
        "stockorg":                 _get("stockorg"),
        "stockorg_number":          _get("stockorg.number"),
        "stockorg_name":            _get("stockorg.name"),
        # 供应商
        "supplier":                 _get("supplier"),
        "supplier_number":          _get("supplier.number"),
        "supplier_name":            _get("supplier.name"),
        # 货主
        "ownertype":                _get("ownertype"),
        "owner":                    _get("owner"),
        "owner_number":             _get("owner.number"),
        "owner_name":               _get("owner.name"),
        # 收料部门 / 操作人
        "department":               _get("department"),
        "department_number":        _get("department.number"),
        "department_name":          _get("department.name"),
        "operator":                 _get("operator"),
        "operator_number":          _get("operator.number"),
        "operator_name":            _get("operator.name"),
        # 审核人
        "approver":                 _get("approver"),
        "approver_number":          _get("approver.number"),
        "approver_name":            _get("approver.name"),
        # 采购员
        "purchaser":                _get("purchaser"),
        "purchaser_number":         _get("purchaser.number"),
        "purchaser_name":           _get("purchaser.name"),
        # 来源单据类型
        "srcbilltype":              _get("srcbilltype"),
        "srcbilltype_name":         _get("srcbilltype.name"),
        # 关联收料通知单
        "receivenote":              _get("receivenote"),
        "receivenote_number":       _get("receivenote.number"),
        # 备注
        "remark":                   _get("remark"),
        # 时间戳
        "modifytime":               _to_dt(_get("modifytime")),
        "createtime":               _to_dt(_get("createtime")),
        # 新增字段示例（取消注释并填写实际 api 字段名）：
        # "new_pg_column": _get("api.field.name"),
    }


# =========================================================
# 明细行字段映射
#
# 增减明细行字段在这里操作（同上）
# =========================================================

def _entry_to_pg(bill_id: str, bill_no: str, entry: dict) -> dict:
    """将接口返回的单条明细行 entry 转换成 PG 表字段 dict。"""

    def _get(key, default=None):
        return entry.get(key, default)

    return {
        # 主键（明细行内码）
        "id":                       str(_get("id")),
        # 关联单据头
        "bill_id":                  bill_id,
        "billno":                   bill_no,
        "seq":                      _get("seq"),
        # 物料
        "material":                 _get("material"),
        "material_number":          _get("material.number"),
        "material_name":            _get("material.name"),
        "material_modelnum":        _get("material.modelnum"),
        "material_helpcode":        _get("material.helpcode"),
        # 物料分类
        "materialgroup":            _get("materialgroup"),
        "materialgroup_number":     _get("materialgroup.number"),
        "materialgroup_name":       _get("materialgroup.name"),
        # 仓库 / 货位
        "warehouse":                _get("warehouse"),
        "warehouse_number":         _get("warehouse.number"),
        "warehouse_name":           _get("warehouse.name"),
        "location":                 _get("location"),
        "location_number":          _get("location.number"),
        "location_name":            _get("location.name"),
        # 计量单位
        "unit":                     _get("unit"),
        "unit_number":              _get("unit.number"),
        "unit_name":                _get("unit.name"),
        # 基本单位
        "baseunit":                 _get("baseunit"),
        "baseunit_number":          _get("baseunit.number"),
        "baseunit_name":            _get("baseunit.name"),
        # 数量
        "qty":                      _to_decimal(_get("qty")),
        "baseqty":                  _to_decimal(_get("baseqty")),
        "qty2nd":                   _to_decimal(_get("qty2nd")),
        "qty3rd":                   _to_decimal(_get("qty3rd")),
        # 实收数量
        "actreceiveqty":            _to_decimal(_get("actreceiveqty")),
        "actreceivebaseqty":        _to_decimal(_get("actreceivebaseqty")),
        # 已开票 / 已结算数量
        "invoicedqty":              _to_decimal(_get("invoicedqty")),
        "settleqty":                _to_decimal(_get("settleqty")),
        # 价格 / 金额
        "price":                    _to_decimal(_get("price")),
        "taxprice":                 _to_decimal(_get("taxprice")),
        "taxrate":                  _to_decimal(_get("taxrate")),
        "amount":                   _to_decimal(_get("amount")),
        "taxamount":                _to_decimal(_get("taxamount")),
        "allamount":                _to_decimal(_get("allamount")),
        # 批次
        "lot":                      _get("lot"),
        "lot_number":               _get("lot.number"),
        "producedate":              _to_date(_get("producedate")),
        "expirydate":               _to_date(_get("expirydate")),
        # 库存状态
        "invstatus":                _get("invstatus"),
        "invstatus_number":         _get("invstatus.number"),
        "invstatus_name":           _get("invstatus.name"),
        # 辅助属性
        "auxpty":                   _get("auxpty"),
        # 货主（行级）
        "ownertype":                _get("ownertype"),
        "owner":                    _get("owner"),
        "owner_number":             _get("owner.number"),
        "owner_name":               _get("owner.name"),
        # 来源采购订单关联
        "srcbillentryid":           _get("srcbillentryid"),
        "srcbillno":                _get("srcbillno"),
        "srcseq":                   _get("srcseq"),
        # 行备注
        "remark":                   _get("remark"),
        # 时间戳
        "modifytime":               _to_dt(_get("modifytime")),
        # 新增字段示例：
        # "new_pg_column": _get("api.field.name"),
    }


# =========================================================
# 动态生成 Upsert SQL（勿改）
# =========================================================

def _build_upsert_sql(table: str, columns: list) -> str:
    """根据字段列表动态生成 INSERT ... ON CONFLICT (id) DO UPDATE 语句。"""
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

def upsert_bills(conn, bills: list) -> tuple:
    """
    将 bills 拆分为单据头和明细行，分别批量 upsert 到 PG 两张表。

    参数：
        conn   psycopg2 连接对象（由 main_purreceivebill.py 传入）
        bills  list[dict]，fetch_purreceivebill.fetch_all_pages() 的返回值
               每个 dict 为一张单据，其中 "entry" 键对应明细行列表

    返回：
        (int, int)  (写入头表行数, 写入明细行数)
    """
    if not bills:
        print("[PG] 无数据需要写入。")
        return 0, 0

    # ---- 单据头 ----
    pg_bills  = [_bill_to_pg(b) for b in bills]
    bill_cols = list(pg_bills[0].keys())
    bill_sql  = _build_upsert_sql(TABLE_BILL, bill_cols)

    # ---- 明细行 ----
    pg_entries = []
    for bill in bills:
        bill_id = str(bill.get("id", ""))
        bill_no = bill.get("billno", "")
        entries = bill.get("entry", []) or []
        for entry in entries:
            pg_entries.append(_entry_to_pg(bill_id, bill_no, entry))

    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, bill_sql, pg_bills, page_size=500)
        if pg_entries:
            entry_cols = list(pg_entries[0].keys())
            entry_sql  = _build_upsert_sql(TABLE_ENTRY, entry_cols)
            psycopg2.extras.execute_batch(cur, entry_sql, pg_entries, page_size=500)

    conn.commit()
    return len(pg_bills), len(pg_entries)
