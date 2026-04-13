# 金蝶云星空 API 数据同步 PostgreSQL 方案

## 1. 方案概述

本方案旨在实现金蝶云星空“科目余额初始化查询”API 的数据同步到 PostgreSQL 数据库。方案涵盖了数据库表结构设计、数据初始化（全量同步）和增量同步的 Python 实现，并提供了详细的使用说明和注意事项。**本次更新增加了 `access_token` 及其过期时间的文件化存储和读取功能，以减少不必要的认证请求，提升 API 调用效率。**

## 2. API 分析

根据金蝶云星空开发者门户提供的 API 文档 [1]，我们分析了“科目余额初始化查询”API 的请求参数和返回参数。

### 2.1 接口基本信息

*   **用途说明**：科目余额初始化查询操作
*   **请求方式**：GET
*   **请求 URL**：`/v2/gl/gl_initbalance/query`

### 2.2 请求头参数

| 参数名称 | 参数值 | 说明 |
| :-- | :-- | :-- |
| Content-Type | `application/json` | 内容格式 |
| accesstoken | 获取的 `accesstoken` 值 | 请求令牌 |
| Idempotency-Key | 唯一的 `requestId` | 非必传参数，防止接口被重复调用 |

### 2.3 Query 参数

| 参数名称 | 参数类型 | 必填 | 说明 | 层级 | 示例 |
| :-- | :-- | :-- | :-- | :-- | :-- |
| org_number | String | 是 | 核算组织.编码 | 1 | `"53461"` |
| booktype_number | String | 是 | 账簿类型.编码 | 1 | `"100001"` |
| isdeleted | String | 否 | 数据是否已删除 | 1 | `"0"` |
| pageSize | Integer | 是 | 分页参数，分页数量 | 1 | `10` |
| pageNo | Integer | 否 | 分页参数，查询页码 | 1 | `1` |

### 2.4 返回参数

API 返回的主要数据体现在 `data.rows` 数组中。以下是 `data.rows` 中包含的字段及其对应的类型和说明：

| 参数名称 | 参数类型 | 说明 | 对应 PostgreSQL 类型 |
| :-- | :-- | :-- | :-- |
| id | Long | id | `BIGINT` |
| modifytime | DateTime | 修改时间 | `TIMESTAMP` |
| createtime | DateTime | 创建时间 | `TIMESTAMP` |
| begindebitqty | Decimal | 期初余额借方数量 | `NUMERIC(20, 4)` |
| begindebitfor | Decimal | 期初余额借方原币 | `NUMERIC(20, 4)` |
| begindebitlocal | Decimal | 期初余额借方本位币 | `NUMERIC(20, 4)` |
| begincreditqty | Decimal | 期初余额贷方数量 | `NUMERIC(20, 4)` |
| begincreditfor | Decimal | 期初余额贷方原币 | `NUMERIC(20, 4)` |
| begincreditlocal | Decimal | 期初余额贷方本位币 | `NUMERIC(20, 4)` |
| yeardebitqty | Decimal | 本年累计借方数量 | `NUMERIC(20, 4)` |
| yeardebitfor | Decimal | 本年累计借方原币 | `NUMERIC(20, 4)` |
| yeardebitlocal | Decimal | 本年累计借方本位币 | `NUMERIC(20, 4)` |
| yearcreditqty | Decimal | 本年累计贷方数量 | `NUMERIC(20, 4)` |
| yearcreditfor | Decimal | 本年累计贷方原币 | `NUMERIC(20, 4)` |
| yearcreditlocal | Decimal | 本年累计贷方本位币 | `NUMERIC(20, 4)` |
| yearprofitdebitqty | Decimal | 本年实际损益借方数量 | `NUMERIC(20, 4)` |
| yearprofitdebitfor | Decimal | 本年实际损益借方原币 | `NUMERIC(20, 4)` |
| yearprofitdebitlocal | Decimal | 本年实际损益借方本位币 | `NUMERIC(20, 4)` |
| yearprofitcreditqty | Decimal | 本年实际损益贷方数量 | `NUMERIC(20, 4)` |
| yearprofitcreditfor | Decimal | 本年实际损益贷方原币 | `NUMERIC(20, 4)` |
| yearprofitcreditlocal | Decimal | 本年实际损益贷方本位币 | `NUMERIC(20, 4)` |
| assgrp | Flex | 核算维度 | `JSONB` |
| org_number | String | 核算组织.编码 | `VARCHAR(50)` |
| org_name | String | 核算组织.名称 | `VARCHAR(255)` |
| booktype_name | String | 账簿类型.名称 | `VARCHAR(255)` |
| booktype_number | String | 账簿类型.编码 | `VARCHAR(50)` |
| accounttable_number | String | 科目表.编码 | `VARCHAR(50)` |
| accounttable_name | String | 科目表.名称 | `VARCHAR(255)` |
| curlocal_number | String | 本位币.货币代码 | `VARCHAR(50)` |
| curlocal_name | String | 本位币.名称 | `VARCHAR(255)` |
| period_name | String | 当前期间.名称 | `VARCHAR(255)` |
| period_number | String | 当前期间.编码 | `VARCHAR(50)` |
| account_number | String | 科目.编码 | `VARCHAR(50)` |
| account_name | String | 科目.名称 | `VARCHAR(255)` |
| currency_number | String | 币别.货币代码 | `VARCHAR(50)` |
| currency_name | String | 币别.名称 | `VARCHAR(255)` |
| measureunit_number | String | 计量单位.编码 | `VARCHAR(50)` |
| measureunit_name | String | 计量单位.名称 | `VARCHAR(255)` |

