# 金蝶调拨申请单同步模块

## 目录

- [模块概述](#模块概述)
- [文件结构](#文件结构)
- [数据库表结构](#数据库表结构)
- [同步流程总览](#同步流程总览)
- [删除同步详细说明](#删除同步详细说明)
- [main.py 参数说明](#mainpy-参数说明)
- [fetch_transapply.py 参数说明](#fetch_transapplypy-参数说明)
- [常用运行示例](#常用运行示例)
- [注意事项](#注意事项)

---

## 模块概述

本模块将金蝶苍穹 **调拨申请单**（`/v2/im/im_transapply/getList`）同步到 PostgreSQL，支持：

- **新增同步**：API 返回的新单据写入 PG
- **修改同步**：API 返回的已有单据覆盖更新 PG
- **删除同步**：API 不再返回的单据在 PG 中标记软删除

---

## 文件结构

```
kingdee_im_transapply_getlist/
├── create_tables.sql        # 建表 SQL（含软删除字段、索引、迁移语句）
├── fetch_transapply.py      # Token 管理 + API 分页拉取
├── load_transapply_to_pg.py # 字段映射 + 批量 Upsert
├── main.py                  # 同步总入口（新增/修改/删除 三合一）
└── README.md                # 本文档
```

---

## 数据库表结构

### 主表 `jdhk.kingdee_transapply`

存储调拨申请单的表头信息（L1 字段）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | BIGINT PK | 金蝶单据 ID |
| `billno` | VARCHAR | 单据编号（如 DBSQ-260405-000001） |
| `billstatus` | VARCHAR | 单据状态：A=暂存，B=已提交，C=已审核 |
| `auditdate` | TIMESTAMP | 审核时间 |
| `modifytime` | TIMESTAMP | 修改时间 |
| `createtime` | TIMESTAMP | 创建时间 |
| `biztime` | DATE | **业务日期**（删除比对的基准字段） |
| `closestatus` | VARCHAR | 关闭状态：A=正常，B=已关闭 |
| `transtype` | VARCHAR | 调拨类型：A=组织内，B=跨组织 |
| `org_number` | VARCHAR | 申请组织编码 |
| `is_deleted` | BOOLEAN | **软删除标记**，默认 FALSE |
| `deleted_at` | TIMESTAMPTZ | 软删除时间（检测到 API 消失时写入） |
| `sync_time` | TIMESTAMPTZ | 最近同步时间 |

### 明细表 `jdhk.kingdee_transapply_entry`

存储调拨申请单的明细行信息（L2 字段）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | BIGINT PK | 明细行 ID |
| `bill_id` | BIGINT NOT NULL | 关联主表 `id`（外键） |
| `material_number` | VARCHAR | 物料编码 |
| `qty` | NUMERIC | 申请数量 |
| `transinqty` | NUMERIC | 已调入数量 |
| `transoutqty` | NUMERIC | 已调出数量 |
| `remaintransoutqty` | NUMERIC | 未调出数量 |
| `is_deleted` | BOOLEAN | **软删除标记**，随主表联动 |
| `deleted_at` | TIMESTAMPTZ | 软删除时间 |
| `sync_time` | TIMESTAMPTZ | 最近同步时间 |

> 完整字段列表见 `create_tables.sql`。

---

## 同步流程总览

每次运行 `main.py` 按以下顺序执行：

```
Step 1  从 API 拉取数据
        ↓
Step 2  连接 PostgreSQL
        ↓
Step 3  Upsert（新增 / 修改）
        ↓
Step 4  删除同步（检测 API 消失的记录 → 软删除）
        ↓
Step 5  更新 sync_state 状态表
```

---

## 删除同步详细说明

### 核心原理

金蝶 API 是**查询现存数据**的接口，不提供专门的删除事件推送。因此采用「日期范围比对」的方式间接检测删除：

> 在同一个 `biztime` 范围内，**PG 里有但 API 不再返回**的记录，即为已在金蝶被删除。

### 执行步骤

```
①  提取本次 API 返回的所有主单 id
    api_ids = { "100001", "100002", "100003" }

②  查询 PG：同 biztime 范围内，is_deleted=FALSE 的所有主单 id
    pg_ids  = { "100001", "100002", "100003", "100004" }

③  计算差集
    deleted_ids = pg_ids - api_ids = { "100004" }
    → id=100004 在 API 消失，认定为已在金蝶删除

④  软删除主表（UPDATE，不物理删除）
    UPDATE kingdee_transapply
    SET is_deleted=TRUE, deleted_at=NOW()
    WHERE id IN ('100004')

⑤  联动软删除明细表
    UPDATE kingdee_transapply_entry
    SET is_deleted=TRUE, deleted_at=NOW()
    WHERE bill_id IN ('100004')

⑥  提交事务（主表和明细在同一事务内，保证一致性）
```

### 触发条件

删除同步**必须满足以下全部条件**才会执行：

| 条件 | 说明 |
|------|------|
| 未使用 `--skip_delete_sync` | 手动跳过时不执行 |
| `billno` 为空 | 指定了单据编号 = 只查了部分记录，不代表全量 |
| `billstatus` 为空 | 指定了状态 = 只查了该状态的记录，其他状态会被误判删除 |
| `org_number` 为空 | 指定了组织 = 只查了该组织的记录，其他组织会被误判删除 |
| `start_biztime` 和 `end_biztime` 均有值 | 没有 biztime 范围则无法做比对 |

**示例：哪些情况会执行删除同步**

```bash
# ✅ 执行删除同步 — 全量查询，API 返回范围内所有记录
python main.py

# ✅ 执行删除同步 — 自定义日期范围，仍是全量查询
python main.py --start_biztime "2025-01-01" --end_biztime "2025-03-31"

# ✅ 执行删除同步 — auditdate 是时间条件，不影响全量性
python main.py --start_auditdate "2025-04-01 00:00:00" --end_auditdate "2025-04-11 23:59:59"

# ❌ 不执行删除同步 — billstatus 导致 API 只返回已审核单据，暂存/提交的单会被误删
python main.py --billstatus C

# ❌ 不执行删除同步 — org_number 导致 API 只返回该组织数据，其他组织的单会被误删
python main.py --org_number "BU-001"

# ❌ 不执行删除同步 — billno 只查了指定单据，其他所有单据都会被误删
python main.py --billno "DBSQ-260405-000001"

# ❌ 不执行删除同步 — 手动跳过
python main.py --skip_delete_sync
```

### 软删除 vs 物理删除

本模块使用**软删除**（标记字段），而非 `DELETE` 语句，原因：

- 保留审计轨迹，可查看哪些单据曾经存在
- 金蝶偶发数据撤销/反审核后重建，软删除可以通过再次 upsert 恢复（`is_deleted` 会被 upsert 覆盖为 FALSE）
- 误删时可手动恢复，`DELETE` 则不可逆

### 查询时过滤软删除记录

业务查询时需主动过滤：

```sql
-- 查询有效的主单
SELECT * FROM jdhk.kingdee_transapply
WHERE is_deleted = FALSE;

-- 查询有效的明细（通过主单过滤）
SELECT e.*
FROM jdhk.kingdee_transapply_entry e
WHERE e.is_deleted = FALSE;

-- 主明细关联查询（双重过滤）
SELECT h.billno, h.billstatus, e.material_number, e.qty
FROM jdhk.kingdee_transapply h
JOIN jdhk.kingdee_transapply_entry e ON e.bill_id = h.id
WHERE h.is_deleted = FALSE
  AND e.is_deleted = FALSE;

-- 查看已被软删除的记录（审计/排查）
SELECT id, billno, biztime, deleted_at
FROM jdhk.kingdee_transapply
WHERE is_deleted = TRUE
ORDER BY deleted_at DESC;
```

---

## main.py 参数说明

`main.py` 是同步总入口，控制同步范围、过滤条件和删除行为。

### 运行方式

```bash
cd kingdee_im_transapply_getlist
python main.py [参数...]
```

### 全部参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--start_biztime` | DATE 字符串 | 今天 - 30 天 | 业务日期下限（含），格式 `YYYY-MM-DD` |
| `--end_biztime` | DATE 字符串 | 今天 | 业务日期上限（含），格式 `YYYY-MM-DD` |
| `--start_auditdate` | DATETIME 字符串 | 无 | 审核时间下限（含），格式 `YYYY-MM-DD HH:MM:SS` |
| `--end_auditdate` | DATETIME 字符串 | 无 | 审核时间上限（含），格式 `YYYY-MM-DD HH:MM:SS` |
| `--billstatus` | 逗号分隔字符串 | 无（不过滤） | 单据状态：`A`=暂存，`B`=已提交，`C`=已审核 |
| `--org_number` | 逗号分隔字符串 | 无（不过滤） | 申请组织编码，多个用逗号分隔 |
| `--billno` | 逗号分隔字符串 | 无（不过滤） | 单据编号，多个用逗号分隔 |
| `--skip_delete_sync` | 开关（无值） | False | 指定后跳过删除同步，只做新增/修改 |

### 参数详细说明

#### `--start_biztime` / `--end_biztime`

控制同步的业务日期范围，**也是删除比对的基准范围**。

- 默认值在程序启动时动态计算（`今天 - 30天` 到 `今天`），不是固定写死的
- 两个参数同时指定才有效，建议成对使用
- 这两个参数的范围越大，一次同步的数据量越多，同时删除比对的范围也越大

```bash
python main.py --start_biztime "2025-01-01" --end_biztime "2025-12-31"
```

#### `--start_auditdate` / `--end_auditdate`

按审核时间过滤，适合**增量同步场景**（只拉取最近被审核的单据）。

- 与 `biztime` 是独立的过滤条件，可同时使用
- 使用审核时间过滤时，不影响删除同步的执行（删除比对仍按 `biztime` 范围做）
- 常用于定时任务，每小时同步一次最近审核的变更

```bash
# 同步今天审核的单据，同时对 biztime 范围做删除比对
python main.py --start_auditdate "2025-04-11 00:00:00" --end_auditdate "2025-04-11 23:59:59"
```

#### `--billstatus`

按单据状态过滤，多个状态用逗号分隔。

- **使用此参数会自动跳过删除同步**，因为 API 只返回指定状态的记录，不能代表全量
- 适合只关心某个状态的场景，如只同步已审核的单据

```bash
python main.py --billstatus C          # 只同步已审核
python main.py --billstatus A,B        # 同步暂存和已提交
python main.py --billstatus A,B,C      # 同步所有状态（等同于不过滤）
```

#### `--org_number`

按申请组织编码过滤，多个组织用逗号分隔。

- **使用此参数会自动跳过删除同步**，因为 API 只返回该组织的记录
- 适合只维护特定组织数据的场景

```bash
python main.py --org_number "BU-001"
python main.py --org_number "BU-001,BU-002,BU-003"
```

#### `--billno`

按单据编号精确同步，多个编号用逗号分隔。

- **使用此参数会自动跳过删除同步**，因为 API 只返回指定单据
- 适合手动补录或排查特定单据

```bash
python main.py --billno "DBSQ-260405-000001"
python main.py --billno "DBSQ-260405-000001,DBSQ-260405-000002"
```

#### `--skip_delete_sync`

强制跳过删除同步，程序只执行新增/修改同步。

- 无需赋值，指定即生效
- 适合初始化历史数据导入时使用（导入期间不做删除判断）
- 也适合只想快速同步变更，不需要检测删除的场景

```bash
python main.py --skip_delete_sync
python main.py --start_biztime "2024-01-01" --end_biztime "2024-12-31" --skip_delete_sync
```

---

## fetch_transapply.py 参数说明

`fetch_transapply.py` 负责 Token 管理和 API 分页拉取，可独立运行用于测试查询。

### 对外接口

#### `fetch_all_pages()` — 供 main.py 调用

自动翻页，返回所有原始数据行（`list[dict]`）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `start_biztime` | str | None | 业务起始日期 |
| `end_biztime` | str | None | 业务截止日期 |
| `start_auditdate` | str | None | 审核起始时间 |
| `end_auditdate` | str | None | 审核截止时间 |
| `billno` | list[str] | None | 单据编号列表 |
| `billstatus` | list[str] | None | 单据状态列表 |
| `org_number` | list[str] | None | 组织编码列表 |
| `pageSize` | int | 100 | 每页条数（建议不超过 200） |
| `max_pages` | int | None | 最大翻页数，None 表示不限制 |
| `sleep_sec` | float | 0.3 | 翻页间隔秒数，避免频繁请求 |

#### `query_transapply()` — 单页查询

查询单页数据，返回接口原始 JSON `dict`，不做字段转换。

#### `get_valid_token()` — Token 管理

自动读取缓存 Token 或重新申请，缓存文件路径由 `config.py` 中 `token_cache_file` 指定。

### 独立运行（测试查询）

`fetch_transapply.py` 可以**单独执行**，只查询 API 数据，不落库，方便调试字段结构。

```bash
cd kingdee_im_transapply_getlist
python fetch_transapply.py [参数...]
```

独立运行时支持的参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--start_biztime` | 今天 - 30 天 | 业务起始日期 |
| `--end_biztime` | 今天 | 业务截止日期 |
| `--start_auditdate` | 无 | 审核起始时间 |
| `--end_auditdate` | 无 | 审核截止时间 |
| `--billno` | 无 | 单据编号（逗号分隔） |
| `--billstatus` | 无 | 单据状态（逗号分隔） |
| `--org_number` | 无 | 组织编码（逗号分隔） |
| `--pagesize` | 5 | 每页条数（测试建议用小值） |

```bash
# 查看最近 3 天的数据，每页 3 条
python fetch_transapply.py --start_biztime "2025-04-08" --end_biztime "2025-04-11" --pagesize 3

# 查看指定单据的原始 JSON 结构
python fetch_transapply.py --billno "DBSQ-260405-000001" --pagesize 1
```

输出为完整的 API 原始 JSON，便于确认字段名和数据结构。

---

## 常用运行示例

### 日常定时同步（推荐）

```bash
# 每天运行，同步近 30 天数据，自动检测删除
python main.py
```

### 历史数据全量导入

```bash
# 导入全年数据，跳过删除同步（导入期间不做删除判断）
python main.py --start_biztime "2024-01-01" --end_biztime "2024-12-31" --skip_delete_sync
```

### 增量同步（按审核时间）

```bash
# 每小时同步一次：只拉取过去 1 小时内审核的单据
python main.py --start_auditdate "2025-04-11 10:00:00" --end_auditdate "2025-04-11 11:00:00"
```

### 手动补录指定单据

```bash
# 单独同步一张单据
python main.py --billno "DBSQ-260405-000001"

# 同步多张单据
python main.py --billno "DBSQ-260405-000001,DBSQ-260405-000002"
```

### 只同步某状态

```bash
# 只同步已审核单据（适合只关心审核完成数据的场景）
python main.py --billstatus C
```

### 排查：只查不落库

```bash
# 先用 fetch 独立运行确认 API 返回的字段结构，再跑 main
python fetch_transapply.py --billno "DBSQ-260405-000001" --pagesize 1
```

---

## 注意事项

1. **删除比对依赖 biztime 范围**
   比对的是「在该 biztime 范围内，PG 有但 API 无的记录」。如果某单据的 biztime 不在当次同步范围内，即使它被删除了，也不会被检测到，下次扩大日期范围时才会被检测到。

2. **选择性过滤与删除同步互斥**
   `--billstatus`、`--org_number`、`--billno` 任一使用时，程序会自动跳过删除同步。这是安全机制，防止误删。

3. **软删除后的 Upsert 恢复**
   如果一条被软删除的记录（`is_deleted=TRUE`）在之后的 API 响应中重新出现（例如金蝶中撤销删除），upsert 操作会将它的所有字段覆盖更新，**但 `is_deleted` 字段不在 upsert 的更新列中**。如需恢复，需手动执行：
   ```sql
   UPDATE jdhk.kingdee_transapply SET is_deleted=FALSE, deleted_at=NULL WHERE id=xxx;
   UPDATE jdhk.kingdee_transapply_entry SET is_deleted=FALSE, deleted_at=NULL WHERE bill_id=xxx;
   ```
   > 如有此需求，可在 `load_transapply_to_pg.py` 的 upsert SQL 中将 `is_deleted` 加入更新列，改为同步 API 返回的删除状态（但 API 不提供此字段，一般无需处理）。

4. **首次建表 vs 已有表迁移**
   - **新环境**：直接执行 `create_tables.sql` 即可
   - **已有表**：执行文件末尾「迁移语句」部分（取消注释后执行）







设计说明
核心机制（日期范围比对法）

API (biztime 2025-03-12 ~ 2025-04-11) 返回：{id_A, id_B, id_C}
PG  (biztime 2025-03-12 ~ 2025-04-11) 存有：{id_A, id_B, id_C, id_D}
                                                                   ↑
                                             id_D 在 API 消失 = 已被删除
→ 软删除 id_D：is_deleted=TRUE, deleted_at=NOW()
触发条件（自动判断）
场景	是否执行删除同步	原因
python main.py（默认）	✅ 执行	全量查询，API 返回范围内全部数据
--billstatus A	❌ 跳过	API 只返回暂存单，不能代表全部
--org_number BU-001	❌ 跳过	API 只返回该组织数据
--billno DBSQ-xxx	❌ 跳过	指定单据查询，不代表全量
--start_auditdate 单独用	✅ 执行	auditdate 是时间条件，不影响全量性
--skip_delete_sync	❌ 跳过	手动跳过
查询已删除记录

-- 正常业务查询（过滤软删除）
SELECT * FROM jdhk.kingdee_transapply WHERE is_deleted = FALSE;

-- 明细关联（自动排除已删主表）
SELECT e.* FROM jdhk.kingdee_transapply_entry e
JOIN jdhk.kingdee_transapply h ON h.id = e.bill_id
WHERE h.is_deleted = FALSE;

-- 查看被删除的记录（审计用）
SELECT * FROM jdhk.kingdee_transapply WHERE is_deleted = TRUE ORDER BY deleted_at DESC;
删除逻辑是什么?只修改了main?其他地方有没有修改，什么情况下会触发删除？请给出详细解释
删除同步逻辑详解
修改了哪些文件？
只修改了两个文件：

create_tables.sql — 主表加了两个字段
main.py — 加了 sync_deletes() 函数和调用逻辑
fetch_transapply.py 和 load_transapply_to_pg.py 没有改动。

删除逻辑的完整流程

每次运行 main.py 的执行顺序：

Step 1: 从 API 拉取数据（已有）
Step 2: 连接 PG（已有）
Step 3: Upsert 新增/修改的记录（已有）
Step 4: 删除同步 ← 新增的
Step 5: 更新 sync_state（已有）
Step 4 的内部逻辑：


①  从 API 拉回的 all_rows 里提取所有 id → api_ids = {id_A, id_B, id_C}

②  去 PG 查：同一个 biztime 范围内，is_deleted=FALSE 的所有 id
    → pg_ids = {id_A, id_B, id_C, id_D}

③  差集 = pg_ids - api_ids = {id_D}
    含义：id_D 在金蝶已被删除，所以 API 不再返回它

④  执行 UPDATE：
    SET is_deleted = TRUE, deleted_at = NOW()
    WHERE id IN (id_D)
什么情况下会触发删除？
触发删除的三个前提条件必须同时满足：


# main.py:286-296
selective_filter_used = any([billno, billstatus, org_number])

if skip_delete_sync:          # 条件1：没有手动跳过
    ...跳过
elif selective_filter_used:   # 条件2：没有用选择性过滤参数
    ...跳过
elif not (start_biztime and end_biztime):  # 条件3：biztime 范围有效
    ...跳过
else:
    # 三个条件都满足 → 执行删除比对
    api_ids = {str(row.get("id")) for row in all_rows}
    total_deleted = sync_deletes(conn, api_ids, start_biztime, end_biztime)
用表格说明：

运行命令	触发删除？	原因
python main.py	✅ 触发	默认全量查 30 天，API 返回该范围内所有记录
python main.py --start_biztime "2025-01-01" --end_biztime "2025-03-31"	✅ 触发	指定范围的全量查询
python main.py --start_auditdate "2025-04-01 00:00:00"	✅ 触发	auditdate 只影响拉取哪些记录，但 biztime 范围仍然有效，比对还是按 biztime 做
python main.py --billstatus C	❌ 不触发	API 只返回已审核的，PG 里暂存/已提交的记录不会出现在 api_ids 里，会被误删
python main.py --org_number BU-001	❌ 不触发	API 只返回该组织的，其他组织的记录会被误删
python main.py --billno DBSQ-001	❌ 不触发	只查了一张单，其他单都会被误删
python main.py --skip_delete_sync	❌ 不触发	手动跳过
为什么 load_transapply_to_pg.py 不需要改？
因为删除比对是在 main.py 里直接操作 PG 的，逻辑是：


main.py 自己做：
  api_ids（来自 all_rows）  vs  PG 查出的 pg_ids  →  差集  →  UPDATE

load_transapply_to_pg.py 只做 upsert，职责不变。
为什么只软删除主表，不动明细表？
明细表的删除通过 JOIN 主表自动过滤，无需单独标记：


-- 正常业务查询，自动排除已删除单据的明细
SELECT e.*
FROM jdhk.kingdee_transapply_entry e
JOIN jdhk.kingdee_transapply h ON h.id = e.bill_id
WHERE h.is_deleted = FALSE;
如果同时给明细表加 is_deleted，维护两张表的一致性反而增加复杂度，没有必要。