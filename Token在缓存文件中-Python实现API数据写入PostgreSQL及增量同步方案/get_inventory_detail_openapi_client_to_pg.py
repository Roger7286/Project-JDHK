import requests
import json
import datetime
import os
import time

import psycopg2
import psycopg2.extras

from config import OPENAPI_CONFIG, SYNC_CONFIG, API_PATHS, PG_CONFIG

# =========================================================
# 金蝶 OpenAPI - 即时库存明细查询 → 写入 PostgreSQL
# 接口地址: /v2/im/getInventoryDetail
# 文档:     https://vip.kingdee.com/knowledge/728252231845369856
#
# 写入策略: INSERT ... ON CONFLICT (id) DO UPDATE（按主键 upsert）
# 配置:     统一读取 config.py（OPENAPI_CONFIG / SYNC_CONFIG / PG_CONFIG）
# Token:    优先读 kingdee_token_cache.json，过期才重新申请
# =========================================================

# ---------- 常用配置快捷引用 ----------
_BASE_URL         = OPENAPI_CONFIG["base_url"]
_TOKEN_PATH       = OPENAPI_CONFIG["token_path"]
_X_ACGW_IDENTITY  = OPENAPI_CONFIG["x_acgw_identity"]
_TOKEN_CACHE_FILE = OPENAPI_CONFIG["token_cache_file"]
_INVENTORY_PATH   = API_PATHS["inventory_detail"]
_REQUEST_TIMEOUT  = SYNC_CONFIG["request_timeout"]

# ---------- 目标表名 ----------
TARGET_TABLE = "kingdee_inventory_detail"


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
# 即时库存明细查询（单页）
# =========================================================

