## API 返回参数分析

根据金蝶云星空 API 文档中的“返回参数”部分，主要的数据体现在 `data.rows` 数组中。以下是 `data.rows` 中包含的字段及其对应的类型和说明，这将作为 PostgreSQL 表结构设计的依据。

| 参数名称 | 参数类型 | 说明 | 对应 PostgreSQL 类型 |
| :-- | :-- | :-- | :-- |
| id | Long | id | BIGINT |
| modifytime | DateTime | 修改时间 | TIMESTAMP |
| createtime | DateTime | 创建时间 | TIMESTAMP |
| begindebitqty | Decimal | 期初余额借方数量 | NUMERIC(20, 4) |
| begindebitfor | Decimal | 期初余额借方原币 | NUMERIC(20, 4) |
| begindebitlocal | Decimal | 期初余额借方本位币 | NUMERIC(20, 4) |
| begincreditqty | Decimal | 期初余额贷方数量 | NUMERIC(20, 4) |
| begincreditfor | Decimal | 期初余额贷方原币 | NUMERIC(20, 4) |
| begincreditlocal | Decimal | 期初余额贷方本位币 | NUMERIC(20, 4) |
| yeardebitqty | Decimal | 本年累计借方数量 | NUMERIC(20, 4) |
| yeardebitfor | Decimal | 本年累计借方原币 | NUMERIC(20, 4) |
| yeardebitlocal | Decimal | 本年累计借方本位币 | NUMERIC(20, 4) |
| yearcreditqty | Decimal | 本年累计贷方数量 | NUMERIC(20, 4) |
| yearcreditfor | Decimal | 本年累计贷方原币 | NUMERIC(20, 4) |
| yearcreditlocal | Decimal | 本年累计贷方本位币 | NUMERIC(20, 4) |
| yearprofitdebitqty | Decimal | 本年实际损益借方数量 | NUMERIC(20, 4) |
| yearprofitdebitfor | Decimal | 本年实际损益借方原币 | NUMERIC(20, 4) |
| yearprofitdebitlocal | Decimal | 本年实际损益借方本位币 | NUMERIC(20, 4) |
| yearprofitcreditqty | Decimal | 本年实际损益贷方数量 | NUMERIC(20, 4) |
| yearprofitcreditfor | Decimal | 本年实际损益贷方原币 | NUMERIC(20, 4) |
| yearprofitcreditlocal | Decimal | 本年实际损益贷方本位币 | NUMERIC(20, 4) |
| assgrp | Flex | 核算维度 | JSONB (或单独表) |
| org_number | String | 核算组织.编码 | VARCHAR(50) |
| org_name | String | 核算组织.名称 | VARCHAR(255) |
| booktype_name | String | 账簿类型.名称 | VARCHAR(255) |
| booktype_number | String | 账簿类型.编码 | VARCHAR(50) |
| accounttable_number | String | 科目表.编码 | VARCHAR(50) |
| accounttable_name | String | 科目表.名称 | VARCHAR(255) |
| curlocal_number | String | 本位币.货币代码 | VARCHAR(50) |
| curlocal_name | String | 本位币.名称 | VARCHAR(255) |
| period_name | String | 当前期间.名称 | VARCHAR(255) |
| period_number | String | 当前期间.编码 | VARCHAR(50) |
| account_number | String | 科目.编码 | VARCHAR(50) |
| account_name | String | 科目.名称 | VARCHAR(255) |
| currency_number | String | 币别.货币代码 | VARCHAR(50) |
| currency_name | String | 币别.名称 | VARCHAR(255) |
| measureunit_number | String | 计量单位.编码 | VARCHAR(50) |
| measureunit_name | String | 计量单位.名称 | VARCHAR(255) |

## 数据库表结构设计

考虑到 `assgrp` 字段是一个复杂的 JSON 对象，为了简化表结构和提高查询效率，我们有两种处理方式：

1.  **存储为 JSONB 类型**：直接将 `assgrp` 字段存储为 PostgreSQL 的 `JSONB` 类型。这种方式简单直接，但如果需要频繁查询 `assgrp` 内部的特定字段，性能可能不如单独的表。
2.  **拆分为单独的表**：将 `assgrp` 内部的字段拆分出来，创建一张新的表，并通过外键与主表关联。这种方式更符合关系型数据库范式，但会增加表的数量和查询的复杂性。