## 3. 数据库表结构设计

考虑到 `assgrp` 字段是一个复杂的 JSON 对象，为了兼顾灵活性和查询效率，我们选择将其存储为 PostgreSQL 的 `JSONB` 类型。这样可以直接存储 JSON 结构，并且 PostgreSQL 对 `JSONB` 类型提供了丰富的查询和索引支持。

**表名建议**：`kd_gl_initbalance_query`

**建表语句**：

```sql
CREATE TABLE IF NOT EXISTS kd_gl_initbalance_query (
    id BIGINT PRIMARY KEY,
    modifytime TIMESTAMP,
    createtime TIMESTAMP,
    begindebitqty NUMERIC(20, 4),
    begindebitfor NUMERIC(20, 4),
    begindebitlocal NUMERIC(20, 4),
    begincreditqty NUMERIC(20, 4),
    begincreditfor NUMERIC(20, 4),
    begincreditlocal NUMERIC(20, 4),
    yeardebitqty NUMERIC(20, 4),
    yeardebitfor NUMERIC(20, 4),
    yeardebitlocal NUMERIC(20, 4),
    yearcreditqty NUMERIC(20, 4),
    yearcreditfor NUMERIC(20, 4),
    yearcreditlocal NUMERIC(20, 4),
    yearprofitdebitqty NUMERIC(20, 4),
    yearprofitdebitfor NUMERIC(20, 4),
    yearprofitdebitlocal NUMERIC(20, 4),
    yearprofitcreditqty NUMERIC(20, 4),
    yearprofitcreditfor NUMERIC(20, 4),
    yearprofitcreditlocal NUMERIC(20, 4),
    assgrp JSONB,
    org_number VARCHAR(50),
    org_name VARCHAR(255),
    booktype_name VARCHAR(255),
    booktype_number VARCHAR(50),
    accounttable_number VARCHAR(50),
    accounttable_name VARCHAR(255),
    curlocal_number VARCHAR(50),
    curlocal_name VARCHAR(255),
    period_name VARCHAR(255),
    period_number VARCHAR(50),
    account_number VARCHAR(50),
    account_name VARCHAR(255),
    currency_number VARCHAR(50),
    currency_name VARCHAR(255),
    measureunit_number VARCHAR(50),
    measureunit_name VARCHAR(255),
    -- 增加一个字段用于记录数据同步时间，便于增量同步追踪
    _sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 为 modifytime 字段创建索引，以加速增量同步查询（尽管本方案中增量同步是全量拉取后比较，但此索引仍有助于其他基于时间的查询）
CREATE INDEX IF NOT EXISTS idx_kd_gl_initbalance_query_modifytime ON kd_gl_initbalance_query (modifytime);
```

## 4. Python 实现

我们使用 Python 编写数据同步脚本 `sync_kingdee_data.py`，利用 `requests` 库调用金蝶 API，`psycopg2` 库连接 PostgreSQL 数据库。脚本包含了建表、数据获取、数据初始化和增量同步的逻辑。**本次更新的关键在于增加了 `access_token` 的自动获取和刷新机制，并将其持久化到临时文件，以提高效率。**

### 4.1 认证流程分析 [2]

金蝶云星空 API 采用 Token 认证机制，具体流程如下：