def query_inventory_detail(
    modifytime_start: str = None,
    modifytime_end:   str = None,
    material:         int = None,
    material_number:  str = None,
    warehouse:        int = None,
    warehouse_number: str = None,
    org:              str = None,
    org_number:       str = None,
    lot:              int = None,
    lot_number:       str = None,
    pageNo:           int = 1,
    pageSize:         int = None,
) -> dict:
    """调用金蝶即时库存明细查询接口（单页），返回原始 JSON dict。"""
    if pageSize is None:
        pageSize = SYNC_CONFIG["page_size"]

    access_token = get_valid_token()
    url = f"{_BASE_URL}{_INVENTORY_PATH}"
    headers = {
        "Content-Type":    "application/json",
        "access_token":    access_token,
        "x-acgw-identity": _X_ACGW_IDENTITY,
    }

    filter_params: dict = {}
    if modifytime_start:  filter_params["modifytime_start"]  = modifytime_start
    if modifytime_end:    filter_params["modifytime_end"]    = modifytime_end
    if material:          filter_params["material"]          = material
    if material_number:   filter_params["material_number"]   = material_number
    if warehouse:         filter_params["warehouse"]         = warehouse
    if warehouse_number:  filter_params["warehouse_number"]  = warehouse_number
    if org:               filter_params["org"]               = org
    if org_number:        filter_params["org_number"]        = org_number
    if lot:               filter_params["lot"]               = lot
    if lot_number:        filter_params["lot_number"]        = lot_number

    payload = {
        "params":   filter_params,
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
# 数据转换：API row → PG 行 dict
# JSON 字段中的 "." 替换为 "_"，与建表语句字段名对应
# =========================================================

def _row_to_pg(row: dict) -> dict:
    """
    将接口返回的单条 row 转换成与 PG 表列名完全对应的 dict。
    字段映射规则：JSON key 中的 '.' → '_'（例如 org.name → org_name）
    """
    def _get(key, default=None):
        return row.get(key, default)

    def _to_dt(val):
        """字符串 → datetime，None 安全。"""
        if not val:
            return None
        try:
            return datetime.datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                return datetime.datetime.strptime(val, "%Y-%m-%d")
            except ValueError:
                return None

    def _to_date(val):
        """字符串 → date，None 安全。"""
        if not val:
            return None
        try:
            return datetime.datetime.strptime(val[:10], "%Y-%m-%d").date()
        except ValueError:
            return None

    return {
        "id":                   str(_get("id")),
        # 组织
        "org":                  _get("org"),
        "org_number":           _get("org.number"),
        "org_name":             _get("org.name"),
        # 物料
        "material":             _get("material"),
        "material_number":      _get("material.number"),
        "material_name":        _get("material.name"),
        "material_modelnum":    _get("material.modelnum"),
        "material_helpcode":    _get("material.helpcode"),
        # 辅助属性 / 批次
        "auxpty":               _get("auxpty"),
        "lotnum":               _get("lotnum"),
        "producedate":          _to_date(_get("producedate")),
        "expirydate":           _to_date(_get("expirydate")),
        # 库存单位
        "unit":                 _get("unit"),
        "unit_number":          _get("unit.number"),
        "unit_name":            _get("unit.name"),
        "qty":                  _get("qty"),
        # 基本单位
        "baseunit":             _get("baseunit"),
        "baseunit_number":      _get("baseunit.number"),
        "baseunit_name":        _get("baseunit.name"),
        "baseqty":              _get("baseqty"),
        # 第二计量单位
        "unit2nd":              _get("unit2nd"),
        "unit2nd_number":       _get("unit2nd.number"),
        "unit2nd_name":         _get("unit2nd.name"),
        "qty2nd":               _get("qty2nd"),
        # 第三计量单位
        "unit3rd":              _get("unit3rd"),
        "unit3rd_number":       _get("unit3rd.number"),
        "unit3rd_name":         _get("unit3rd.name"),
        "qty3rd":               _get("qty3rd"),
        # 仓库
        "warehouse":            _get("warehouse"),
        "warehouse_number":     _get("warehouse.number"),
        "warehouse_name":       _get("warehouse.name"),
        # 货位
        "location":             _get("location"),
        "location_number":      _get("location.number"),
        "location_name":        _get("location.name"),
        # 库存状态
        "invstatus":            _get("invstatus"),
        "invstatus_number":     _get("invstatus.number"),
        "invstatus_name":       _get("invstatus.name"),
        # 库存类型
        "invtype":              _get("invtype"),
        "invtype_number":       _get("invtype.number"),
        "invtype_name":         _get("invtype.name"),
        # 货主
        "ownertype":            _get("ownertype"),
        "owner":                _get("owner"),
        "owner_number":         _get("owner.number"),
        "owner_name":           _get("owner.name"),
        # 保管方
        "keepertype":           _get("keepertype"),
        "keeper":               _get("keeper"),
        "keeper_number":        _get("keeper.number"),
        "keeper_name":          _get("keeper.name"),
        # 跟踪号
        "tracknumber":          _get("tracknumber"),
        "tracknumber_number":   _get("tracknumber.number"),
        "tracknumber_name":     _get("tracknumber.name"),
        # 配置码
        "configuredcode":       _get("configuredcode"),
        "configuredcode_number": _get("configuredcode.number"),
        "configuredcode_name":  _get("configuredcode.name"),
        # 项目
        "project":              _get("project"),
        "project_number":       _get("project.number"),
        "project_name":         _get("project.name"),
        # 版本
        "mversion":             _get("mversion"),
        "mversion_number":      _get("mversion.number"),
        "mversion_name":        _get("mversion.name"),
        # 可用数量
        "avbbaseqty":           _get("avbbaseqty"),
        "avbqty":               _get("avbqty"),
        "avbqty2nd":            _get("avbqty2nd"),
        "avbqty3rd":            _get("avbqty3rd"),
        # 锁定/预留数量
        "baseqty_lock":         _get("baseqty_lock"),
        "qty_lock":             _get("qty_lock"),
        "qty2nd_lock":          _get("qty2nd_lock"),
        "qty3rd_lock":          _get("qty3rd_lock"),
        "lockbaseqty":          _get("lockbaseqty"),
        "lockqty":              _get("lockqty"),
        "lockqty2nd":           _get("lockqty2nd"),
        "lockqty3rd":           _get("lockqty3rd"),
        # 修改时间
        "modifytime":           _to_dt(_get("modifytime")),
    }


# =========================================================
# PostgreSQL Upsert（按主键 id 更新全部字段）
# =========================================================

def _build_upsert_sql(columns: list) -> str:
    """
    动态生成 INSERT ... ON CONFLICT (id) DO UPDATE 语句。
    sync_time 固定使用 NOW()，不从 API 数据中取。
    """
    col_list   = ", ".join(columns)
    val_list   = ", ".join([f"%({c})s" for c in columns])
    update_set = ", ".join(
        [f"{c} = EXCLUDED.{c}" for c in columns if c != "id"]
    )
    sql = f"""
        INSERT INTO {TARGET_TABLE} ({col_list}, sync_time)
        VALUES ({val_list}, NOW())
        ON CONFLICT (id) DO UPDATE
        SET {update_set},
            sync_time = NOW()
    """
    return sql


def upsert_rows(conn, rows: list[dict]) -> int:
    """
    将 rows 列表批量 upsert 到 PG 表。
    返回实际写入行数。
    """
    if not rows:
        return 0

    pg_rows = [_row_to_pg(r) for r in rows]
    columns = list(pg_rows[0].keys())
    sql     = _build_upsert_sql(columns)

    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, pg_rows, page_size=500)
    conn.commit()
    return len(pg_rows)


