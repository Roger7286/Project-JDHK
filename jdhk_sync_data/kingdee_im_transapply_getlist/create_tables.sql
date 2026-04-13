-- =============================================================
-- 调拨申请单（im_transapply）数据表建表语句
-- API: /v2/im/im_transapply/getList
-- Schema: jdhk
--
-- 表结构说明：
--   1. kingdee_transapply        — 单据主表（表头，L1 字段）
--   2. kingdee_transapply_entry  — 单据明细表（表体，L2 字段）
--
-- 关联关系：
--   kingdee_transapply_entry.bill_id → kingdee_transapply.id
-- =============================================================

-- -------------------------------------------------------------
-- 1. 单据主表
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jdhk.kingdee_transapply (
    id                          BIGINT          PRIMARY KEY,          -- 单据ID
    billno                      VARCHAR(100),                         -- 单据编号
    billstatus                  VARCHAR(10),                          -- 单据状态 [A:暂存, B:已提交, C:已审核]
    auditdate                   TIMESTAMP,                            -- 审核时间
    modifytime                  TIMESTAMP,                            -- 修改时间
    createtime                  TIMESTAMP,                            -- 创建时间
    biztime                     DATE,                                 -- 业务日期
    comment                     TEXT,                                 -- 备注
    closedate                   TIMESTAMP,                            -- 关闭日期
    closestatus                 VARCHAR(10),                          -- 关闭状态 [A:正常, B:已关闭]
    handcloseflag               BOOLEAN,                              -- 手工关闭
    transtype                   VARCHAR(10),                          -- 调拨类型 [A:组织内调拨, B:跨组织调拨]
    biztype_number              VARCHAR(100),                         -- 业务类型.编码
    biztype_name                VARCHAR(200),                         -- 业务类型.名称
    billtype_number             VARCHAR(100),                         -- 单据类型.编码
    billtype_name               VARCHAR(200),                         -- 单据类型.名称
    org_number                  VARCHAR(100),                         -- 申请组织.编码
    org_name                    VARCHAR(200),                         -- 申请组织.名称
    applydept_number            VARCHAR(100),                         -- 申请部门.编码
    applyuser_number            VARCHAR(100),                         -- 申请人.工号
    settlecurrency_number       VARCHAR(20),                          -- 本位币.货币代码
    is_deleted                  BOOLEAN         DEFAULT FALSE,        -- 软删除标记（TRUE=已在金蝶删除）
    deleted_at                  TIMESTAMPTZ     DEFAULT NULL,         -- 软删除时间
    sync_time                   TIMESTAMPTZ     DEFAULT NOW()         -- 同步时间
);

COMMENT ON TABLE  jdhk.kingdee_transapply                       IS '金蝶调拨申请单主表';
COMMENT ON COLUMN jdhk.kingdee_transapply.id                    IS '单据ID（金蝶内部ID）';
COMMENT ON COLUMN jdhk.kingdee_transapply.billno                IS '单据编号';
COMMENT ON COLUMN jdhk.kingdee_transapply.billstatus            IS '单据状态：A=暂存，B=已提交，C=已审核';
COMMENT ON COLUMN jdhk.kingdee_transapply.biztime               IS '业务日期';
COMMENT ON COLUMN jdhk.kingdee_transapply.transtype             IS '调拨类型：A=组织内调拨，B=跨组织调拨';
COMMENT ON COLUMN jdhk.kingdee_transapply.closestatus           IS '关闭状态：A=正常，B=已关闭';
COMMENT ON COLUMN jdhk.kingdee_transapply.org_number            IS '申请组织编码';
COMMENT ON COLUMN jdhk.kingdee_transapply.is_deleted            IS '软删除标记：TRUE=已在金蝶删除，正常查询应过滤 is_deleted=FALSE';
COMMENT ON COLUMN jdhk.kingdee_transapply.deleted_at            IS '软删除时间（同步程序检测到该记录从API消失时写入）';
COMMENT ON COLUMN jdhk.kingdee_transapply.sync_time             IS '最近一次同步时间';

-- 主表索引
CREATE INDEX IF NOT EXISTS idx_transapply_billno
    ON jdhk.kingdee_transapply (billno);
CREATE INDEX IF NOT EXISTS idx_transapply_biztime
    ON jdhk.kingdee_transapply (biztime);