1.  **获取 `app_token`**：通过 `appId` 和 `appSecret` 请求认证 API (`/api/getAppToken.do`) 获取临时 `app_token`。`app_token` 有效期通常为 2 小时。
2.  **获取 `access_token`**：使用 `app_token` 和用户手机号（或其他用户标识）请求认证 API (`/api/login.do`) 获取 `access_token`。`access_token` 同样具有有效期（通常为 2 小时），是后续调用业务 API 的凭证。
3.  **刷新 `access_token`**：在 `access_token` 过期前（例如提前 5 分钟），需要重新执行上述步骤获取新的 `access_token`。
4.  **Token 持久化**：为了减少重复认证请求，`access_token` 及其过期时间将被写入一个临时文件。在每次需要 `access_token` 时，优先从文件中读取，并判断是否仍然有效。如果有效则直接使用，如果过期则重新获取并更新文件。

### 4.2 脚本代码 (`sync_kingdee_data.py`)

```python
import requests
import psycopg2
from psycopg2 import extras
import json
from datetime import datetime, timedelta
import os
import time

# 数据库配置
DB_CONFIG = {
    'host': os.getenv('PG_HOST', 'localhost'),
    'database': os.getenv('PG_DATABASE', 'kingdee_db'),
    'user': os.getenv('PG_USER', 'postgres'),
    'password': os.getenv('PG_PASSWORD', 'postgres'),
    'port': os.getenv('PG_PORT', '5432')
}

# 金蝶 API 配置
KINGDEE_API_CONFIG = {
    'base_url': os.getenv('KINGDEE_API_BASE_URL', 'http://your_kingdee_api_domain/kapi'), # 请替换为实际的金蝶API域名
    'auth_base_url': os.getenv('KINGDEE_AUTH_BASE_URL', 'http://your_kingdee_auth_domain/api'), # 请替换为实际的金蝶认证API域名
    'app_id': os.getenv('KINGDEE_APP_ID', 'YOUR_APP_ID'), # 第三方应用appId
    'app_secret': os.getenv('KINGDEE_APP_SECRET', 'YOUR_APP_SECRET'), # 第三方应用appSecret
    'user_phone': os.getenv('KINGDEE_USER_PHONE', 'YOUR_USER_PHONE'), # 用户手机号
    'tenant_id': os.getenv('KINGDEE_TENANT_ID', ''), # 租户ID，非必填
    'account_id': os.getenv('KINGDEE_ACCOUNT_ID', ''), # 数据中心ID，非必填
    'org_number': os.getenv('KINGDEE_ORG_NUMBER', '53461'), # 核算组织编码
    'booktype_number': os.getenv('KINGDEE_BOOKTYPE_NUMBER', '100001'), # 账簿类型编码
    'page_size': 100 # 每次请求的数据量
}

TABLE_NAME = 'kd_gl_initbalance_query'
TOKEN_FILE = '/tmp/kingdee_access_token.json' # 临时文件路径，用于存储 access_token

# 数据库建表语句
CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    id BIGINT PRIMARY KEY,
    modifytime TIMESTAMP,
    createtime TIMESTAMP,
    begindebitqty NUMERIC(20, 4),
    begindebitfor NUMERIC(20, 4),
    begindebitlocal NUMERIC(20, 4),
    begincreditqty NUMERIC(20, 4),
    begincreditfor NUMERIC(20, 4),
    begincreditlocal NUMERIC(20, 4),
    yeardebitqty NUMERIC(20, 4),
    yeardebitfor NUMERIC(20, 4),
    yeardebitlocal NUMERIC(20, 4),
    yearcreditqty NUMERIC(20, 4),
    yearcreditfor NUMERIC(20, 4),
    yearcreditlocal NUMERIC(20, 4),
    yearprofitdebitqty NUMERIC(20, 4),
    yearprofitdebitfor NUMERIC(20, 4),
    yearprofitdebitlocal NUMERIC(20, 4),
    yearprofitcreditqty NUMERIC(20, 4),
    yearprofitcreditfor NUMERIC(20, 4),
    yearprofitcreditlocal NUMERIC(20, 4),
    assgrp JSONB,
    org_number VARCHAR(50),
    org_name VARCHAR(255),
    booktype_name VARCHAR(255),
    booktype_number VARCHAR(50),
    accounttable_number VARCHAR(50),
    accounttable_name VARCHAR(255),
    curlocal_number VARCHAR(50),
    curlocal_name VARCHAR(255),
    period_name VARCHAR(255),
    period_number VARCHAR(50),
    account_number VARCHAR(50),
    account_name VARCHAR(255),
    currency_number VARCHAR(50),
    currency_name VARCHAR(255),
    measureunit_number VARCHAR(50),
    measureunit_name VARCHAR(255),
    _sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_modifytime ON {TABLE_NAME} (modifytime);
"""

def get_db_connection():
    """建立数据库连接"""
    return psycopg2.connect(**DB_CONFIG)

def create_table():
    """创建数据表"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(CREATE_TABLE_SQL)
        conn.commit()
        print(f"Table '{TABLE_NAME}' created or already exists.")
    except Exception as e:
        print(f"Error creating table: {e}")
    finally:
        if conn:
            conn.close()

def save_token_to_file(token_data):
    """将 token 数据保存到文件"""
    try:
        with open(TOKEN_FILE, 'w') as f:
            json.dump(token_data, f)
        print(f"Token data saved to {TOKEN_FILE}")
    except Exception as e:
        print(f"Error saving token to file: {e}")

def load_token_from_file():
    """从文件加载 token 数据"""
    if not os.path.exists(TOKEN_FILE):
        return None
    try:
        with open(TOKEN_FILE, 'r') as f:
            token_data = json.load(f)
        print(f"Token data loaded from {TOKEN_FILE}")
        return token_data
    except Exception as e:
        print(f"Error loading token from file: {e}")
        return None

def get_app_token():
    """获取 app_token"""
    url = f"{KINGDEE_API_CONFIG['auth_base_url']}/getAppToken.do"
    headers = {'Content-Type': 'application/json'}
    payload = {
        'appId': KINGDEE_API_CONFIG['app_id'],
        'appSecret': KINGDEE_API_CONFIG['app_secret'],
    }
    if KINGDEE_API_CONFIG['tenant_id']:
        payload['tenantid'] = KINGDEE_API_CONFIG['tenant_id']
    if KINGDEE_API_CONFIG['account_id']:
        payload['accountId'] = KINGDEE_API_CONFIG['account_id']

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        if result.get('status') and result.get('data') and result['data'].get('app_token'):
            print("App token obtained successfully.")
            return result['data']['app_token']
        else:
            print(f"Failed to get app token: {result.get('data', {}).get('error_desc', 'Unknown error')}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error getting app token: {e}")
        return None

def get_access_token(app_token):
    """获取 access_token"""
    url = f"{KINGDEE_API_CONFIG['auth_base_url']}/login.do"
    headers = {'Content-Type': 'application/json'}
    payload = {
        'user': KINGDEE_API_CONFIG['user_phone'],
        'apptoken': app_token,
        'usertype': 'Mobile', # 假设是手机号登录
        'language': 'zh_CN'
    }
    if KINGDEE_API_CONFIG['tenant_id']:
        payload['tenantid'] = KINGDEE_API_CONFIG['tenant_id']
    if KINGDEE_API_CONFIG['account_id']:
        payload['accountId'] = KINGDEE_API_CONFIG['account_id']

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        if result.get('status') and result.get('data') and result['data'].get('access_token'):
            print("Access token obtained successfully.")
            access_token = result['data']['access_token']
            # API 返回的 expire_time 是毫秒级时间戳
            expire_timestamp_ms = result['data']['expire_time']
            # 提前5分钟刷新，所以过期时间减去5分钟
            expire_time = datetime.fromtimestamp(expire_timestamp_ms / 1000) - timedelta(minutes=5)
            
            token_data = {
                'access_token': access_token,
                'expire_time': expire_time.isoformat() # 存储为 ISO 格式字符串
            }
            save_token_to_file(token_data)
            return access_token
        else:
            print(f"Failed to get access token: {result.get('data', {}).get('error_desc', 'Unknown error')}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error getting access token: {e}")
        return None

def get_valid_access_token():
    """获取一个有效的 access_token，优先从文件加载，过期则刷新"""
    token_data = load_token_from_file()
    if token_data:
        access_token = token_data.get('access_token')
        expire_time_str = token_data.get('expire_time')
        if access_token and expire_time_str:
            expire_time = datetime.fromisoformat(expire_time_str)
            if datetime.now() < expire_time:
                print("Using access token from file.")
                return access_token
            else:
                print("Access token from file is expired.")
        
    print("Access token not found or expired, obtaining new one...")
    app_token = get_app_token()
    if app_token:
        return get_access_token(app_token)
    return None

def fetch_kingdee_data(page_no, page_size):
    """从金蝶 API 获取数据"""
    current_access_token = get_valid_access_token()
    if not current_access_token:
        print("Could not get a valid access token. Aborting data fetch.")
        return None

    headers = {
        'Content-Type': 'application/json',
        'accesstoken': current_access_token
    }
    params = {
        'org_number': KINGDEE_API_CONFIG['org_number'],
        'booktype_number': KINGDEE_API_CONFIG['booktype_number'],
        'pageSize': page_size,
        'pageNo': page_no
    }
    url = f"{KINGDEE_API_CONFIG['base_url']}/v2/gl/gl_initbalance/query"
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status() # 检查 HTTP 错误
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API request error: {e}")
        return None

def insert_or_update_data(data_rows, current_sync_time):
    """插入或更新数据到数据库"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        for row in data_rows:
            processed_row = {}
            for k, v in row.items():
                if isinstance(v, (float, int)) and k not in ['id']:
                    processed_row[k] = str(v) # 将数字转换为字符串，数据库会进行隐式转换
                elif k == 'assgrp' and isinstance(v, dict):
                    processed_row[k] = json.dumps(v) # 将 assgrp 字典转换为 JSON 字符串
                elif k in ['modifytime', 'createtime'] and v:
                    try:
                        processed_row[k] = datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        processed_row[k] = None # 处理日期格式错误
                else:
                    processed_row[k] = v

            # 构建插入或更新的 SQL 语句
            # 使用 ON CONFLICT (id) DO UPDATE 实现 upsert
            insert_sql = f"""
            INSERT INTO {TABLE_NAME} (
                id, modifytime, createtime, begindebitqty, begindebitfor, begindebitlocal,
                begincreditqty, begincreditfor, begincreditlocal, yeardebitqty, yeardebitfor,
                yeardebitlocal, yearcreditqty, yearcreditfor, yearcreditlocal, yearprofitdebitqty,
                yearprofitdebitfor, yearprofitdebitlocal, yearprofitcreditqty, yearprofitcreditfor,
                yearprofitcreditlocal, assgrp, org_number, org_name, booktype_name, booktype_number,
                accounttable_number, accounttable_name, curlocal_number, curlocal_name, period_name,
                period_number, account_number, account_name, currency_number, currency_name,
                measureunit_number, measureunit_name, _sync_time
            ) VALUES (
                %(id)s, %(modifytime)s, %(createtime)s, %(begindebitqty)s, %(begindebitfor)s, %(begindebitlocal)s,
                %(begincreditqty)s, %(begincreditfor)s, %(begincreditlocal)s, %(yeardebitqty)s, %(yeardebitfor)s,
                %(yeardebitlocal)s, %(yearcreditqty)s, %(yearcreditfor)s, %(yearcreditlocal)s, %(yearprofitdebitqty)s,
                %(yearprofitdebitfor)s, %(yearprofitdebitlocal)s, %(yearprofitcreditqty)s, %(yearprofitcreditfor)s,
                %(yearprofitcreditlocal)s, %(assgrp)s, %(org_number)s, %(org_name)s, %(booktype_name)s, %(booktype_number)s,
                %(accounttable_number)s, %(accounttable_name)s, %(curlocal_number)s, %(curlocal_name)s, %(period_name)s,
                %(period_number)s, %(account_number)s, %(account_name)s, %(currency_number)s, %(currency_name)s,
                %(measureunit_number)s, %(measureunit_name)s, %(_sync_time)s
            ) ON CONFLICT (id) DO UPDATE SET
                modifytime = EXCLUDED.modifytime,
                createtime = EXCLUDED.createtime,
                begindebitqty = EXCLUDED.begindebitqty,
                begindebitfor = EXCLUDED.begindebitfor,
                begindebitlocal = EXCLUDED.begindebitlocal,
                begincreditqty = EXCLUDED.begincreditqty,
                begincreditfor = EXCLUDED.begincreditfor,
                begincreditlocal = EXCLUDED.begincreditlocal,
                yeardebitqty = EXCLUDED.yeardebitqty,
                yeardebitfor = EXCLUDED.yeardebitfor,
                yeardebitlocal = EXCLUDED.yeardebitlocal,
                yearcreditqty = EXCLUDED.yearcreditqty,
                yearcreditfor = EXCLUDED.yearcreditfor,
                yearcreditlocal = EXCLUDED.yearcreditlocal,
                yearprofitdebitqty = EXCLUDED.yearprofitdebitqty,
                yearprofitdebitfor = EXCLUDED.yearprofitdebitfor,
                yearprofitdebitlocal = EXCLUDED.yearprofitdebitlocal,
                yearprofitcreditqty = EXCLUDED.yearprofitcreditqty,
                yearprofitcreditfor = EXCLUDED.yearprofitcreditfor,
                yearprofitcreditlocal = EXCLUDED.yearprofitcreditlocal,
                assgrp = EXCLUDED.assgrp,
                org_number = EXCLUDED.org_number,
                org_name = EXCLUDED.org_name,
                booktype_name = EXCLUDED.booktype_name,
                booktype_number = EXCLUDED.booktype_number,
                accounttable_number = EXCLUDED.accounttable_number,
                accounttable_name = EXCLUDED.accounttable_name,
                curlocal_number = EXCLUDED.curlocal_number,
                curlocal_name = EXCLUDED.curlocal_name,
                period_name = EXCLUDED.period_name,
                period_number = EXCLUDED.period_number,
                account_number = EXCLUDED.account_number,
                account_name = EXCLUDED.account_name,
                currency_number = EXCLUDED.currency_number,
                currency_name = EXCLUDED.currency_name,
                measureunit_number = EXCLUDED.measureunit_number,
                measureunit_name = EXCLUDED.measureunit_name,
                _sync_time = EXCLUDED._sync_time
            WHERE EXCLUDED.modifytime > {TABLE_NAME}.modifytime;
            """
            # 确保 _sync_time 字段被正确传递
            processed_row['_sync_time'] = current_sync_time
            cur.execute(insert_sql, processed_row)
        
        conn.commit()
        print(f"Successfully processed {len(data_rows)} records.")
    except Exception as e:
        print(f"Error inserting/updating data: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def full_sync():
    """执行全量同步（数据初始化）"""
    print("Starting full synchronization...")
    create_table()
    page_no = 1
    has_more = True
    current_sync_time = datetime.now()

    while has_more:
        print(f"Fetching page {page_no}...")
        api_response = fetch_kingdee_data(page_no, KINGDEE_API_CONFIG['page_size'])
        if api_response and api_response.get('status') and api_response.get('data') and api_response['data'].get('rows'):
            data_rows = api_response['data']['rows']
            insert_or_update_data(data_rows, current_sync_time)
            if api_response['data'].get('lastPage'):
                has_more = False
            else:
                page_no += 1
        else:
            print(f"No data or error in API response for page {page_no}: {api_response}")
            has_more = False
            # 如果获取不到数据，等待一段时间后重试，或者直接退出
            time.sleep(5) 
    print("Full synchronization completed.")

def incremental_sync():
    """执行增量同步"""
    print("Starting incremental synchronization...")
    create_table() # 确保表存在
    current_sync_time = datetime.now()
    
    # 增量同步策略：全量拉取，基于 id 和 modifytime 比较更新
    # 由于 API 不支持 modifytime 过滤，我们只能全量拉取后在本地进行比较
    # 实际生产环境中，如果数据量巨大，需要考虑 API 是否支持时间范围查询或更高效的增量接口
    
    page_no = 1
    has_more = True
    while has_more:
        print(f"Fetching page {page_no} for incremental sync...")
        api_response = fetch_kingdee_data(page_no, KINGDEE_API_CONFIG['page_size'])
        if api_response and api_response.get('status') and api_response.get('data') and api_response['data'].get('rows'):
            data_rows = api_response['data']['rows']
            insert_or_update_data(data_rows, current_sync_time)
            if api_response['data'].get('lastPage'):
                has_more = False
            else:
                page_no += 1
        else:
            print(f"No data or error in API response for page {page_no}: {api_response}")
            has_more = False
            # 如果获取不到数据，等待一段时间后重试，或者直接退出
            time.sleep(5)
    print("Incremental synchronization completed.")

if __name__ == '__main__':
    # 示例用法：
    # 首次运行或需要全量同步时调用 full_sync()
    # full_sync()

    # 定期运行增量同步时调用 incremental_sync()
    # incremental_sync()
    
    print("请根据需要选择运行 full_sync() 或 incremental_sync() 函数。")
    print("请确保已设置环境变量 PG_HOST, PG_DATABASE, PG_USER, PG_PASSWORD, PG_PORT, KINGDEE_API_BASE_URL, KINGDEE_AUTH_BASE_URL, KINGDEE_APP_ID, KINGDEE_APP_SECRET, KINGDEE_USER_PHONE, KINGDEE_TENANT_ID, KINGDEE_ACCOUNT_ID, KINGDEE_ORG_NUMBER, KINGDEE_BOOKTYPE_NUMBER。")

```

