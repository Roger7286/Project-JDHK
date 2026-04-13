-- =============================================================
-- 金蝶苍穹 采购收料单 建表语句
-- 接口：/v2/im/im_purreceivebill/query
-- 拆分为：单据头表 + 明细行表（主子表结构）
-- Schema：jdhk
-- =============================================================


-- -------------------------------------------------------------
-- 1. 单据头表
--    主键：id（金蝶单据内码，全局唯一）
--    唯一索引：billno（单据编号）
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jdhk.kingdee_pur_receivebill (

    -- 主键
    id                      VARCHAR(64)     NOT NULL,

    -- 单据基本信息
    billno                  VARCHAR(64),                    -- 单据编号
    billtype                VARCHAR(64),                    -- 单据类型内码
    billtype_number         VARCHAR(64),                    -- 单据类型编号
    billtype_name           VARCHAR(200),                   -- 单据类型名称
    billstatus              VARCHAR(10),                    -- 单据状态码 1=暂存 2=已提交 3=已审核 4=已关闭
    billstatus_name         VARCHAR(50),                    -- 单据状态名称

    -- 日期
    date                    DATE,                           -- 单据日期
    approvedate             DATE,                           -- 审核日期

    -- 业务组织
    org                     VARCHAR(64),                    -- 业务组织内码
    org_number              VARCHAR(64),                    -- 业务组织编号
    org_name                VARCHAR(200),                   -- 业务组织名称

    -- 仓储组织
    stockorg                VARCHAR(64),                    -- 仓储组织内码
    stockorg_number         VARCHAR(64),                    -- 仓储组织编号
    stockorg_name           VARCHAR(200),                   -- 仓储组织名称

    -- 供应商
    supplier                VARCHAR(64),                    -- 供应商内码
    supplier_number         VARCHAR(64),                    -- 供应商编号
    supplier_name           VARCHAR(200),                   -- 供应商名称

    -- 货主
    ownertype               VARCHAR(64),                    -- 货主类型
    owner                   VARCHAR(64),                    -- 货主内码
    owner_number            VARCHAR(64),                    -- 货主编号
    owner_name              VARCHAR(200),                   -- 货主名称

    -- 收料部门 / 操作人
    department              VARCHAR(64),                    -- 收料部门内码
    department_number       VARCHAR(64),                    -- 收料部门编号
    department_name         VARCHAR(200),                   -- 收料部门名称
    operator                VARCHAR(64),                    -- 操作人内码
    operator_number         VARCHAR(64),                    -- 操作人编号
    operator_name           VARCHAR(200),                   -- 操作人名称

    -- 审核人
    approver                VARCHAR(64),                    -- 审核人内码
    approver_number         VARCHAR(64),                    -- 审核人编号
    approver_name           VARCHAR(200),                   -- 审核人名称

    -- 采购员
    purchaser               VARCHAR(64),                    -- 采购员内码
    purchaser_number        VARCHAR(64),                    -- 采购员编号
    purchaser_name          VARCHAR(200),                   -- 采购员名称

    -- 来源单据类型
    srcbilltype             VARCHAR(64),                    -- 来源单据类型内码
    srcbilltype_name        VARCHAR(200),                   -- 来源单据类型名称

    -- 关联收料通知单
    receivenote             VARCHAR(64),                    -- 收料通知单内码
    receivenote_number      VARCHAR(64),                    -- 收料通知单编号

    -- 备注
    remark                  TEXT,

    -- 时间戳
    createtime              TIMESTAMP,                      -- 创建时间
    modifytime              TIMESTAMP,                      -- 最后修改时间
    sync_time               TIMESTAMP DEFAULT NOW(),        -- 同步时间

    CONSTRAINT pk_pur_receivebill PRIMARY KEY (id)
);

-- 常用查询索引
CREATE UNIQUE INDEX IF NOT EXISTS uix_pur_receivebill_billno
    ON jdhk.kingdee_pur_receivebill (billno);

CREATE INDEX IF NOT EXISTS ix_pur_receivebill_date
    ON jdhk.kingdee_pur_receivebill (date);

CREATE INDEX IF NOT EXISTS ix_pur_receivebill_approvedate
    ON jdhk.kingdee_pur_receivebill (approvedate);

