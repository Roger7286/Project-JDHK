
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
TOKEN_FILE = '/tmp/kingdee_access_token.json' # 临时文件路径

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

