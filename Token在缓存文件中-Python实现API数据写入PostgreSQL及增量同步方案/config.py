import os

# =========================================================
# config.py  —  金蝶 OpenAPI 公共配置
# 所有业务脚本统一从此处 import，避免参数分散在各文件中。
#
# 使用方式（在业务脚本顶部）：
#   from config import OPENAPI_CONFIG, SYNC_CONFIG
# =========================================================

# ---------------------------------------------------------
# OpenAPI 认证 & 基础连接配置
# ---------------------------------------------------------
OPENAPI_CONFIG = {
    # 账号/认证
    "account_id":       "2438647909164529664",
    "client_id":        "AWS",
    "username":         "AWS",
    "client_secret":    "WWViVi20251110$HQAZ621",
    "x_acgw_identity":  "djF8MTlkMWY4N2M3OGQwMDExNjhmMDF8NDkyNzk1MDQ4NTUyOXxbv5-LC7jhMXrdVvfUYbgYuKh8fX3MSrybpN6z5P9HAnw=",

    # 服务地址
    "base_url":         "https://hkprod.kdsuite.ai",
    "token_path":       "/kapi/oauth2/getToken",
    "language":         "zh_CN",

    # Token 本地缓存文件路径（与 config.py 同目录）
    "token_cache_file": os.path.join(os.path.dirname(__file__), "kingdee_token_cache.json"),
}

# ---------------------------------------------------------
# 各业务接口路径
# ---------------------------------------------------------
API_PATHS = {
    # 即时库存明细查询
    "inventory_detail": "/kapi/v2/im/getInventoryDetail",

    # 销售订单查询
    "sal_order":        "/kapi/v2/sm/sm_salorder/query",
}

# ---------------------------------------------------------
# 同步任务通用配置
# ---------------------------------------------------------
SYNC_CONFIG = {
    # 每页拉取条数（最大 1000）
    "page_size":        100,

    # 翻页间隔（秒），防止接口限流
    "sleep_sec":        0.3,

    # 单次请求超时（秒）
    "request_timeout":  60,
}

# ---------------------------------------------------------
# PostgreSQL 数据库连接配置
# ---------------------------------------------------------
PG_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "database": "kingdee",
    "user":     "postgres",
    "password": "your_pg_password",   # ← 按实际修改
}