考虑到 `assgrp` 的结构示例中包含 `弹性域名称-辅助资料类型`、`弹性域名称-基础资料类型` 等动态键，以及 `id`, `number`, `name` 等子字段，将其直接存储为 `JSONB` 类型更为灵活，且能更好地适应未来可能的变化。如果后续有明确的查询需求，可以再考虑创建索引或将其拆分。

因此，我们选择将 `assgrp` 存储为 `JSONB` 类型。

**表名建议**：`kd_gl_initbalance_query` (金蝶总账科目余额初始化查询)

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
    -- 增加一个字段用于记录数据同步时间，便于增量同步
    _sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 为 modifytime 字段创建索引，以加速增量同步查询
CREATE INDEX IF NOT EXISTS idx_kd_gl_initbalance_query_modifytime ON kd_gl_initbalance_query (modifytime);
```

## 数据同步方案

### 1. 数据初始化

数据初始化是指首次从 API 获取所有历史数据并写入数据库。由于 API 提供了分页参数 (`pageSize`, `pageNo`)，我们需要循环调用 API，直到获取所有页面数据。

**步骤**：

1.  设置 `pageSize` 为一个合适的值（例如 100 或 500）。
2.  从 `pageNo = 1` 开始，循环调用 API。
3.  每次调用获取数据后，将 `data.rows` 中的记录插入到 `kd_gl_initbalance_query` 表中。为了避免重复插入，可以使用 `ON CONFLICT (id) DO NOTHING` 或 `ON CONFLICT (id) DO UPDATE SET ...` 语句。
4.  根据 API 返回的 `lastPage` 字段判断是否为最后一页，如果 `lastPage` 为 `true`，则停止循环。

### 2. 增量同步

增量同步是指定期检查 API，只获取自上次同步以来发生变化或新增的数据。API 响应中包含 `modifytime` 字段，可以利用此字段进行增量同步。

**步骤**：

1.  查询 `kd_gl_initbalance_query` 表中 `modifytime` 字段的最大值 (`max_modifytime`)。如果表为空，则执行数据初始化。
2.  调用 API 时，在 Query 参数中增加一个过滤条件，例如 `modifytime > max_modifytime`。然而，金蝶 API 的 `Query` 参数中没有直接支持 `modifytime` 过滤的字段。因此，我们需要采取另一种策略：
    *   **全量拉取，基于 `modifytime` 比较更新**：定期（例如每小时或每天）全量拉取所有数据（或者拉取一个时间窗口内的数据，例如过去24小时内的数据，如果API支持按时间范围查询）。然后，对于每条记录，根据其 `id` 判断是新增还是更新：
        *   如果 `id` 不存在，则插入新记录。
        *   如果 `id` 存在，并且 API 返回的 `modifytime` 大于数据库中对应记录的 `modifytime`，则更新该记录。
    *   **基于 `_sync_time` 字段进行增量标记**：在每次同步时，记录当前同步时间到 `_sync_time` 字段。下次同步时，可以查询 `_sync_time` 大于上次同步时间的记录，但这种方式需要 API 能够支持按照 `_sync_time` 字段进行过滤，或者我们仍然需要全量拉取后在本地进行比较。

考虑到金蝶 API 的 `Query` 参数中没有直接支持 `modifytime` 过滤，**“全量拉取，基于 `modifytime` 比较更新”** 是一个更稳健的方案。虽然是全量拉取，但我们可以通过 `pageSize` 和 `pageNo` 分页拉取，并在本地进行 `id` 和 `modifytime` 的比较，只更新有变化的记录，从而实现“增量”的效果。

**增量同步具体步骤**：

1.  获取当前时间 `current_sync_time`。
2.  循环调用 API，获取所有页面数据。
3.  对于每条从 API 获取的记录：
    a.  尝试根据 `id` 查询数据库中是否存在该记录。
    b.  如果记录不存在，则插入新记录，并将 `_sync_time` 设置为 `current_sync_time`。
    c.  如果记录存在，比较 API 返回的 `modifytime` 和数据库中记录的 `modifytime`。
        i.  如果 API 返回的 `modifytime` 更新，则更新数据库中的记录，并将 `_sync_time` 设置为 `current_sync_time`。
        ii. 如果 API 返回的 `modifytime` 没有更新，则跳过该记录。

这种方式确保了数据的完整性，并且只对有变化的记录进行数据库操作，减少了不必要的写入开销。
