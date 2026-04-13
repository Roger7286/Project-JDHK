"""
fetch_purreceivebill.py
=======================
职责：Token 管理（复用）+ 调用金蝶苍穹采购收料单查询接口
      （/v2/im/im_purreceivebill/query）
      返回接口原始数据，不做任何字段转换，不涉及数据库。

对外暴露：
    get_valid_token()        → str         获取有效 access_token（与库存明细共用同一逻辑）
    query_purreceivebill()   → dict        单页查询，返回接口原始 JSON
    fetch_all_pages()        → list[dict]  自动翻页，返回全部原始 bills（含 entry 明细）

依赖：config.py（OPENAPI_CONFIG / SYNC_CONFIG / API_PATHS）

注意：此文件 **不需要** 因为增减字段而修改。
      增减字段只需修改 load_purreceivebill_to_pg.py。
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
_BASE_URL             = OPENAPI_CONFIG["base_url"]
_TOKEN_PATH           = OPENAPI_CONFIG["token_path"]
_X_ACGW_IDENTITY      = OPENAPI_CONFIG["x_acgw_identity"]
_TOKEN_CACHE_FILE     = OPENAPI_CONFIG["token_cache_file"]
_PUR_RECEIVE_PATH     = API_PATHS["purreceivebill"]   # "/v2/im/im_purreceivebill/query"
_REQUEST_TIMEOUT      = SYNC_CONFIG["request_timeout"]


# =========================================================
# Token 管理（与 fetch_inventory_detail.py 逻辑完全一致）
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
# 采购收料单查询（单页）
# =========================================================

def query_purreceivebill(
    billno:             str   = None,   # 单据编号（精确）
    billno_like:        str   = None,   # 单据编号（模糊）
    billstatus:         str   = None,   # 单据状态：1=暂存 2=已提交 3=已审核 4=已关闭
    org_number:         str   = None,   # 业务组织编号
    supplier_number:    str   = None,   # 供应商编号
    material_number:    str   = None,   # 物料编号（明细行过滤）
    warehouse_number:   str   = None,   # 仓库编号
    date_start:         str   = None,   # 单据日期起（含）格式 "2024-06-01"
    date_end:           str   = None,   # 单据日期止（含）格式 "2024-06-30"
    modifytime_start:   str   = None,   # 修改时间起 格式 "2024-06-01 00:00:00"
    modifytime_end:     str   = None,   # 修改时间止 格式 "2024-06-30 23:59:59"
    pageNo:             int   = 1,
    pageSize:           int   = None,
) -> dict:
    """
    调用金蝶苍穹采购收料单查询接口（单页），返回接口原始 JSON dict。
    接口路径: /v2/im/im_purreceivebill/query
    """
    if pageSize is None:
        pageSize = SYNC_CONFIG["page_size"]

    url     = f"{_BASE_URL}{_PUR_RECEIVE_PATH}"
    headers = {
        "Content-Type":    "application/json",
        "access_token":    get_valid_token(),
        "x-acgw-identity": _X_ACGW_IDENTITY,
    }

    filter_params: dict = {}
    if billno:              filter_params["billno"]           = billno
    if billno_like:         filter_params["billno_like"]      = billno_like
    if billstatus:          filter_params["billstatus"]       = billstatus
    if org_number:          filter_params["org_number"]       = org_number
    if supplier_number:     filter_params["supplier_number"]  = supplier_number
    if material_number:     filter_params["material_number"]  = material_number
    if warehouse_number:    filter_params["warehouse_number"] = warehouse_number
    if date_start:          filter_params["date_start"]       = date_start
    if date_end:            filter_params["date_end"]         = date_end
    if modifytime_start:    filter_params["modifytime_start"] = modifytime_start
    if modifytime_end:      filter_params["modifytime_end"]   = modifytime_end

    payload = {"params": filter_params, "pageNo": pageNo, "pageSize": pageSize}

    print(f"\n[API] POST {url}")
    print(f"[API] 请求体: {json.dumps(payload, ensure_ascii=False, indent=2)}")

    resp = requests.post(url, headers=headers, json=payload, timeout=_REQUEST_TIMEOUT)
    print(f"[API] HTTP 状态码: {resp.status_code}")
    resp.raise_for_status()
    return resp.json()


# =========================================================
# 自动翻页拉取（返回全部原始 bills）
# =========================================================

def fetch_all_pages(
    billstatus:         str   = None,
    org_number:         str   = None,
    supplier_number:    str   = None,
    material_number:    str   = None,
    warehouse_number:   str   = None,
    date_start:         str   = None,
    date_end:           str   = None,
    modifytime_start:   str   = None,
    modifytime_end:     str   = None,
    pageSize:           int   = None,
    max_pages:          int   = None,
    sleep_sec:          float = None,
) -> list:
    """
    自动翻页，拉取采购收料单全部数据。

    返回：list[dict] — 接口原始 bills（每条 bill 内含 entry 明细列表），
                        未经任何字段转换。
    """
    if pageSize  is None: pageSize  = SYNC_CONFIG["page_size"]
    if sleep_sec is None: sleep_sec = SYNC_CONFIG["sleep_sec"]

    all_bills = []
    page      = 1

    while True:
        print(f"\n===== [API] 第 {page} 页（每页 {pageSize} 条）=====")
        resp = query_purreceivebill(
            billstatus       = billstatus,
            org_number       = org_number,
            supplier_number  = supplier_number,
            material_number  = material_number,
            warehouse_number = warehouse_number,
            date_start       = date_start,
            date_end         = date_end,
            modifytime_start = modifytime_start,
            modifytime_end   = modifytime_end,
            pageNo           = page,
            pageSize         = pageSize,
        )

        if not resp.get("status"):
            error_code = resp.get("errorCode", "UNKNOWN")
            message    = resp.get("message", "")
            print(f"[API 错误] errorCode={error_code}, message={message}")
            break

        data        = resp.get("data", {})
        bills       = data.get("rows", [])
        total_count = data.get("totalCount", "?")
        is_last     = data.get("lastPage", True)

        all_bills.extend(bills)
        print(f"[API] 本页 {len(bills)} 条单据，累计 {len(all_bills)} 条，"
              f"接口总记录数 {total_count}，末页={is_last}")

        if is_last:
            print("[API] 已到最后一页，停止翻页。")
            break

        if max_pages and page >= max_pages:
            print(f"[API] 已达最大页数限制 {max_pages}，停止翻页。")
            break

        page += 1
        time.sleep(sleep_sec)

    print(f"[API] 拉取完成，共 {len(all_bills)} 条原始单据。")
    return all_bills


# =========================================================
# 独立测试（直接运行此文件时）
# =========================================================

if __name__ == "__main__":
    print("=" * 60)
    print("【fetch_purreceivebill.py 独立测试 — 只查询不落库】")
    print("=" * 60)
    result = query_purreceivebill(pageNo=1, pageSize=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
