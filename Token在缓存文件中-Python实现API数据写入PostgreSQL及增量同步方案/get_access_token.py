import requests
import json
import datetime


# ===== 现在已有的 =====
ACCOUNT_ID = "2438647909164529664"
CLIENT_ID = "AWS"
X_ACGW_IDENTITY = "djF8MTlkMWY4N2M3OGQwMDExNjhmMDF8NDkyNzk1MDQ4NTUyOXxbv5-LC7jhMXrdVvfUYbgYuKh8fX3MSrybpN6z5P9HAnw="
USERNAME = "AWS"
# ===== 还缺的 =====
CLIENT_SECRET = "WWViVi20251110$HQAZ621"   # AccessToken认证密钥
BASE_URL = "https://hkprod.kdsuite.ai"     # https://xxx.xxx.com
TOKEN_PATH = "/kapi/oauth2/getToken"       # token接口路径
LANGUAGE = "zh_CN"
NOCE = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
TIMESTAMP = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_access_token():
    url = f"{BASE_URL}{TOKEN_PATH}"

    headers = {
        "Content-Type": "application/json",
        "x-acgw-identity": X_ACGW_IDENTITY,
    }

    # 注意：
    # 下面 payload 字段名是“模板写法”
    # 真实字段名要以你们当前 OpenAPI 文档为准
    payload = {
        "accountId": ACCOUNT_ID,
        "client_id": CLIENT_ID,
        "username": USERNAME,
        "client_secret": CLIENT_SECRET,
        "language": LANGUAGE,
        "nonce": NOCE,
        "timestamp": TIMESTAMP
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)

    print("status_code =", resp.status_code)
    print("response_text =", resp.text)

    resp.raise_for_status()

    data = resp.json()

    # 常见写法：返回里有 access_token
    access_token = data.get("access_token")
    if not access_token:
        raise ValueError(f"未在响应中找到 access_token，完整返回为: {json.dumps(data, ensure_ascii=False)}")

    return access_token


if __name__ == "__main__":
    token = get_access_token()
    print("access_token =", token)