### 4.3 脚本说明

*   **`DB_CONFIG`**: 数据库连接配置，通过环境变量获取，方便部署和管理。
*   **`KINGDEE_API_CONFIG`**: 金蝶 API 配置，包括 `base_url`（业务 API 域名）、`auth_base_url`（认证 API 域名）、`app_id`、`app_secret`、`user_phone`、`tenant_id`、`account_id`、`org_number`、`booktype_number` 和 `page_size`，同样通过环境变量配置。
*   **`TOKEN_FILE`**: 新增的配置项，定义了存储 `access_token` 及其过期时间的临时文件路径，默认为 `/tmp/kingdee_access_token.json`。
*   **`save_token_to_file(token_data)`**: 新增函数，负责将包含 `access_token` 和 `expire_time` 的字典保存到 `TOKEN_FILE` 中。
*   **`load_token_from_file()`**: 新增函数，负责从 `TOKEN_FILE` 中读取 `access_token` 和 `expire_time`。如果文件不存在或读取失败，则返回 `None`。
*   **`get_app_token()`**: 根据 `appId` 和 `appSecret` 获取 `app_token`。
*   **`get_access_token(app_token)`**: 根据 `app_token` 和 `user_phone` 获取 `access_token`，并设置其过期时间。**成功获取后，会将 `access_token` 和计算出的过期时间保存到 `TOKEN_FILE` 中。**
*   **`get_valid_access_token()`**: **核心优化函数**。它首先尝试从 `TOKEN_FILE` 中加载 `access_token`。如果加载成功且 `access_token` 尚未过期，则直接返回该 `access_token`。否则，它会调用 `get_app_token` 和 `get_access_token` 来获取新的 `access_token`，并将其保存到文件中。
*   **`fetch_kingdee_data(page_no, page_size)`**: 调用金蝶 API 获取指定页码和数量的数据。**在每次调用前会先调用 `get_valid_access_token()` 来确保使用有效的 `access_token`。**
*   **`insert_or_update_data(data_rows, current_sync_time)`**: 将从 API 获取的数据插入或更新到数据库。它使用 `ON CONFLICT (id) DO UPDATE` 语句实现 upsert (更新或插入) 逻辑。当 `id` 冲突时，如果 API 返回的 `modifytime` 大于数据库中已有的 `modifytime`，则更新记录。
*   **`full_sync()`**: 执行全量同步。它会循环调用 API，获取所有分页数据，并将其插入或更新到数据库。适用于首次数据导入或需要完全刷新数据时。
*   **`incremental_sync()`**: 执行增量同步。由于金蝶 API 不直接支持 `modifytime` 作为查询条件进行增量过滤，本方案采用“全量拉取，基于 `id` 和 `modifytime` 比较更新”的策略。每次同步都会拉取所有数据，但只更新 `id` 存在且 `modifytime` 有变化的记录，以及插入新记录。

