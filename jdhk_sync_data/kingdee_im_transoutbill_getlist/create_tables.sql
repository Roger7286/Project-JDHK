-- =============================================================
-- 分步调出单（im_transoutbill）数据表建表语句
-- API: /v2/im/im_transoutbill/getList
-- Schema: jdhk
--
-- 表结构说明：
--   1. kingdee_transoutbill        — 单据主表（表头，L1 字段）
--   2. kingdee_transoutbill_entry  — 单据明细表（表体，L2 字段）
--
-- 关联关系：
--   kingdee_transoutbill_entry.bill_id → kingdee_transoutbill.id
-- =============================================================

-- -------------------------------------------------------------
-- 1. 单据主表
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jdhk.kingdee_transoutbill (
    id                          BIGINT          PRIMARY KEY,          -- 单据ID
    billno                      VARCHAR(100),                         -- 单据编号
    billstatus                  VARCHAR(10),                          -- 单据状态 [A:暂存, B:已提交, C:已审核]
    biztime                     DATE,                                 -- 业务日期
    transtype                   VARCHAR(10),                          -- 调拨类型 [A:组织内调拨, B:跨组织调拨]
    transit                     VARCHAR(10),                          -- 在途归属 [A:调出货主, B:调入货主]
    org_number                  VARCHAR(100),                         -- 调出组织.编码
    inorg_number                VARCHAR(100),                         -- 调入组织.编码
    billtype_number             VARCHAR(100),                         -- 单据类型.编码
    billtype_name               VARCHAR(200),                         -- 单据类型.名称
    biztype_number              VARCHAR(100),                         -- 业务类型.编码
    biztype_name                VARCHAR(200),                         -- 业务类型.名称
    invscheme_number            VARCHAR(100),                         -- 库存事务.编码
    invscheme_name              VARCHAR(200),                         -- 库存事务.名称
    sync_time                   TIMESTAMPTZ     DEFAULT NOW()         -- 同步时间
);

COMMENT ON TABLE  jdhk.kingdee_transoutbill                     IS '金蝶分步调出单主表';
COMMENT ON COLUMN jdhk.kingdee_transoutbill.id                  IS '单据ID（金蝶内部ID）';
COMMENT ON COLUMN jdhk.kingdee_transoutbill.billno              IS '单据编号';
COMMENT ON COLUMN jdhk.kingdee_transoutbill.billstatus          IS '单据状态：A=暂存，B=已提交，C=已审核';
COMMENT ON COLUMN jdhk.kingdee_transoutbill.biztime             IS '业务日期';
COMMENT ON COLUMN jdhk.kingdee_transoutbill.transtype           IS '调拨类型：A=组织内调拨，B=跨组织调拨';
COMMENT ON COLUMN jdhk.kingdee_transoutbill.transit             IS '在途归属：A=调出货主，B=调入货主';
COMMENT ON COLUMN jdhk.kingdee_transoutbill.org_number          IS '调出组织编码';
COMMENT ON COLUMN jdhk.kingdee_transoutbill.inorg_number        IS '调入组织编码';
COMMENT ON COLUMN jdhk.kingdee_transoutbill.sync_time           IS '最近一次同步时间';

-- 主表索引
CREATE INDEX IF NOT EXISTS idx_transoutbill_billno
    ON jdhk.kingdee_transoutbill (billno);
CREATE INDEX IF NOT EXISTS idx_transoutbill_biztime
    ON jdhk.kingdee_transoutbill (biztime);
CREATE INDEX IF NOT EXISTS idx_transoutbill_billstatus
    ON jdhk.kingdee_transoutbill (billstatus);
CREATE INDEX IF NOT EXISTS idx_transoutbill_org
    ON jdhk.kingdee_transoutbill (org_number);


