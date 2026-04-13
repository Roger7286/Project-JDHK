-- =========================================================
-- 金蝶 即时库存明细 - PostgreSQL 建表语句
-- 对应接口: /v2/im/getInventoryDetail
-- 文档:     https://vip.kingdee.com/knowledge/728252231845369856
--
-- 主键: id（金蝶记录唯一 ID）
-- 写入策略: INSERT ... ON CONFLICT (id) DO UPDATE（upsert）
-- =========================================================

CREATE TABLE IF NOT EXISTS kingdee_inventory_detail (

    -- ---- 主键 ----
    id                  VARCHAR(64)      NOT NULL,   -- 记录唯一 ID

    -- ---- 组织 ----
    org                 BIGINT,                      -- 库存组织 ID
    org_number          VARCHAR(64),                 -- 库存组织编码
    org_name            VARCHAR(255),                -- 库存组织名称

    -- ---- 物料 ----
    material            VARCHAR(64),                 -- 物料 ID
    material_number     VARCHAR(128),                -- 物料编码
    material_name       VARCHAR(255),                -- 物料名称
    material_modelnum   VARCHAR(255),                -- 规格型号
    material_helpcode   VARCHAR(128),                -- 助记码

    -- ---- 辅助属性 / 批次 ----
    auxpty              VARCHAR(64),                 -- 辅助属性
    lotnum              VARCHAR(128),                -- 批次号
    producedate         DATE,                        -- 生产日期
    expirydate          DATE,                        -- 到期日

    -- ---- 库存计量单位 ----
    unit                BIGINT,                      -- 库存单位 ID
    unit_number         VARCHAR(64),                 -- 库存单位编码
    unit_name           VARCHAR(64),                 -- 库存单位名称
    qty                 NUMERIC(28, 10),             -- 库存单位数量

    -- ---- 基本单位 ----
    baseunit            BIGINT,                      -- 基本单位 ID
    baseunit_number     VARCHAR(64),                 -- 基本单位编码
    baseunit_name       VARCHAR(64),                 -- 基本单位名称
    baseqty             NUMERIC(28, 10),             -- 基本单位数量

    -- ---- 第二计量单位 ----
    unit2nd             BIGINT,                      -- 第二计量单位 ID
    unit2nd_number      VARCHAR(64),                 -- 第二计量单位编码
    unit2nd_name        VARCHAR(64),                 -- 第二计量单位名称
    qty2nd              NUMERIC(28, 10),             -- 第二计量单位数量

    -- ---- 第三计量单位 ----
    unit3rd             BIGINT,                      -- 第三计量单位 ID
    unit3rd_number      VARCHAR(64),                 -- 第三计量单位编码
    unit3rd_name        VARCHAR(64),                 -- 第三计量单位名称
    qty3rd              NUMERIC(28, 10),             -- 第三计量单位数量

    -- ---- 仓库 ----
    warehouse           VARCHAR(64),                 -- 仓库 ID
    warehouse_number    VARCHAR(128),                -- 仓库编码
    warehouse_name      VARCHAR(255),                -- 仓库名称

    -- ---- 货位 ----
    location            BIGINT,                      -- 货位 ID
    location_number     VARCHAR(128),                -- 货位编码
    location_name       VARCHAR(255),                -- 货位名称

    -- ---- 库存状态 ----
    invstatus           VARCHAR(64),                 -- 库存状态 ID
    invstatus_number    VARCHAR(64),                 -- 库存状态编码
    invstatus_name      VARCHAR(128),                -- 库存状态名称（如：可用）

    -- ---- 库存类型 ----
    invtype             VARCHAR(64),                 -- 库存类型 ID
    invtype_number      VARCHAR(64),                 -- 库存类型编码
    invtype_name        VARCHAR(128),                -- 库存类型名称（如：普通）

    -- ---- 货主 ----
    ownertype           VARCHAR(64),                 -- 货主类型
    owner               BIGINT,                      -- 货主 ID
    owner_number        VARCHAR(64),                 -- 货主编码
    owner_name          VARCHAR(255),                -- 货主名称

    -- ---- 保管方 ----
    keepertype          VARCHAR(64),                 -- 保管方类型
    keeper              BIGINT,                      -- 保管方 ID
    keeper_number       VARCHAR(64),                 -- 保管方编码
    keeper_name         VARCHAR(255),                -- 保管方名称

    -- ---- 跟踪号 / 配置码 / 项目 ----
    tracknumber         BIGINT,                      -- 跟踪号 ID
    tracknumber_number  VARCHAR(128),                -- 跟踪号编码
    tracknumber_name    VARCHAR(255),                -- 跟踪号名称
    configuredcode      BIGINT,                      -- 配置码 ID
    configuredcode_number VARCHAR(128),              -- 配置码编码
    configuredcode_name VARCHAR(255),                -- 配置码名称
    project             BIGINT,                      -- 项目 ID
    project_number      VARCHAR(128),                -- 项目编码
    project_name        VARCHAR(255),                -- 项目名称

    -- ---- 版本 ----
    mversion            BIGINT,                      -- 版本 ID
    mversion_number     VARCHAR(64),                 -- 版本编码
    mversion_name       VARCHAR(128),                -- 版本名称

    -- ---- 可用数量 ----
    avbbaseqty          NUMERIC(28, 10),             -- 基本单位可用数量
    avbqty              NUMERIC(28, 10),             -- 库存单位可用数量
    avbqty2nd           NUMERIC(28, 10),             -- 第二单位可用数量
    avbqty3rd           NUMERIC(28, 10),             -- 第三单位可用数量

    -- ---- 预留/锁定数量 ----
    baseqty_lock        NUMERIC(28, 10),             -- 基本单位预留数量（API 原始字段）
    qty_lock            NUMERIC(28, 10),             -- 库存单位预留数量（API 原始字段）
    qty2nd_lock         NUMERIC(28, 10),             -- 第二单位预留数量（API 原始字段）
    qty3rd_lock         NUMERIC(28, 10),             -- 第三单位预留数量（API 原始字段）
    lockbaseqty         NUMERIC(28, 10),             -- 锁定基本数量
    lockqty             NUMERIC(28, 10),             -- 锁定库存单位数量
    lockqty2nd          NUMERIC(28, 10),             -- 锁定第二单位数量
    lockqty3rd          NUMERIC(28, 10),             -- 锁定第三单位数量

    -- ---- 时间戳 ----
    modifytime          TIMESTAMP,                   -- 最后修改时间

    -- ---- ETL 元数据 ----
    sync_time           TIMESTAMP NOT NULL DEFAULT NOW(),  -- 本次同步写入时间

    CONSTRAINT pk_kingdee_inventory_detail PRIMARY KEY (id)
);

-- 常用查询索引
CREATE INDEX IF NOT EXISTS idx_kid_org_number      ON kingdee_inventory_detail (org_number);
CREATE INDEX IF NOT EXISTS idx_kid_material_number ON kingdee_inventory_detail (material_number);
CREATE INDEX IF NOT EXISTS idx_kid_warehouse_number ON kingdee_inventory_detail (warehouse_number);
CREATE INDEX IF NOT EXISTS idx_kid_modifytime      ON kingdee_inventory_detail (modifytime);

COMMENT ON TABLE kingdee_inventory_detail IS '金蝶即时库存明细，来源接口: /v2/im/getInventoryDetail';