## 5. 使用方法

### 5.1 环境准备

1.  **安装 Python 依赖**：
    ```bash
    pip install requests psycopg2-binary
    ```
2.  **PostgreSQL 数据库**：确保您有一个运行中的 PostgreSQL 数据库，并创建好相应的数据库和用户。
3.  **金蝶云星空应用注册**：在金蝶云星空 OpenAPI（开放平台）注册第三方应用，获取 `appId` 和 `appSecret`，并配置认证方式为 AccessToken 认证。同时，您需要一个用于登录的用户手机号。

### 5.2 配置环境变量

在运行脚本之前，需要设置以下环境变量，以提供数据库连接信息和金蝶 API 凭证。您可以将这些变量添加到您的 shell 配置文件（如 `.bashrc`, `.zshrc`）或在运行脚本前临时设置。

```bash
export PG_HOST="your_pg_host"
export PG_DATABASE="your_pg_database"
export PG_USER="your_pg_user"
export PG_PASSWORD="your_pg_password"
export PG_PORT="5432"

export KINGDEE_API_BASE_URL="http://your_kingdee_api_domain/kapi" # 例如：http://api.kingdee.com/kapi
export KINGDEE_AUTH_BASE_URL="http://your_kingdee_auth_domain/api" # 例如：http://api.kingdee.com/api
export KINGDEE_APP_ID="YOUR_APP_ID"
export KINGDEE_APP_SECRET="YOUR_APP_SECRET"
export KINGDEE_USER_PHONE="YOUR_USER_PHONE"
export KINGDEE_TENANT_ID="" # 租户ID，如果需要请填写
export KINGDEE_ACCOUNT_ID="" # 数据中心ID，如果需要请填写
export KINGDEE_ORG_NUMBER="53461" # 根据您的实际情况修改
export KINGDEE_BOOKTYPE_NUMBER="100001" # 根据您的实际情况修改
```

