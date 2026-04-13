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
    "account_id":       "2438647909676230656",
    "client_id":        "AWS",
    "username":         "AWS",
    "client_secret":    "Happy1234567890!",
    "x_acgw_identity":  "djF8MTlkNDgwNzRmMWMwMDExNjhmMDF8NDkyODYyOTkzMjAyNny-EPmorbbR5vPU9Nda3rQ0Cv4cZF01PXmksYq4ELxjYHw=",

    # 服务地址
    "base_url":         "https://hkprod.test.kdsuite.ai",
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
    "host":     "jdhk-prod.c58iamu0qyeg.ap-southeast-1.rds.amazonaws.com",
    "port":     5432,
    "database": "jdhk_db",
    "user":     "app_jdhk_prod",
    "password": "Xavi0408$&",   # ← 按实际修改
    "schema":   "jdhk"
}