# =========================================================
# 主同步函数：全量翻页拉取 + 写入 PG
# =========================================================

def sync_inventory_to_pg(
    modifytime_start: str = None,
    modifytime_end:   str = None,
    material_number:  str = None,
    warehouse_number: str = None,
    org:              str = None,
    org_number:       str = None,
    lot_number:       str = None,
    pageSize:         int = None,
    max_pages:        int = None,
    sleep_sec:        float = None,
) -> int:
    """
    全量翻页拉取即时库存明细，并按主键 id upsert 到 PostgreSQL。

    参数：
        modifytime_start / end  增量同步时间区间，格式 '2024-06-01 00:00:00'
        org / org_number        组织过滤
        max_pages               最多拉取页数（None = 不限制）
        sleep_sec               翻页间隔（None = 取 config.SYNC_CONFIG["sleep_sec"]）

    返回：
        总写入/更新行数
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

    total_upserted = 0
    page = 1

    try:
        while True:
            print(f"\n===== 正在拉取第 {page} 页（每页 {pageSize} 条）=====")
            resp = query_inventory_detail(
                modifytime_start=modifytime_start,
                modifytime_end=modifytime_end,
                material_number=material_number,
                warehouse_number=warehouse_number,
                org=org,
                org_number=org_number,
                lot_number=lot_number,
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
            is_last     = data.get("lastPage", True)

            # 写入 PG
            upserted = upsert_rows(conn, rows)
            total_upserted += upserted
            print(f"[PG] 本页 upsert {upserted} 条，累计 {total_upserted} 条，API 总计 {total_count} 条，末页={is_last}")

            if is_last:
                print("[分页] 已到最后一页，停止翻页。")
                break

            if max_pages and page >= max_pages:
                print(f"[分页] 已达到最大页数限制 {max_pages}，停止翻页。")
                break

            page += 1
            time.sleep(sleep_sec)

    finally:
        conn.close()
        print("[PG] 连接已关闭。")

    print(f"\n===== 同步完成，共 upsert {total_upserted} 条即时库存明细记录 =====")
    return total_upserted


# =========================================================
# 主程序入口（示例调用）
# =========================================================

if __name__ == "__main__":
    print("=" * 60)
    print("金蝶即时库存明细 → PostgreSQL 同步")
    print("=" * 60)

    # -------------------------------------------------------
    # 增量同步示例：按修改时间区间同步
    # -------------------------------------------------------
    # sync_inventory_to_pg(
    #     modifytime_start="2024-06-01 00:00:00",
    #     modifytime_end="2024-06-30 23:59:59",
    # )

    # -------------------------------------------------------
    # 全量同步示例：按组织拉取全部数据
    # -------------------------------------------------------
    total = sync_inventory_to_pg(
        org="00",       # 组织编码，按实际填写
        pageSize=100,
    )
    print(f"\n本次共同步 {total} 条记录到 PostgreSQL。")