CREATE INDEX IF NOT EXISTS idx_transapply_modifytime
    ON jdhk.kingdee_transapply (modifytime);
CREATE INDEX IF NOT EXISTS idx_transapply_billstatus
    ON jdhk.kingdee_transapply (billstatus);
CREATE INDEX IF NOT EXISTS idx_transapply_org
    ON jdhk.kingdee_transapply (org_number);
CREATE INDEX IF NOT EXISTS idx_transapply_is_deleted
    ON jdhk.kingdee_transapply (is_deleted)
    WHERE is_deleted = TRUE;  -- 部分索引，仅索引已删除记录，节省空间


-- -------------------------------------------------------------
-- 2. 单据明细表
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jdhk.kingdee_transapply_entry (
    id                          BIGINT          PRIMARY KEY,          -- 明细行ID
    bill_id                     BIGINT          NOT NULL,             -- 关联主表ID（外键）

    -- 物料
    material_number             VARCHAR(100),                         -- 物料编码
    material_name               VARCHAR(500),                         -- 物料名称

    -- 仓库（调出）
    warehouse_number            VARCHAR(100),                         -- 调出仓库.编码
    warehouse_name              VARCHAR(200),                         -- 调出仓库.名称
    location_number             VARCHAR(100),                         -- 调出仓位.编码
    location_name               VARCHAR(200),                         -- 调出仓位.名称

    -- 仓库（调入）
    inwarehouse_number          VARCHAR(100),                         -- 调入仓库.编码
    inwarehouse_name            VARCHAR(200),                         -- 调入仓库.名称
    inlocation_number           VARCHAR(100),                         -- 调入仓位.编码
    inlocation_name             VARCHAR(200),                         -- 调入仓位.名称

    -- 数量
    qty                         NUMERIC(20, 6),                       -- 数量
    qtyunit2nd                  NUMERIC(20, 6),                       -- 辅助数量
    qtyunit3rd                  NUMERIC(20, 6),                       -- 辅助数量(2)

    -- 调拨数量
    transinqty                  NUMERIC(20, 6),                       -- 已调入数量
    transoutqty                 NUMERIC(20, 6),                       -- 已调出数量
    remaintransoutqty           NUMERIC(20, 6),                       -- 未调出数量

    -- 日期
    producedate                 DATE,                                 -- 生产日期
    expirydate                  DATE,                                 -- 有效期至

    -- 批次 / 属性
    lotnumber                   VARCHAR(200),                         -- 批号
    auxpty                      TEXT,                                 -- 辅助属性

    -- 货主 / 保管者（调出）
    ownertype                   VARCHAR(50),                          -- 出库货主类型
    owner_number                VARCHAR(100),                         -- 调出货主.编码
    owner_name                  VARCHAR(200),                         -- 调出货主.名称
    keepertype                  VARCHAR(50),                          -- 出库保管者类型
    keeper_number               VARCHAR(100),                         -- 出库保管者.编码
    keeper_name                 VARCHAR(200),                         -- 出库保管者.名称

    -- 货主 / 保管者（调入）
    inownertype                 VARCHAR(50),                          -- 入库货主类型
    inowner_number              VARCHAR(100),                         -- 调入货主.编码
    inowner_name                VARCHAR(200),                         -- 调入货主.名称
    inkeepertype                VARCHAR(50),                          -- 入库保管者类型
    inkeeper_number             VARCHAR(100),                         -- 入库保管者.编码
    inkeeper_name               VARCHAR(200),                         -- 入库保管者.名称

    -- 库存状态 / 类型（调出）
    invstatus_number            VARCHAR(100),                         -- 调出库存状态.编码
    invstatus_name              VARCHAR(200),                         -- 调出库存状态.名称
    invtype_number              VARCHAR(100),                         -- 调出库存类型.编码
    invtype_name                VARCHAR(200),                         -- 调出库存类型.名称

    -- 库存状态 / 类型（调入）
    ininvstatus_number          VARCHAR(100),                         -- 调入库存状态.编码
    ininvstatus_name            VARCHAR(200),                         -- 调入库存状态.名称
    ininvtype_number            VARCHAR(100),                         -- 调入库存类型.编码
    ininvtype_name              VARCHAR(200),                         -- 调入库存类型.名称

    -- 组织
    outorg_number               VARCHAR(100),                         -- 调出组织.编码
    outorg_name                 VARCHAR(200),                         -- 调出组织.名称
    inorg_number                VARCHAR(100),                         -- 调入组织.编码
    inorg_name                  VARCHAR(200),                         -- 调入组织.名称

    -- 项目
    project_number              VARCHAR(100),                         -- 调出项目编码
    project_name                VARCHAR(200),                         -- 调出项目名称
    inproject_number            VARCHAR(100),                         -- 调入项目编码
    inproject_name              VARCHAR(200),                         -- 调入项目名称

    -- 比率
    transrateup                 NUMERIC(10, 4),                       -- 数量超出比率(%)
    transratedown               NUMERIC(10, 4),                       -- 数量短缺比率(%)

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

    -- 备注
    entrycomment                TEXT,                                 -- 行备注

    is_deleted                  BOOLEAN         DEFAULT FALSE,        -- 软删除标记（TRUE=随主表删除）
    deleted_at                  TIMESTAMPTZ     DEFAULT NULL,         -- 软删除时间
    sync_time                   TIMESTAMPTZ     DEFAULT NOW()         -- 同步时间
);