-- -------------------------------------------------------------
-- 2. 单据明细表
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jdhk.kingdee_transoutbill_entry (
    id                          BIGINT          PRIMARY KEY,          -- 明细行ID
    bill_id                     BIGINT          NOT NULL,             -- 关联主表ID（外键）

    -- 物料
    material_number             VARCHAR(100),                         -- 物料编码
    material_name               VARCHAR(500),                         -- 物料名称

    -- 调出仓库
    warehouse_number            VARCHAR(100),                         -- 调出仓库.编码
    warehouse_name              VARCHAR(200),                         -- 调出仓库.名称
    location_number             VARCHAR(100),                         -- 调出仓位.编码
    location_name               VARCHAR(200),                         -- 调出仓位.名称

    -- 调入仓库
    inwarehouse_number          VARCHAR(100),                         -- 调入仓库.编码
    inwarehouse_name            VARCHAR(200),                         -- 调入仓库.名称
    inlocation_number           VARCHAR(100),                         -- 调入仓位.编码
    inlocation_name             VARCHAR(200),                         -- 调入仓位.名称

    -- 数量
    qty                         NUMERIC(20, 6),                       -- 数量
    qtyunit3rd                  NUMERIC(20, 6),                       -- 辅助数量(2)

    -- 批次
    lotnumber                   VARCHAR(200),                         -- 批号

    -- 调出方（货主 / 保管者 / 库存状态类型）
    outownertype                VARCHAR(50),                          -- 调出货主类型
    outowner_number             VARCHAR(100),                         -- 调出货主.编码
    outowner_name               VARCHAR(200),                         -- 调出货主.名称
    outkeepertype               VARCHAR(50),                          -- 调出保管者类型
    outkeeper_number            VARCHAR(100),                         -- 调出保管者.编码
    outkeeper_name              VARCHAR(200),                         -- 调出保管者.名称
    outinvstatus_number         VARCHAR(100),                         -- 调出库存状态.编码
    outinvstatus_name           VARCHAR(200),                         -- 调出库存状态.名称
    outinvtype_number           VARCHAR(100),                         -- 调出库存类型.编码
    outinvtype_name             VARCHAR(200),                         -- 调出库存类型.名称

    -- 调入方（货主 / 保管者 / 库存状态类型）
    owner_number                VARCHAR(100),                         -- 调入货主.编码
    owner_name                  VARCHAR(200),                         -- 调入货主.名称
    keeper_number               VARCHAR(100),                         -- 调入保管者.编码
    keeper_name                 VARCHAR(200),                         -- 调入保管者.名称
    invstatus_number            VARCHAR(100),                         -- 调入库存状态.编码
    invstatus_name              VARCHAR(200),                         -- 调入库存状态.名称
    invtype_number              VARCHAR(100),                         -- 调入库存类型.编码
    invtype_name                VARCHAR(200),                         -- 调入库存类型.名称

    -- 在途货主
    transitowner_number         VARCHAR(100),                         -- 在途货主.编码
    transitowner_name           VARCHAR(200),                         -- 在途货主.名称

    -- 项目
    project_number              VARCHAR(100),                         -- 调出项目编码
    project_name                VARCHAR(200),                         -- 调出项目名称
    inproject_number            VARCHAR(100),                         -- 调入项目编码
    inproject_name              VARCHAR(200),                         -- 调入项目名称

    -- 单位
    unit_number                 VARCHAR(50),                          -- 库存单位.编码
    unit_name                   VARCHAR(100),                         -- 库存单位.名称
    unit2nd_number              VARCHAR(50),                          -- 辅助单位.编码
    unit2nd_name                VARCHAR(100),                         -- 辅助单位.名称
    unit3rd_number              VARCHAR(50),                          -- 辅助单位(2).编码
    unit3rd_name                VARCHAR(100),                         -- 辅助单位(2).名称

    -- 物料版本
    mversion_number             VARCHAR(100),                         -- 物料版本编码
    mversion_name               VARCHAR(200),                         -- 物料版本名称

    -- 行类型 / 跟踪号 / 配置号
    linetype_number             VARCHAR(100),                         -- 行类型.编码
    linetype_name               VARCHAR(200),                         -- 行类型.名称
    tracknumber_number          VARCHAR(200),                         -- 跟踪号
    configuredcode_number       VARCHAR(100),                         -- 配置号.编码
    configuredcode_name         VARCHAR(200),                         -- 配置号.名称

    -- 关联子实体（来源单据链接，JSON 序列化存储）
    billentry_lk                TEXT,                                 -- 关联子实体（JSON）

    sync_time                   TIMESTAMPTZ     DEFAULT NOW()         -- 同步时间
);

COMMENT ON TABLE  jdhk.kingdee_transoutbill_entry               IS '金蝶分步调出单明细表';
COMMENT ON COLUMN jdhk.kingdee_transoutbill_entry.id            IS '明细行ID（金蝶内部ID）';
COMMENT ON COLUMN jdhk.kingdee_transoutbill_entry.bill_id       IS '关联主表 kingdee_transoutbill.id';
COMMENT ON COLUMN jdhk.kingdee_transoutbill_entry.material_number IS '物料编码';
COMMENT ON COLUMN jdhk.kingdee_transoutbill_entry.warehouse_number IS '调出仓库编码';
COMMENT ON COLUMN jdhk.kingdee_transoutbill_entry.qty           IS '调出数量';
COMMENT ON COLUMN jdhk.kingdee_transoutbill_entry.billentry_lk  IS '来源单据关联信息（JSON数组）';
COMMENT ON COLUMN jdhk.kingdee_transoutbill_entry.sync_time     IS '最近一次同步时间';

-- 明细表索引
CREATE INDEX IF NOT EXISTS idx_transoutbill_entry_bill_id
    ON jdhk.kingdee_transoutbill_entry (bill_id);
CREATE INDEX IF NOT EXISTS idx_transoutbill_entry_material
    ON jdhk.kingdee_transoutbill_entry (material_number);
CREATE INDEX IF NOT EXISTS idx_transoutbill_entry_warehouse
    ON jdhk.kingdee_transoutbill_entry (warehouse_number);
CREATE INDEX IF NOT EXISTS idx_transoutbill_entry_lotnumber
    ON jdhk.kingdee_transoutbill_entry (lotnumber);
