import requests
import json
import datetime
import os
import time

from config import OPENAPI_CONFIG, SYNC_CONFIG, API_PATHS

# =========================================================
# 金蝶 OpenAPI - 即时库存明细查询
# 接口地址: /v2/im/getInventoryDetail
# 文档: https://vip.kingdee.com/knowledge/728252231845369856
#
# 配置统一读取自 config.py（OPENAPI_CONFIG / SYNC_CONFIG）
# Token 优先从 kingdee_token_cache.json 缓存文件读取，
# 过期或不存在时自动重新申请并写回缓存，避免重复刷新。
# =========================================================

# 从集中配置中取出常用字段，方便后续引用
_BASE_URL          = OPENAPI_CONFIG["base_url"]
_TOKEN_PATH        = OPENAPI_CONFIG["token_path"]
_X_ACGW_IDENTITY   = OPENAPI_CONFIG["x_acgw_identity"]
_TOKEN_CACHE_FILE  = OPENAPI_CONFIG["token_cache_file"]
_INVENTORY_PATH    = API_PATHS["inventory_detail"]
_REQUEST_TIMEOUT   = SYNC_CONFIG["request_timeout"]


# =========================================================
# Token 管理（从缓存文件读取，过期则重新获取）
# =========================================================

def _fetch_new_token() -> dict:
    """向金蝶认证接口申请新 Token，写入缓存文件，返回含 access_token 和 expire_at 的字典。"""
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
    # 接口返回结构: {"status": true, "data": {"access_token": "...", "expires_in": ...}}
    inner = resp_json.get("data", {})
    access_token = inner.get("access_token")
    if not access_token:
        raise ValueError(
            f"未在响应中找到 access_token，完整返回: {json.dumps(resp_json, ensure_ascii=False)}"
        )

    # expires_in 为毫秒时值远大于 86400，统一转换为秒；默认 7200 秒
    raw_expires = inner.get("expires_in", 7200 * 1000)
    expire_in   = int(raw_expires / 1000) if raw_expires > 86400 else int(raw_expires)
    # 提前 300 秒过期，留出刷新余量
    expire_at   = (datetime.datetime.now() + datetime.timedelta(seconds=expire_in - 300)).isoformat()

    token_cache = {"access_token": access_token, "expire_at": expire_at}
    with open(_TOKEN_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(token_cache, f, ensure_ascii=False, indent=2)
    print(f"[Token] 新 Token 已缓存，有效至: {expire_at}")
    return token_cache


def get_valid_token() -> str:
    """
    优先从 kingdee_token_cache.json 读取 Token。
    Token 不存在或已过期时，自动重新申请并更新缓存。
    """
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
    org:              int = None,
    org_number:       str = None,
    lot:              int = None,
    lot_number:       str = None,
    pageNo:           int = 1,
    pageSize:         int = None,   # None 时取 SYNC_CONFIG["page_size"]
) -> dict:
    """
    调用金蝶即时库存明细查询接口（单页）。

    参数说明：
        modifytime_start  记录修改开始时间，格式 '2024-06-25 00:00:00'
        modifytime_end    记录修改结束时间，格式 '2024-06-28 23:59:59'
        material          物料 ID（Long）
        material_number   物料编码
        warehouse         仓库 ID（Long）
        warehouse_number  仓库编码
        org               组织 ID（Long）
        org_number        组织编码
        lot               批次 ID（Long）
        lot_number        批次编码
        pageNo            页码，默认 1
        pageSize          每页条数，默认取 config.SYNC_CONFIG["page_size"]，最大 1000

    返回：
        接口原始 JSON 响应（dict）
    """
    if pageSize is None:
        pageSize = SYNC_CONFIG["page_size"]

    access_token = get_valid_token()

    url = f"{_BASE_URL}{_INVENTORY_PATH}"
    # Headers：access_token + x-acgw-identity 缺一不可
    headers = {
        "Content-Type":    "application/json",
        "access_token":    access_token,
        "x-acgw-identity": _X_ACGW_IDENTITY,
    }

    # 过滤条件放入 params 子对象，仅传入非 None 的字段
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
# 即时库存明细查询（自动翻页，拉取全部数据）
# =========================================================

