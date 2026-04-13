import requests
import json
import datetime
import os
import time

import psycopg2
import psycopg2.extras

from config import OPENAPI_CONFIG, SYNC_CONFIG, API_PATHS, PG_CONFIG

# =========================================================
# 金蝶 OpenAPI - 销售订单查询 → 写入 PostgreSQL（完整版）
# 接口地址: /v2/sm/sm_salorder/query
# 文档:     https://dev.kingdee.com/open/detail/api/1769178924861893632
#
# 表结构（三张表，层级关系）：
#   sm_salorder               — 销售订单主表（单据头）
#   sm_salorder_entry         — 销售订单明细行（billentry）
#   sm_salorder_deliver_entry — 交货计划子行（orderdeliverentry）
#
# 说明：
#   auxpty（弹性域）以 JSON key=弹性域名称 存储，整体写入 JSONB 列；
#   auxpty.id 单独提取存储到 auxpty_id 字段。
#
# 写入策略: INSERT ... ON CONFLICT (id) DO UPDATE（按主键 upsert）
# 配置:     统一读取 config.py
# Token:    优先读 kingdee_token_cache.json，过期才重新申请
# =========================================================

# ---------- 常用配置快捷引用 ----------
_BASE_URL         = OPENAPI_CONFIG["base_url"]
_TOKEN_PATH       = OPENAPI_CONFIG["token_path"]
_X_ACGW_IDENTITY  = OPENAPI_CONFIG["x_acgw_identity"]
_TOKEN_CACHE_FILE = OPENAPI_CONFIG["token_cache_file"]
_SAL_ORDER_PATH   = API_PATHS["sal_order"]
_REQUEST_TIMEOUT  = SYNC_CONFIG["request_timeout"]

# ---------- 目标表名 ----------
TABLE_HEADER  = "sm_salorder"
TABLE_ENTRY   = "sm_salorder_entry"
TABLE_DELIVER = "sm_salorder_deliver_entry"


# =========================================================
# Token 管理
# =========================================================

