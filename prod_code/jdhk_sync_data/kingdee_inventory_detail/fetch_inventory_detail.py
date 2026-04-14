"""
fetch_inventory_detail.py
=========================
职责：Token 管理 + 调用金蝶即时库存明细接口（/v2/im/getInventoryDetail）
      返回接口原始数据，不做任何字段转换，不涉及数据库。

对外暴露：
    get_valid_token()         → str         获取有效 access_token
    query_inventory_detail()  → dict        单页查询，返回接口原始 JSON
    fetch_all_pages()         → list[dict]  自动翻页，返回全部原始 rows

依赖：config.py（OPENAPI_CONFIG / SYNC_CONFIG / API_PATHS）

注意：此文件 **不需要** 因为增减字段而修改。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
import datetime
import time

from config import OPENAPI_CONFIG, SYNC_CONFIG, API_PATHS

# ---------- 配置快捷引用 ----------
_BASE_URL         = OPENAPI_CONFIG["base_url"]
_TOKEN_PATH       = OPENAPI_CONFIG["token_path"]
_X_ACGW_IDENTITY  = OPENAPI_CONFIG["x_acgw_identity"]
_TOKEN_CACHE_FILE = OPENAPI_CONFIG["token_cache_file"]
_INVENTORY_PATH   = API_PATHS["inventory_detail"]
_REQUEST_TIMEOUT  = SYNC_CONFIG["request_timeout"]


# =========================================================
# Token 管理
# =========================================================

def _fetch_new_token() -> dict:
    """向金蝶认证接口申请新 Token，写入缓存文件，返回 {access_token, expire_at}。"""
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
        "timestamp":     str(int(time.time() * 1000)),
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=_REQUEST_TIMEOUT)
    print(f"[Token] HTTP {resp.status_code}")
    resp.raise_for_status()

    resp_json    = resp.json()
    inner        = resp_json.get("data") or {}
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
    """
    优先读取缓存 Token；不存在或已过期时重新申请。
    返回有效的 access_token 字符串。
    """
    if os.path.exists(_TOKEN_CACHE_FILE):
        try:
            with open(_TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
            expire_at = datetime.datetime.fromisoformat(cache["expire_at"])
            if datetime.datetime.now() < expire_at:
                print(f"[Token] 使用缓存 Token，有效至: {expire_at}")
                return cache["access_token"]
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
    """
    调用金蝶即时库存明细接口（单页），返回接口原始 JSON dict。
    文档: https://vip.kingdee.com/knowledge/728252231845369856
    """
    if pageSize is None:
        pageSize = SYNC_CONFIG["page_size"]

    url     = f"{_BASE_URL}{_INVENTORY_PATH}"
    headers = {
        "Content-Type":    "application/json",
        "access_token":    get_valid_token(),
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

    payload = {"params": filter_params, "pageNo": pageNo, "pageSize": pageSize}

    print(f"\n[API] POST {url}")
    print(f"[API] 请求体: {json.dumps(payload, ensure_ascii=False, indent=2)}")

    resp = requests.post(url, headers=headers, json=payload, timeout=_REQUEST_TIMEOUT)
    print(f"[API] HTTP 状态码: {resp.status_code}")
    resp.raise_for_status()
    return resp.json()


# =========================================================
# 自动翻页拉取（返回全部原始 rows）
# =========================================================

def fetch_all_pages(
    modifytime_start: str   = None,
    modifytime_end:   str   = None,
    material_number:  str   = None,
    warehouse_number: str   = None,
    org:              str   = None,
    org_number:       str   = None,
    lot_number:       str   = None,
    pageSize:         int   = None,
    max_pages:        int   = None,
    sleep_sec:        float = None,
) -> list:
    """
    自动翻页，拉取即时库存明细全部数据。

    返回：list[dict] — 接口原始 rows，未经任何字段转换。
    """
    if pageSize  is None: pageSize  = SYNC_CONFIG["page_size"]
    if sleep_sec is None: sleep_sec = SYNC_CONFIG["sleep_sec"]

    all_rows = []
    page     = 1

    while True:
        print(f"\n===== [API] 第 {page} 页（每页 {pageSize} 条）=====")
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
            print(f"[API 错误] errorCode={error_code}, message={message}")
            break

        data        = resp.get("data", {})
        rows        = data.get("rows", [])
        total_count = data.get("totalCount", "?")
        is_last     = data.get("lastPage", True)

        all_rows.extend(rows)
        print(f"[API] 本页 {len(rows)} 条，累计 {len(all_rows)} 条，接口总记录数 {total_count}，末页={is_last}")

        if is_last:
            print("[API] 已到最后一页，停止翻页。")
            break

        if max_pages and page >= max_pages:
            print(f"[API] 已达最大页数限制 {max_pages}，停止翻页。")
            break

        page += 1
        time.sleep(sleep_sec)

    print(f"[API] 拉取完成，共 {len(all_rows)} 条原始记录。")
    return all_rows


# =========================================================
# 独立测试（直接运行此文件时）
# =========================================================

if __name__ == "__main__":
    print("=" * 60)
    print("【fetch_inventory_detail.py 独立测试 — 只查询不落库】")
    print("=" * 60)
    result = query_inventory_detail(org="00", pageNo=1, pageSize=5)
    print(json.dumps(result, ensure_ascii=False, indent=2))