请务必将 `your_pg_host`、`your_pg_database`、`your_pg_user`、`your_pg_password`、`YOUR_APP_ID`、`YOUR_APP_SECRET`、`YOUR_USER_PHONE`、`your_kingdee_api_domain` 和 `your_kingdee_auth_domain` 替换为您的实际值。

### 5.3 运行脚本

1.  **保存脚本**：将上述 Python 代码保存为 `sync_kingdee_data.py` 文件。

2.  **首次运行（数据初始化）**：
    如果您是第一次同步数据，或者需要重新全量导入所有数据，请在 `sync_kingdee_data.py` 文件的 `if __name__ == '__main__':` 块中取消注释 `full_sync()`，并注释掉 `incremental_sync()`：
    ```python
    if __name__ == '__main__':
        full_sync()
        # incremental_sync()
    ```
    然后运行脚本：
    ```bash
    python sync_kingdee_data.py
    ```

3.  **定期运行（增量同步）**：
    如果您已经完成了数据初始化，并希望定期同步增量数据，请在 `sync_kingdee_data.py` 文件的 `if __name__ == '__main__':` 块中取消注释 `incremental_sync()`，并注释掉 `full_sync()`：
    ```python
    if __name__ == '__main__':
        # full_sync()
        incremental_sync()
    ```
    然后运行脚本。您可以将此脚本配置为定时任务（如使用 `cron`），以便定期执行增量同步。