def _fetch_new_token() -> dict:
    """向金蝶认证接口申请新 Token，写入缓存，返回 {access_token, expire_at}。"""
    url = f"{_BASE_URL}{_TOKEN_PATH}"
    headers = {
        "Content-Type":    "application/json",
        "x-acgw-identity": _X_ACGW_IDENTITY,
    }
    payload = {
        "accountId":     OPENAPI_CONFIG["account_id"],
        "client_id":     OPENAPI_CONFIG["client_id"],
        "username":      OPENAPI_CONFIG["username"],
        "client_secret": OPENAPI_CONFIG["client_secret"],
        "language":      OPENAPI_CONFIG["language"],
        "nonce":         datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp":     datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=_REQUEST_TIMEOUT)
    print(f"[Token] HTTP {resp.status_code}")
    resp.raise_for_status()

    resp_json = resp.json()
    inner = resp_json.get("data", {})
    access_token = inner.get("access_token")
    if not access_token:
        raise ValueError(
            f"未在响应中找到 access_token，完整返回: {json.dumps(resp_json, ensure_ascii=False)}"
        )

    raw_expires = inner.get("expires_in", 7200 * 1000)
    expire_in   = int(raw_expires / 1000) if raw_expires > 86400 else int(raw_expires)
    expire_at   = (datetime.datetime.now() + datetime.timedelta(seconds=expire_in - 300)).isoformat()

    token_cache = {"access_token": access_token, "expire_at": expire_at}
    with open(_TOKEN_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(token_cache, f, ensure_ascii=False, indent=2)
    print(f"[Token] 新 Token 已缓存，有效至: {expire_at}")
    return token_cache


def get_valid_token() -> str:
    """优先从 kingdee_token_cache.json 读取；过期/不存在时重新申请。"""
    if os.path.exists(_TOKEN_CACHE_FILE):
        try:
            with open(_TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
            expire_at = datetime.datetime.fromisoformat(cache["expire_at"])
            if datetime.datetime.now() < expire_at:
                print(f"[Token] 使用缓存 Token，有效至: {expire_at}")
                return cache["access_token"]
            else:
                print("[Token] 缓存 Token 已过期，重新获取...")
        except Exception as e:
            print(f"[Token] 读取缓存失败: {e}，重新获取...")
    else:
        print("[Token] 未找到缓存文件，首次获取 Token...")
    return _fetch_new_token()["access_token"]


# =========================================================
# 销售订单查询（单页）
# =========================================================

def query_sal_order(
    start_bizdate:     str   = None,
    end_bizdate:       str   = None,
    id:                list  = None,
    billno:            list  = None,
    billstatus:        list  = None,
    org_number:        list  = None,
    start_createtime:  str   = None,
    end_createtime:    str   = None,
    start_modifytime:  str   = None,
    end_modifytime:    str   = None,
    start_auditdate:   str   = None,
    end_auditdate:     str   = None,
    customer_number:   list  = None,
    pageNo:            int   = 1,
    pageSize:          int   = None,
) -> dict:
    """
    调用金蝶销售订单查询接口（单页），返回原始 JSON dict。

    参数说明：
        start_bizdate / end_bizdate       订单日期区间，格式 '2024-01-01'
        id                                订单内部 ID 列表
        billno                            单据编号列表
        billstatus                        单据状态：A=保存 B=提交 C=审核
        org_number                        销售组织编码列表
        start_createtime / end_createtime 创建时间区间，格式 '2024-01-01 00:00:00'
        start_modifytime / end_modifytime 修改时间区间（增量同步推荐）
        start_auditdate  / end_auditdate  审核时间区间
        customer_number                   客户编码列表
    """
    if pageSize is None:
        pageSize = SYNC_CONFIG["page_size"]

    access_token = get_valid_token()
    url = f"{_BASE_URL}{_SAL_ORDER_PATH}"
    # 注意：销售订单接口 Header 使用 "accesstoken"（无下划线）
    headers = {
        "Content-Type":    "application/json",
        "accesstoken":     access_token,
        "x-acgw-identity": _X_ACGW_IDENTITY,
    }

    filter_data: dict = {}
    if start_bizdate:    filter_data["start_bizdate"]    = start_bizdate
    if end_bizdate:      filter_data["end_bizdate"]      = end_bizdate
    if id:               filter_data["id"]               = id
    if billno:           filter_data["billno"]           = billno
    if billstatus:       filter_data["billstatus"]       = billstatus
    if org_number:       filter_data["org_number"]       = org_number
    if start_createtime: filter_data["start_createtime"] = start_createtime
    if end_createtime:   filter_data["end_createtime"]   = end_createtime
    if start_modifytime: filter_data["start_modifytime"] = start_modifytime
    if end_modifytime:   filter_data["end_modifytime"]   = end_modifytime
    if start_auditdate:  filter_data["start_auditdate"]  = start_auditdate
    if end_auditdate:    filter_data["end_auditdate"]    = end_auditdate
    if customer_number:  filter_data["customer_number"]  = customer_number

    payload = {
        "data":     filter_data,
        "pageNo":   pageNo,
        "pageSize": pageSize,
    }

    print(f"\n[API] POST {url}")
    print(f"[API] 请求体: {json.dumps(payload, ensure_ascii=False, indent=2)}")

    resp = requests.post(url, headers=headers, json=payload, timeout=_REQUEST_TIMEOUT)
    print(f"[API] HTTP 状态码: {resp.status_code}")
    resp.raise_for_status()
    return resp.json()


# =========================================================
# 工具函数：类型转换
# =========================================================

def _to_dt(val: str):
    """字符串 → datetime，None 安全。支持 'YYYY-MM-DD HH:MM:SS' 及 'YYYY-MM-DD'。"""
    if not val:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(val[:len(fmt)], fmt)
        except (ValueError, TypeError):
            continue
    return None


def _to_date(val: str):
    """字符串 → date，None 安全。"""
    if not val:
        return None
    try:
        return datetime.datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _to_f(val):
    """数值类型转换，兼容 None / str / float。"""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _to_i(val):
    """整型转换，兼容 None / str。"""
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _id(val):
    """金蝶 ID 统一转 str（可能超出 int64 安全范围，部分情况以字符串存储）。"""
    return str(val) if val is not None else None


def _bigint(val):
    """金蝶 ID → Python int，用于 BIGINT 列。"""
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


# =========================================================
# 数据转换：API row → 三张 PG 表的行 dict
# =========================================================

def _header_to_pg(row: dict) -> dict:
    """
    将接口返回的销售订单主表头转换成 PG sm_salorder 行。
    金蝶对象字段命名规则：字段本身返回 ID，".number" / ".name" 返回编码/名称。
    """
    g = row.get

    return {
        # ----- 单据基本标识 -----
        "id":                       _bigint(g("id")),
        "billno":                   g("billno"),
        "billstatus":               g("billstatus"),
        "billstatusname":           g("billstatusname"),
        "closestatus":              g("closestatus"),
        "closedate":                _to_dt(g("closedate")),
        "changestatus":             g("changestatus"),
        "changedate":               _to_dt(g("changedate")),

        # ----- 日期 -----
        "bizdate":                  _to_date(g("bizdate")),
        "auditdate":                _to_dt(g("auditdate")),
        "createtime":               _to_dt(g("createtime")),
        "modifytime":               _to_dt(g("modifytime")),

        # ----- 单据类型 -----
        "billtype":                 _bigint(g("billtype_id")),
        "billtype_number":          g("billtype_number"),
        "billtype_name":            g("billtype_name"),
        "biztype":                  _bigint(g("biztype_id")),
        "biztype_number":           g("biztype_number"),
        "biztype_name":             g("biztype_name"),
        "billcretype":              g("billcretype"),
        "billsource":               g("billsource"),

        # ----- 销售组织 -----
        "org":                      _bigint(g("org_id")),
        "org_number":               g("org_number"),
        "org_name":                 g("org_name"),

        # ----- 客户 -----
        "customer":                 _bigint(g("customer_id")),
        "customer_number":          g("customer_number"),
        "customer_name":            g("customer_name"),

        # ----- 部门 -----
        "dept":                     _bigint(g("dept_id")),
        "dept_number":              g("dept_number"),
        "dept_name":                g("dept_name"),

        # ----- 业务员 -----
        "salesman":                 _bigint(g("salesman_id")),
        "salesman_number":          g("salesman_number"),
        "salesman_name":            g("salesman_name"),

        # ----- 操作人 -----
        "operator":                 _bigint(g("operator_id")),
        "operator_number":          g("operator_number"),
        "operator_name":            g("operator_name"),

        # ----- 创建/修改/审核/变更人 -----
        "creator":                  _bigint(g("creator_id")),
        "creator_number":           g("creator_number"),
        "creator_name":             g("creator_name"),
        "modifier":                 _bigint(g("modifier_id")),
        "modifier_number":          g("modifier_number"),
        "modifier_name":            g("modifier_name"),
        "auditor":                  _bigint(g("auditor_id")),
        "auditor_number":           g("auditor_number"),
        "auditor_name":             g("auditor_name"),
        "changer":                  _bigint(g("changer_id")),
        "changer_number":           g("changer_number"),
        "changer_name":             g("changer_name"),

        # ----- 币别 / 汇率 -----
        "settlecurrency":           _bigint(g("settlecurrency_id")),
        "settlecurrency_number":    g("settlecurrency_number"),
        "settlecurrency_name":      g("settlecurrency_name"),
        "exchangerate":             _to_f(g("exchangerate")),
        "exchangetype":             g("exchangetype"),

        # ----- 价格表 / 收款条件 -----
        "pricelist":                _bigint(g("pricelist_id")),
        "pricelist_number":         g("pricelist_number"),
        "pricelist_name":           g("pricelist_name"),
        "reccondition":             _bigint(g("reccondition_id")),
        "reccondition_number":      g("reccondition_number"),
        "reccondition_name":        g("reccondition_name"),

        # ----- 含税标志 -----
        "istax":                    g("istax"),

        # ----- 金额合计 -----
        "totalamount":              _to_f(g("totalamount")),
        "totaltaxamount":           _to_f(g("totaltaxamount")),
        "totalallamount":           _to_f(g("totalallamount")),
        "prereceiptamount":         _to_f(g("prereceiptamount")),
        "receiptamount":            _to_f(g("receiptamount")),

        # ----- 付款方式 -----
        "paymode":                  g("paymode"),

        # ----- 收货 / 联系人 -----
        "receiveaddress":           g("receiveaddress"),
        "address":                  g("address"),
        "comment":                  g("comment"),
        "deliveryway":              _bigint(g("deliveryway_id")),
        "deliveryway_number":       g("deliveryway_number"),
        "deliveryway_name":         g("deliveryway_name"),
        "deliveraddressf7":         _bigint(g("deliveraddressf7_id")),
        "deliveraddressf7_number":  g("deliveraddressf7_number"),
        "deliveraddressf7_name":    g("deliveraddressf7_name"),
        "linkman":                  g("linkman"),
        "reclinkman":               g("reclinkman"),
    }


def _entry_to_pg(entry: dict, order_id: int) -> dict:
    """
    将单条明细行（billentry 中的一个元素）转换成 PG sm_salorder_entry 行。

    auxpty 结构说明：
      API 返回的 auxpty 是一个对象，key 为弹性域配置名称（中文，如"弹性域名称-辅助资料类型"），
      value 可能是 {id, number, name} 对象 或 纯字符串（"其他类型"弹性域）。
      由于 key 不固定且为中文，不适合拆成独立列，整体以 JSONB 存储。
      auxpty.id（辅助属性组自身的 ID）单独提取到 auxpty_id 列。
    """
    g = entry.get

    # --- auxpty 处理 ---
    auxpty_raw = g("auxpty")
    auxpty_id  = None
    auxpty_json = None
    if isinstance(auxpty_raw, dict):
        auxpty_id   = _bigint(auxpty_raw.get("id"))
        # 保留 id 以外的所有弹性域字段
        auxpty_body = {k: v for k, v in auxpty_raw.items() if k != "id"}
        auxpty_json = json.dumps(auxpty_body, ensure_ascii=False) if auxpty_body else None
    elif auxpty_raw is not None:
        auxpty_json = json.dumps(auxpty_raw, ensure_ascii=False)

    return {
        # ----- 行标识 -----
        "id":                       _bigint(g("id")),
        "order_id":                 order_id,
        "seq":                      _to_i(g("seq")),

        # ----- 物料 -----
        "material":                 _bigint(g("material_id")),
        "material_number":          g("material_masterid_number"),
        "material_name":            g("material_masterid_name"),
        "material_modelnum":        g("material_masterid_modelnum"),
        "materialversion":          _bigint(g("materialversion_id")),
        "materialversion_number":   g("materialversion_number"),
        "materialversion_name":     g("materialversion_name"),

        # ----- 弹性域辅助属性 -----
        "auxpty":                   auxpty_json,    # JSONB（字符串传入，psycopg2 会转 JSONB）
        "auxpty_id":                auxpty_id,

        # ----- 数量 / 库存单位 -----
        "unit":                     _bigint(g("unit_id")),
        "unit_number":              g("unit_number"),
        "unit_name":                g("unit_name"),
        "qty":                      _to_f(g("qty")),

        # ----- 辅助数量 / 辅助单位 -----
        "auxunit":                  _bigint(g("auxunit_id")),
        "auxunit_number":           g("auxunit_number"),
        "auxunit_name":             g("auxunit_name"),
        "auxqty":                   _to_f(g("auxqty")),

        # ----- 基本单位数量 -----
        "baseqty":                  _to_f(g("baseqty")),

        # ----- 价格 -----
        "price":                    _to_f(g("price")),
        "priceandtax":              _to_f(g("priceandtax")),
        "discounttype":             g("discounttype"),
        "discountrate":             _to_f(g("discountrate")),

        # ----- 税率 -----
        "taxrateid":                _bigint(g("taxrateid_id")),
        "taxrateid_number":         g("taxrateid_number"),
        "taxrateid_name":           g("taxrateid_name"),

        # ----- 金额 -----
        "taxamount":                _to_f(g("taxamount")),
        "curtaxamount":             _to_f(g("curtaxamount")),
        "curamount":                _to_f(g("curamount")),
        "amount":                   _to_f(g("amount")),
        "discountamount":           _to_f(g("discountamount")),
        "amountandtax":             _to_f(g("amountandtax")),
        "curamountandtax":          _to_f(g("curamountandtax")),

        # ----- 库存组织 -----
        "e_stockorg":               _bigint(g("e_stockorg_id")),
        "e_stockorg_number":        g("e_stockorg_number"),
        "e_stockorg_name":          g("e_stockorg_name"),

        # ----- 仓库 -----
        "warehouse":                _bigint(g("warehouse_id")),
        "warehouse_number":         g("warehouse_number"),
        "warehouse_name":           g("warehouse_name"),

        # ----- 货位 -----
        "location":                 _bigint(g("location_id")),
        "location_number":          g("location_number"),
        "location_name":            g("location_name"),

        # ----- 货主 -----
        "ownertype":                g("ownertype"),
        "owner":                    _bigint(g("owner_id")),
        "owner_number":             g("owner_number"),
        "owner_name":               g("owner_name"),

        # ----- 结算组织（行级）-----
        "entrysettleorg":           _bigint(g("entrysettleorg_id")),
        "entrysettleorg_number":    g("entrysettleorg_number"),
        "entrysettleorg_name":      g("entrysettleorg_name"),

        # ----- 交货控制 -----
        "deliverydate":             _to_date(g("deliverydate")),
        "iscontrolday":             g("iscontrolday"),
        "deliveradvdays":           _to_i(g("deliveradvdays")),
        "deliverdelaydays":         _to_i(g("deliverdelaydays")),
        "ispresent":                g("ispresent"),
        "iscontrolqty":             g("iscontrolqty"),

        # ----- 交货进度 -----
        "deliveratedown":           _to_f(g("deliveratedown")),
        "deliverateup":             _to_f(g("deliverateup")),
        "deliverqtydown":           _to_f(g("deliverqtydown")),
        "deliverqtyup":             _to_f(g("deliverqtyup")),

        # ----- 批次 -----
        "lotnumber":                g("lotnumber"),

        # ----- 项目 -----
        "project":                  _bigint(g("project_id")),
        "project_number":           g("project_number"),
        "project_name":             g("project_name"),

        # ----- 来源合同 -----
        "conbillnumber":            g("conbillnumber"),
        "conbillrownum":            g("conbillrownum"),

        # ----- 关闭 / 终止状态 -----
        "rowclosestatus":           g("rowclosestatus"),
        "rowterminatestatus":       g("rowterminatestatus"),
    }


def _deliver_to_pg(deliver: dict, entry_id: int, order_id: int, seq: int) -> dict:
    """
    将单条交货计划子行（orderdeliverentry 中的一个元素）转换成
    PG sm_salorder_deliver_entry 行。

    id 处理：若金蝶未返回 id 或为 None，使用 f"{entry_id}_{seq}" 合成唯一键。
    """
    g = deliver.get

    raw_id = g("id")
    row_id = str(raw_id) if raw_id else f"{entry_id}_{seq}"

    return {
        "id":                       row_id,
        "entry_id":                 entry_id,
        "order_id":                 order_id,
        "seq":                      seq,

        # ----- 收货地址 -----
        "d_receiveaddress":         g("d_receiveaddress"),
        "d_receiveaddressf7":       _bigint(g("d_receiveaddressf7_id")),
        "d_receiveaddressf7_number": g("d_receiveaddressf7_number"),
        "d_receiveaddressf7_name":  g("d_receiveaddressf7_name"),

        # ----- 计划交货 -----
        "d_plandate":               _to_date(g("d_plandate")),
        "d_plandeliverydate":       _to_date(g("d_plandeliverydate")),
        "d_transportleadtime":      _to_i(g("d_transportleadtime")),

        # ----- 计划数量 -----
        "d_planqty":                _to_f(g("d_planqty")),
        "d_planbaseqty":            _to_f(g("d_planbaseqty")),

        # ----- 计划单位 -----
        "d_planunit":               _bigint(g("d_planunit_id")),
        "d_planunit_number":        g("d_planunit_number"),
        "d_planunit_name":          g("d_planunit_name"),

        # ----- 备注 -----
        "d_remark":                 g("d_remark"),
    }


def parse_order(row: dict):
    """
    将 API 返回的单条 row 拆分成三元组：
        (header_dict, [entry_dict, ...], [deliver_dict, ...])
    """
    order_id = _bigint(row.get("id"))
    header   = _header_to_pg(row)

    entries   = []
    delivers  = []

    for entry in row.get("billentry", []):
        entry_id = _bigint(entry.get("id"))
        entries.append(_entry_to_pg(entry, order_id))

        for seq, deliver in enumerate(entry.get("orderdeliverentry", []), start=1):
            delivers.append(_deliver_to_pg(deliver, entry_id, order_id, seq))

    return header, entries, delivers


# =========================================================
# PostgreSQL Upsert 工具
# =========================================================

def _build_upsert_sql(table: str, columns: list, conflict_col: str = "id") -> str:
    """
    动态生成 INSERT ... ON CONFLICT (conflict_col) DO UPDATE 语句。
    sync_time 固定使用 NOW()，不从 API 数据中取。
    """
    col_list   = ", ".join(columns)
    val_list   = ", ".join([f"%({c})s" for c in columns])
    update_set = ", ".join(
        [f"{c} = EXCLUDED.{c}" for c in columns if c != conflict_col]
    )
    return f"""
        INSERT INTO {table} ({col_list}, sync_time)
        VALUES ({val_list}, NOW())
        ON CONFLICT ({conflict_col}) DO UPDATE
        SET {update_set},
            sync_time = NOW()
    """


def _upsert_batch(conn, table: str, rows: list[dict], conflict_col: str = "id"):
    """对单张表执行批量 upsert，返回写入行数。"""
    if not rows:
        return 0
    columns = list(rows[0].keys())
    sql     = _build_upsert_sql(table, columns, conflict_col)
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, rows, page_size=500)
    return len(rows)


# =========================================================
# 主同步函数：全量翻页拉取 + 写入 PG（三张表）
# =========================================================

def sync_salorder_to_pg(
    start_bizdate:    str   = None,
    end_bizdate:      str   = None,
    billstatus:       list  = None,
    org_number:       list  = None,
    start_createtime: str   = None,
    end_createtime:   str   = None,
    start_modifytime: str   = None,
    end_modifytime:   str   = None,
    start_auditdate:  str   = None,
    end_auditdate:    str   = None,
    customer_number:  list  = None,
    pageSize:         int   = None,
    max_pages:        int   = None,
    sleep_sec:        float = None,
) -> dict:
    """
    全量翻页拉取销售订单，并将主表、明细行、交货计划分别 upsert 到 PostgreSQL。

    参数：
        start_modifytime / end_modifytime  增量同步时间区间（推荐用于定时任务）
        start_bizdate    / end_bizdate     按订单日期范围同步
        billstatus                         单据状态过滤，如 ["C"]（仅审核）
        max_pages                          最多拉取页数（None = 不限制）
        sleep_sec                          翻页间隔（None = 取 config.SYNC_CONFIG["sleep_sec"]）

    返回：
        {"headers": N, "entries": M, "delivers": K}  各表 upsert 总行数
    """
    if pageSize is None:
        pageSize  = SYNC_CONFIG["page_size"]
    if sleep_sec is None:
        sleep_sec = SYNC_CONFIG["sleep_sec"]

    # 建立 PG 连接
    conn = psycopg2.connect(
        host=PG_CONFIG["host"],
        port=PG_CONFIG["port"],
        dbname=PG_CONFIG["database"],
        user=PG_CONFIG["user"],
        password=PG_CONFIG["password"],
    )
    print(f"[PG] 已连接: {PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['database']}")

    total = {"headers": 0, "entries": 0, "delivers": 0}
    page  = 1

    try:
        while True:
            print(f"\n===== 正在拉取第 {page} 页（每页 {pageSize} 条）=====")
            resp = query_sal_order(
                start_bizdate=start_bizdate,
                end_bizdate=end_bizdate,
                billstatus=billstatus,
                org_number=org_number,
                start_createtime=start_createtime,
                end_createtime=end_createtime,
                start_modifytime=start_modifytime,
                end_modifytime=end_modifytime,
                start_auditdate=start_auditdate,
                end_auditdate=end_auditdate,
                customer_number=customer_number,
                pageNo=page,
                pageSize=pageSize,
            )

            if not resp.get("status"):
                error_code = resp.get("errorCode", "UNKNOWN")
                message    = resp.get("message", "")
                print(f"[错误] 接口返回失败: errorCode={error_code}, message={message}")
                break

            data        = resp.get("data", {})
            rows        = data.get("rows", [])
            total_count = data.get("totalCount", "?")
            is_last     = data.get("lastPage", len(rows) < pageSize)

            # ----- 拆分三张表的数据 -----
            all_headers  = []
            all_entries  = []
            all_delivers = []
            for row in rows:
                h, e_list, d_list = parse_order(row)
                all_headers.append(h)
                all_entries.extend(e_list)
                all_delivers.extend(d_list)

            # ----- 写入 PG（同一事务）-----
            n_h = _upsert_batch(conn, TABLE_HEADER,  all_headers)
            n_e = _upsert_batch(conn, TABLE_ENTRY,   all_entries)
            n_d = _upsert_batch(conn, TABLE_DELIVER, all_delivers)
            conn.commit()

            total["headers"]  += n_h
            total["entries"]  += n_e
            total["delivers"] += n_d

            print(
                f"[PG] 本页: 主表 {n_h} 条 / 明细 {n_e} 条 / 交货计划 {n_d} 条，"
                f"累计: 主表 {total['headers']} / 明细 {total['entries']} / 交货 {total['delivers']}，"
                f"API 总计 {total_count} 条，末页={is_last}"
            )

            if is_last:
                print("[分页] 已到最后一页，停止翻页。")
                break

            if max_pages and page >= max_pages:
                print(f"[分页] 已达到最大页数限制 {max_pages}，停止翻页。")
                break

            page += 1
            time.sleep(sleep_sec)

    except Exception as exc:
        conn.rollback()
        print(f"[错误] 发生异常，已回滚当前页事务: {exc}")
        raise
    finally:
        conn.close()
        print("[PG] 连接已关闭。")

    print(
        f"\n===== 同步完成 =====\n"
        f"  sm_salorder               : {total['headers']:>6} 条\n"
        f"  sm_salorder_entry         : {total['entries']:>6} 条\n"
        f"  sm_salorder_deliver_entry : {total['delivers']:>6} 条"
    )
    return total


# =========================================================
# 主程序入口（示例调用）
# =========================================================

if __name__ == "__main__":
    print("=" * 60)
    print("金蝶销售订单 → PostgreSQL 同步（三表拆分·完整版）")
    print("=" * 60)

    # -------------------------------------------------------
    # 增量同步示例：按最后修改时间区间同步（推荐用于定时任务）
    # -------------------------------------------------------
    # sync_salorder_to_pg(
    #     start_modifytime="2024-06-01 00:00:00",
    #     end_modifytime="2024-06-30 23:59:59",
    #     billstatus=["C"],   # 仅同步已审核单据
    # )

    # -------------------------------------------------------
    # 全量同步示例：拉取所有状态销售订单
    # -------------------------------------------------------
    result = sync_salorder_to_pg(
        billstatus=["A", "B", "C"],   # A=保存 B=提交 C=审核
        pageSize=100,
    )
    print(f"\n本次同步结果: {result}")
