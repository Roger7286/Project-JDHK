import requests
import json
import datetime
import os
import time

# =========================================================
# 金蝶 OpenAPI - 销售订单查询
# 接口地址: /v2/sm/sm_salorder/query
# 文档: https://dev.kingdee.com/open/detail/api/1769178924861893632
# =========================================================

# ===== API 基础配置（与 get_access_token.py 保持一致）=====
ACCOUNT_ID        = "2438647909164529664"
CLIENT_ID         = "AWS"
X_ACGW_IDENTITY   = "djF8MTlkMWY4N2M3OGQwMDExNjhmMDF8NDkyNzk1MDQ4NTUyOXxbv5-LC7jhMXrdVvfUYbgYuKh8fX3MSrybpN6z5P9HAnw="
USERNAME          = "AWS"
CLIENT_SECRET     = "WWViVi20251110$HQAZ621"
BASE_URL          = "https://hkprod.kdsuite.ai"
TOKEN_PATH        = "/kapi/oauth2/getToken"
LANGUAGE          = "zh_CN"

# Token 缓存文件（与同目录下其他脚本共享）
TOKEN_CACHE_FILE  = os.path.join(os.path.dirname(__file__), "kingdee_token_cache.json")

# 销售订单查询接口路径
SAL_ORDER_PATH = "/kapi/v2/sm/sm_salorder/query"


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
    inner = resp_json.get("data", {})
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
# 销售订单查询（单页）
# =========================================================

def query_sal_order(
    start_bizdate:     str = None,
    end_bizdate:       str = None,
    id:                list = None,
    billno:            list = None,
    billstatus:        list = None,
    org_number:        list = None,
    start_createtime:  str = None,
    end_createtime:    str = None,
    start_modifytime:  str = None,
    end_modifytime:    str = None,
    customer_number:   list = None,
    pageNo:            int = 1,
    pageSize:          int = 100,
) -> dict:
    """
    调用金蝶销售订单查询接口（单页）。

    参数说明：
        start_bizdate      订单日期开始，格式 '2023-09-06'
        end_bizdate        订单日期结束，格式 '2023-09-06'
        id                 订单内部 ID 列表，如 ["7434491278170763264"]
        billno             单据编号列表，如 ["SO-0001"]
        billstatus         单据状态列表：A=保存, B=提交, C=审核，如 ["A", "C"]
        org_number         销售组织编码列表，如 ["001"]
        start_createtime   创建时间开始，格式 '2023-09-12 00:00:00'
        end_createtime     创建时间结束，格式 '2023-09-12 00:00:00'
        start_modifytime   修改时间开始，格式 '2023-09-12 00:00:00'
        end_modifytime     修改时间结束，格式 '2023-09-12 00:00:00'
        customer_number    客户编码列表，如 ["C001"]
        pageNo             页码，默认 1
        pageSize           每页条数，默认 100，最大 1000

    返回：
        接口原始 JSON 响应（dict）
    """
    access_token = get_valid_token()

    url = f"{BASE_URL}{SAL_ORDER_PATH}"
    # 注意：销售订单查询接口 Header 使用 "accesstoken"（无下划线），与库存接口不同
    headers = {
        "Content-Type":    "application/json",
        "accesstoken":     access_token,
        "x-acgw-identity": X_ACGW_IDENTITY,
    }

    # 过滤条件放入 data 子对象，仅传入非 None / 非空的字段
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
    if customer_number:  filter_data["customer_number"]  = customer_number

    # 请求体结构: {"data": {...过滤条件...}, "pageNo": N, "pageSize": N}
    payload = {
        "data":     filter_data,
        "pageNo":   pageNo,
        "pageSize": pageSize,
    }

    print(f"\n[API] POST {url}")
    print(f"[API] 请求体: {json.dumps(payload, ensure_ascii=False, indent=2)}")

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    print(f"[API] HTTP 状态码: {resp.status_code}")
    resp.raise_for_status()

    result = resp.json()
    return result


# =========================================================
# 销售订单查询（自动翻页，拉取全部数据）
# =========================================================

def query_all_pages(
    start_bizdate:    str = None,
    end_bizdate:      str = None,
    billno:           list = None,
    billstatus:       list = None,
    org_number:       list = None,
    start_createtime: str = None,
    end_createtime:   str = None,
    start_modifytime: str = None,
    end_modifytime:   str = None,
    customer_number:  list = None,
    pageSize:         int = 100,
    max_pages:        int = None,
    sleep_sec:        float = 0.3,
) -> list:
    """
    自动翻页，拉取所有销售订单记录。

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
        resp = query_sal_order(
            start_bizdate=start_bizdate,
            end_bizdate=end_bizdate,
            billno=billno,
            billstatus=billstatus,
            org_number=org_number,
            start_createtime=start_createtime,
            end_createtime=end_createtime,
            start_modifytime=start_modifytime,
            end_modifytime=end_modifytime,
            customer_number=customer_number,
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
        # 判断是否最后一页：当本页条数 < pageSize 时视为最后一页
        is_last = len(rows) < pageSize

        print(f"[分页] 本页获取 {len(rows)} 条，累计 {len(all_rows)} 条，总计 {total_count} 条，末页={is_last}")

        if is_last:
            print("[分页] 已到最后一页，停止翻页。")
            break

        if max_pages and page >= max_pages:
            print(f"[分页] 已达到最大页数限制 {max_pages}，停止翻页。")
            break

        page += 1
        time.sleep(sleep_sec)

    print(f"\n===== 共获取 {len(all_rows)} 条销售订单记录 =====")
    return all_rows


# =========================================================
# 主程序入口（示例调用）
# =========================================================

if __name__ == "__main__":
    # -------------------------------------------------------
    # 示例 1：单页查询（按修改时间段过滤）
    # -------------------------------------------------------
    print("=" * 60)
    print("示例 1：单页查询")
    print("=" * 60)

    result = query_sal_order(
        # 按订单日期范围过滤（取消注释以启用）
        # start_bizdate="2024-01-01",
        # end_bizdate="2024-12-31",

        # 按修改时间过滤（取消注释以启用）
        # start_modifytime="2024-06-01 00:00:00",
        # end_modifytime="2024-06-30 23:59:59",

        # 按单据状态过滤：A=保存, B=提交, C=审核
        # billstatus=["C"],

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
    #     start_modifytime="2024-06-01 00:00:00",
    #     end_modifytime="2024-06-30 23:59:59",
    #     billstatus=["C"],
    #     pageSize=100,
    # )
    # print(f"\n共获取 {len(all_records)} 条记录")