def query_all_pages(
    modifytime_start: str = None,
    modifytime_end:   str = None,
    material_number:  str = None,
    warehouse_number: str = None,
    org_number:       str = None,
    lot_number:       str = None,
    pageSize:         int = None,   # None 时取 SYNC_CONFIG["page_size"]
    max_pages:        int = None,
    sleep_sec:        float = None, # None 时取 SYNC_CONFIG["sleep_sec"]
) -> list:
    """
    自动翻页，拉取所有即时库存明细记录。

    参数：
        max_pages   最多拉取页数（None 表示不限制）
        sleep_sec   每页请求间隔秒数，防止接口限流；None 时取 config.SYNC_CONFIG["sleep_sec"]

    返回：
        所有页 rows 合并后的列表
    """
    if pageSize is None:
        pageSize = SYNC_CONFIG["page_size"]
    if sleep_sec is None:
        sleep_sec = SYNC_CONFIG["sleep_sec"]

    all_rows = []
    page = 1

    while True:
        print(f"\n===== 正在拉取第 {page} 页（每页 {pageSize} 条）=====")
        resp = query_inventory_detail(
            modifytime_start=modifytime_start,
            modifytime_end=modifytime_end,
            material_number=material_number,
            warehouse_number=warehouse_number,
            org_number=org_number,
            lot_number=lot_number,
            pageNo=page,
            pageSize=pageSize,
        )

        # 检查接口返回状态
        if not resp.get("status"):
            error_code = resp.get("errorCode", "UNKNOWN")
            message    = resp.get("message", "")
            print(f"[错误] 接口返回失败: errorCode={error_code}, message={message}")
            break

        data     = resp.get("data", {})
        rows     = data.get("rows", [])
        all_rows.extend(rows)

        total_count = data.get("totalCount", "?")
        is_last     = data.get("lastPage", True)

        print(f"[分页] 本页获取 {len(rows)} 条，累计 {len(all_rows)} 条，总计 {total_count} 条，末页={is_last}")

        if is_last:
            print("[分页] 已到最后一页，停止翻页。")
            break

        if max_pages and page >= max_pages:
            print(f"[分页] 已达到最大页数限制 {max_pages}，停止翻页。")
            break

        page += 1
        time.sleep(sleep_sec)

    print(f"\n===== 共获取 {len(all_rows)} 条即时库存明细记录 =====")
    return all_rows


# =========================================================
# 主程序入口（示例调用）
# =========================================================

if __name__ == "__main__":
    # -------------------------------------------------------
    # 示例 1：单页查询
    # -------------------------------------------------------
    print("=" * 60)
    print("示例 1：单页查询")
    print("=" * 60)

    result = query_inventory_detail(
        # modifytime_start="2024-06-25 00:00:00",
        # modifytime_end="2024-06-28 23:59:59",
        org="00",   # 组织编码，按实际填写
        pageNo=1,
        pageSize=10,
    )

    print("\n[响应] 完整返回值:")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 解析关键字段
    if result.get("status"):
        data = result.get("data", {})
        print(f"\n[解析] 总记录数: {data.get('totalCount')}")
        print(f"[解析] 当前页: {data.get('pageNo')}")
        print(f"[解析] 是否末页: {data.get('lastPage')}")
        rows = data.get("rows", [])
        print(f"[解析] 本页记录数: {len(rows)}")
        if rows:
            print("[解析] 第一条记录示例:")
            print(json.dumps(rows[0], ensure_ascii=False, indent=2))
    else:
        print(f"[失败] errorCode={result.get('errorCode')}, message={result.get('message')}")

    # -------------------------------------------------------
    # 示例 2：全量翻页查询（取消注释以运行）
    # -------------------------------------------------------
    # print("\n" + "=" * 60)
    # print("示例 2：全量翻页查询")
    # print("=" * 60)
    # all_records = query_all_pages(
    #     modifytime_start="2024-06-01 00:00:00",
    #     modifytime_end="2024-06-30 23:59:59",
    #     org_number="00",
    # )
    # print(f"\n共获取 {len(all_records)} 条记录")