CREATE INDEX IF NOT EXISTS ix_pur_receivebill_supplier
    ON jdhk.kingdee_pur_receivebill (supplier_number);

CREATE INDEX IF NOT EXISTS ix_pur_receivebill_org
    ON jdhk.kingdee_pur_receivebill (org_number);

CREATE INDEX IF NOT EXISTS ix_pur_receivebill_billstatus
    ON jdhk.kingdee_pur_receivebill (billstatus);

CREATE INDEX IF NOT EXISTS ix_pur_receivebill_modifytime
    ON jdhk.kingdee_pur_receivebill (modifytime);


-- -------------------------------------------------------------
-- 2. 明细行表
--    主键：id（明细行内码）
--    外键关联：bill_id -> kingdee_pur_receivebill.id
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jdhk.kingdee_pur_receivebill_entry (

    -- 主键（明细行内码）
    id                      VARCHAR(64)     NOT NULL,

    -- 关联单据头
    bill_id                 VARCHAR(64)     NOT NULL,       -- 单据头内码（FK）
    billno                  VARCHAR(64),                    -- 单据编号（冗余，方便查询）
    seq                     INTEGER,                        -- 行序号

    -- 物料
    material                VARCHAR(64),                    -- 物料内码
    material_number         VARCHAR(64),                    -- 物料编号
    material_name           VARCHAR(500),                   -- 物料名称
    material_modelnum       VARCHAR(200),                   -- 规格型号
    material_helpcode       VARCHAR(200),                   -- 助记码

    -- 物料分类
    materialgroup           VARCHAR(64),                    -- 物料分类内码
    materialgroup_number    VARCHAR(64),                    -- 物料分类编号
    materialgroup_name      VARCHAR(200),                   -- 物料分类名称

    -- 仓库 / 货位
    warehouse               VARCHAR(64),                    -- 仓库内码
    warehouse_number        VARCHAR(64),                    -- 仓库编号
    warehouse_name          VARCHAR(200),                   -- 仓库名称
    location                VARCHAR(64),                    -- 货位内码
    location_number         VARCHAR(64),                    -- 货位编号
    location_name           VARCHAR(200),                   -- 货位名称

    -- 计量单位
    unit                    VARCHAR(64),                    -- 计量单位内码
    unit_number             VARCHAR(64),                    -- 计量单位编号
    unit_name               VARCHAR(64),                    -- 计量单位名称

    -- 基本单位
    baseunit                VARCHAR(64),                    -- 基本单位内码
    baseunit_number         VARCHAR(64),                    -- 基本单位编号
    baseunit_name           VARCHAR(64),                    -- 基本单位名称

    -- 数量
    qty                     NUMERIC(20, 6),                 -- 应收数量（计量单位）
    baseqty                 NUMERIC(20, 6),                 -- 应收数量（基本单位）
    qty2nd                  NUMERIC(20, 6),                 -- 应收数量（第二计量）
    qty3rd                  NUMERIC(20, 6),                 -- 应收数量（第三计量）

    -- 实收数量
    actreceiveqty           NUMERIC(20, 6),                 -- 实收数量（计量单位）
    actreceivebaseqty       NUMERIC(20, 6),                 -- 实收数量（基本单位）

    -- 已开票 / 已结算
    invoicedqty             NUMERIC(20, 6),                 -- 已开票数量
    settleqty               NUMERIC(20, 6),                 -- 已结算数量

    -- 价格 / 金额
    price                   NUMERIC(20, 6),                 -- 单价（不含税）
    taxprice                NUMERIC(20, 6),                 -- 单价（含税）
    taxrate                 NUMERIC(10, 4),                 -- 税率（%）
    amount                  NUMERIC(20, 2),                 -- 金额（不含税）
    taxamount               NUMERIC(20, 2),                 -- 税额
    allamount               NUMERIC(20, 2),                 -- 价税合计

    -- 批次
    lot                     VARCHAR(64),                    -- 批次内码
    lot_number              VARCHAR(200),                   -- 批次号
    producedate             DATE,                           -- 生产日期
    expirydate              DATE,                           -- 到期日

    -- 库存状态
    invstatus               VARCHAR(64),                    -- 库存状态内码
    invstatus_number        VARCHAR(64),                    -- 库存状态编号
    invstatus_name          VARCHAR(200),                   -- 库存状态名称

    -- 辅助属性
    auxpty                  VARCHAR(64),                    -- 辅助属性内码

    -- 货主（行级）
    ownertype               VARCHAR(64),                    -- 货主类型
    owner                   VARCHAR(64),                    -- 货主内码
    owner_number            VARCHAR(64),                    -- 货主编号
    owner_name              VARCHAR(200),                   -- 货主名称

    -- 来源采购订单关联
    srcbillentryid          VARCHAR(64),                    -- 来源订单明细内码
    srcbillno               VARCHAR(64),                    -- 来源订单编号
    srcseq                  INTEGER,                        -- 来源订单行号

    -- 备注
    remark                  TEXT,

    -- 时间戳
    modifytime              TIMESTAMP,                      -- 最后修改时间
    sync_time               TIMESTAMP DEFAULT NOW(),        -- 同步时间

    CONSTRAINT pk_pur_receivebill_entry PRIMARY KEY (id)
);

