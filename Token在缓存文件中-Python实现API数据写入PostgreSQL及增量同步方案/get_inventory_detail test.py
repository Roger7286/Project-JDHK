import requests
import json
import datetime
import os
import time

# =========================================================
# 金蝶 OpenAPI - 即时库存明细查询
# 接口地址: /v2/im/getInventoryDetail
# 文档: https://vip.kingdee.com/knowledge/728252231845369856
# =========================================================

# ===== API 基础配置（与 get_access_token.py 保持一致）=====
ACCOUNT_ID        = "2438647909676230656"
CLIENT_ID         = "AWS"
X_ACGW_IDENTITY   = "djF8MTlkNDgwNzRmMWMwMDExNjhmMDF8NDkyODYyOTkzMjAyNny-EPmorbbR5vPU9Nda3rQ0Cv4cZF01PXmksYq4ELxjYHw="
USERNAME          = "AWS"
CLIENT_SECRET     = "Happy1234567890!"
BASE_URL          = "https://hkprod.test.kdsuite.ai"
TOKEN_PATH        = "/kapi/oauth2/getToken"
LANGUAGE          = "zh_CN"

# Token 缓存文件（与同目录下其他脚本共享）
TOKEN_CACHE_FILE  = os.path.join(os.path.dirname(__file__), "kingdee_token_cache_test.json")

# 即时库存明细查询接口路径
INVENTORY_DETAIL_PATH = "/kapi/v2/im/getInventoryDetail"


# =========================================================
# Token 管理（从缓存文件读取，过期则重新获取）
# =========================================================

def _fetch_new_token() -> dict:
    """向金蝶认证接口申请新 Token，返回含 access_token 和 expire_at 的字典。"""
    url = f"{BASE_URL}{TOKEN_PATH}"
    headers = {
        "Content-Type": "application/json",
        "x-acgw-identity": X_ACGW_IDENTITY,
    }
    payload = {
        "accountId":    ACCOUNT_ID,
        "client_id":    CLIENT_ID,
        "username":     USERNAME,
        "client_secret": CLIENT_SECRET,
        "language":     LANGUAGE,
        "nonce":        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp":    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    print(f"[Token] HTTP {resp.status_code}")
    resp.raise_for_status()

    resp_json = resp.json()
    # 接口返回结构: {"status": true, "data": {"access_token": "...", "expires_in": ...}}
    inner = resp_json.get("data") or {}
    access_token = inner.get("access_token")
    if not access_token:
        raise ValueError(f"未在响应中找到 access_token，完整返回: {json.dumps(resp_json, ensure_ascii=False)}")

    # 缓存有效期：优先取接口返回的 expires_in（毫秒），否则默认 7200 秒
    raw_expires = inner.get("expires_in", 7200 * 1000)
    # expires_in 为毫秒级时值会远大于 86400，转换为秒
    expire_in = int(raw_expires / 1000) if raw_expires > 86400 else int(raw_expires)
    expire_at = (datetime.datetime.now() + datetime.timedelta(seconds=expire_in - 300)).isoformat()

    token_cache = {"access_token": access_token, "expire_at": expire_at}
    with open(TOKEN_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(token_cache, f, ensure_ascii=False, indent=2)
    print(f"[Token] 新 Token 已缓存，有效至: {expire_at}")
    return token_cache


def get_valid_token() -> str:
    """优先从缓存文件读取 Token；Token 不存在或过期时重新获取。"""
    if os.path.exists(TOKEN_CACHE_FILE):
        try:
            with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
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
# 即时库存明细查询
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
    pageNo:        int = 1,
    pageSize:         int = 100,
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
        pageNo         页码，默认 1
        pageSize          每页条数，默认 100，最大 1000

    返回：
        接口原始 JSON 响应（dict）
    """
    access_token = get_valid_token()

    url = f"{BASE_URL}{INVENTORY_DETAIL_PATH}"
    # Headers 与 API Fox 跑通时完全一致：access_token + x-acgw-identity 缺一不可
    headers = {
        "Content-Type":    "application/json",
        "access_token":    access_token,
        "x-acgw-identity": X_ACGW_IDENTITY,
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

    # 请求体结构: {"params": {...过滤条件...}, "pageNo": N, "pageSize": N}
    payload = {
        "params":  filter_params,
        "pageNo":  pageNo,
        "pageSize": pageSize,
    }

    print(f"\n[API] POST {url}")
    print(f"[API] 请求体: {json.dumps(payload, ensure_ascii=False, indent=2)}")

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    print(f"[API] HTTP 状态码: {resp.status_code}")
    resp.raise_for_status()

    result = resp.json()
    return result


def query_all_pages(
    modifytime_start: str = None,
    modifytime_end:   str = None,
    material_number:  str = None,
    warehouse_number: str = None,
    org_number:       str = None,
    lot_number:       str = None,
    pageSize:         int = 100,
    max_pages:        int = None,
    sleep_sec:        float = 0.3,
) -> list:
    """
    自动翻页，拉取所有即时库存明细记录。

    参数：
        max_pages   最多拉取页数（None 表示不限制）
        sleep_sec   每页请求间隔秒数，防止接口限流

    返回：
        所有页的 rows 合并后的列表
    """
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

        data  = resp.get("data", {})
        rows  = data.get("rows", [])
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
    # 示例 1：单页查询（按修改时间段 + 组织编码过滤）
    # -------------------------------------------------------
    print("=" * 60)
    print("示例 1：单页查询")
    print("=" * 60)

    result = query_inventory_detail(
        #modifytime_start="2024-06-25 00:00:00",
        #modifytime_end="2024-06-28 23:59:59",
        org="3200614",        # 组织编码，按实际填写
        pageNo=1,
        pageSize=100,
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
            print(f"[解析] 第一条记录示例:")
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
    #     pageSize=100,
    # )
    # print(f"\n共获取 {len(all_records)} 条记录")