COMMENT ON TABLE  jdhk.kingdee_transapply_entry                 IS '金蝶调拨申请单明细表';
COMMENT ON COLUMN jdhk.kingdee_transapply_entry.id              IS '明细行ID（金蝶内部ID）';
COMMENT ON COLUMN jdhk.kingdee_transapply_entry.bill_id         IS '关联主表 kingdee_transapply.id';
COMMENT ON COLUMN jdhk.kingdee_transapply_entry.material_number IS '物料编码';
COMMENT ON COLUMN jdhk.kingdee_transapply_entry.warehouse_number IS '调出仓库编码';
COMMENT ON COLUMN jdhk.kingdee_transapply_entry.qty             IS '调拨申请数量';
COMMENT ON COLUMN jdhk.kingdee_transapply_entry.transinqty      IS '已调入数量';
COMMENT ON COLUMN jdhk.kingdee_transapply_entry.transoutqty     IS '已调出数量';
COMMENT ON COLUMN jdhk.kingdee_transapply_entry.is_deleted      IS '软删除标记：TRUE=主单已在金蝶删除，随主表联动';
COMMENT ON COLUMN jdhk.kingdee_transapply_entry.deleted_at      IS '软删除时间（与主表同步写入）';
COMMENT ON COLUMN jdhk.kingdee_transapply_entry.sync_time       IS '最近一次同步时间';

-- 明细表索引
CREATE INDEX IF NOT EXISTS idx_transapply_entry_bill_id
    ON jdhk.kingdee_transapply_entry (bill_id);
CREATE INDEX IF NOT EXISTS idx_transapply_entry_material
    ON jdhk.kingdee_transapply_entry (material_number);
CREATE INDEX IF NOT EXISTS idx_transapply_entry_warehouse
    ON jdhk.kingdee_transapply_entry (warehouse_number);
CREATE INDEX IF NOT EXISTS idx_transapply_entry_lotnumber
    ON jdhk.kingdee_transapply_entry (lotnumber);
CREATE INDEX IF NOT EXISTS idx_transapply_entry_is_deleted
    ON jdhk.kingdee_transapply_entry (is_deleted)
    WHERE is_deleted = TRUE;


-- =============================================================
-- 迁移语句（已建表的环境执行，新建表无需执行）
-- =============================================================
-- ALTER TABLE jdhk.kingdee_transapply
--     ADD COLUMN IF NOT EXISTS is_deleted  BOOLEAN     DEFAULT FALSE,
--     ADD COLUMN IF NOT EXISTS deleted_at  TIMESTAMPTZ DEFAULT NULL;
--
-- CREATE INDEX IF NOT EXISTS idx_transapply_is_deleted
--     ON jdhk.kingdee_transapply (is_deleted)
--     WHERE is_deleted = TRUE;
--
-- ALTER TABLE jdhk.kingdee_transapply_entry
--     ADD COLUMN IF NOT EXISTS is_deleted  BOOLEAN     DEFAULT FALSE,
--     ADD COLUMN IF NOT EXISTS deleted_at  TIMESTAMPTZ DEFAULT NULL;
--
-- CREATE INDEX IF NOT EXISTS idx_transapply_entry_is_deleted
--     ON jdhk.kingdee_transapply_entry (is_deleted)
--     WHERE is_deleted = TRUE;