-- 常用查询索引
CREATE INDEX IF NOT EXISTS ix_pur_entry_bill_id
    ON jdhk.kingdee_pur_receivebill_entry (bill_id);

CREATE INDEX IF NOT EXISTS ix_pur_entry_billno
    ON jdhk.kingdee_pur_receivebill_entry (billno);

CREATE INDEX IF NOT EXISTS ix_pur_entry_material
    ON jdhk.kingdee_pur_receivebill_entry (material_number);

CREATE INDEX IF NOT EXISTS ix_pur_entry_warehouse
    ON jdhk.kingdee_pur_receivebill_entry (warehouse_number);

CREATE INDEX IF NOT EXISTS ix_pur_entry_lot
    ON jdhk.kingdee_pur_receivebill_entry (lot_number);

CREATE INDEX IF NOT EXISTS ix_pur_entry_srcbillno
    ON jdhk.kingdee_pur_receivebill_entry (srcbillno);

CREATE INDEX IF NOT EXISTS ix_pur_entry_modifytime
    ON jdhk.kingdee_pur_receivebill_entry (modifytime);


-- -------------------------------------------------------------
-- 3. 外键约束（可选，按需启用）
--    如果需要严格约束，取消下面注释；
--    如果只做数据仓库宽松落库，可不加 FK。
-- -------------------------------------------------------------
-- ALTER TABLE jdhk.kingdee_pur_receivebill_entry
--     ADD CONSTRAINT fk_entry_bill
--     FOREIGN KEY (bill_id)
--     REFERENCES jdhk.kingdee_pur_receivebill (id)
--     ON DELETE CASCADE;


-- -------------------------------------------------------------
-- 4. 注释（可选，推荐执行）
-- -------------------------------------------------------------
COMMENT ON TABLE jdhk.kingdee_pur_receivebill       IS '金蝶苍穹采购收料单 - 单据头';
COMMENT ON TABLE jdhk.kingdee_pur_receivebill_entry IS '金蝶苍穹采购收料单 - 明细行';

COMMENT ON COLUMN jdhk.kingdee_pur_receivebill.id           IS '金蝶单据内码（主键）';
COMMENT ON COLUMN jdhk.kingdee_pur_receivebill.billno        IS '单据编号';
COMMENT ON COLUMN jdhk.kingdee_pur_receivebill.billstatus    IS '单据状态：1暂存 2已提交 3已审核 4已关闭';
COMMENT ON COLUMN jdhk.kingdee_pur_receivebill.sync_time     IS '最近同步时间（程序写入）';

COMMENT ON COLUMN jdhk.kingdee_pur_receivebill_entry.id         IS '明细行内码（主键）';
COMMENT ON COLUMN jdhk.kingdee_pur_receivebill_entry.bill_id    IS '关联单据头内码';
COMMENT ON COLUMN jdhk.kingdee_pur_receivebill_entry.billno     IS '单据编号（冗余）';
COMMENT ON COLUMN jdhk.kingdee_pur_receivebill_entry.qty        IS '应收数量（计量单位）';
COMMENT ON COLUMN jdhk.kingdee_pur_receivebill_entry.actreceiveqty IS '实收数量（计量单位）';
COMMENT ON COLUMN jdhk.kingdee_pur_receivebill_entry.sync_time  IS '最近同步时间（程序写入）';