## 6. 注意事项

*   **API 访问令牌**：`access_token` 具有有效期，脚本中已实现自动刷新机制，并支持将 `access_token` 及其过期时间持久化到临时文件 (`/tmp/kingdee_access_token.json`)。这样可以减少不必要的认证请求，提高 API 调用效率。请确保运行脚本的用户对 `/tmp` 目录有读写权限。
*   **API 速率限制**：金蝶 API 可能存在速率限制。如果数据量较大，频繁请求可能导致被限流。在实际使用中，可能需要根据 API 的限制调整 `page_size` 或在请求之间增加适当的延迟。
*   **数据量**：由于金蝶 API 不支持 `modifytime` 作为查询条件进行增量过滤，本方案的增量同步实际上是全量拉取后在本地进行比较更新。对于**超大数据量**的场景，这可能会带来较大的网络传输和数据库处理开销。如果 API 提供了更高效的增量接口（例如支持按时间范围查询），建议优先使用。
*   **错误处理**：脚本中包含了基本的异常处理，但在生产环境中，建议增加更完善的日志记录、重试机制和告警通知。
*   **`assgrp` 字段**：`assgrp` 字段存储为 `JSONB` 类型，如果后续需要对其内部字段进行频繁查询，可以考虑在 `assgrp` 字段上创建 GIN 索引以提高查询性能。
*   **数据类型转换**：API 返回的 `Decimal` 类型字段在 Python 中通常是字符串，脚本中已处理为 `NUMERIC(20, 4)` 类型存储到 PostgreSQL。如果精度要求不同，请调整 `NUMERIC` 的参数。

## 参考文献

[1] 金蝶AI苍穹开发者门户 - 科目余额初始化查询. [https://dev.kingdee.com/open/detail/api/1758915647800086528](https://dev.kingdee.com/open/detail/api/1758915647800086528)
[2] 金蝶云社区 - 认证方式-Accesstoken认证/JWT认证. [https://vip.kingdee.com/knowledge/specialDetail/272110040385964032?category=523054764884674304&id=537675769762560000&type=Knowledge&productLineId=1&lang=zh-CN](https://vip.kingdee.com/knowledge/specialDetail/272110040385964032?category=523054764884674304&id=537675769762560000&type=Knowledge&productLineId=1&lang=zh-CN)
