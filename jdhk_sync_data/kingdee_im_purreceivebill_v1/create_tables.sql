-- =============================================================
-- 收料通知单（im_purreceivebill）数据表建表语句
-- API: /v2/im/im_purreceivebill/query
-- Schema: jdhk
--
-- 表结构说明：
--   1. kingdee_purreceivebill        — 单据主表（表头，L1 字段）
--   2. kingdee_purreceivebill_entry  — 单据明细表（表体，L2 字段）
--
-- 关联关系：
--   kingdee_purreceivebill_entry.bill_id → kingdee_purreceivebill.id
-- =============================================================

-- -------------------------------------------------------------
-- 1. 单据主表
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jdhk.kingdee_purreceivebill (
    id                          BIGINT          PRIMARY KEY,          -- 单据ID
    billno                      VARCHAR(100),                         -- 单据编号
    billstatus                  VARCHAR(10),                          -- 单据状态 [A:暂存, B:已提交, C:已审核]
    billstatus_title            VARCHAR(50),                          -- 单据状态标题
    auditdate                   TIMESTAMP,                            -- 审核时间
    modifytime                  TIMESTAMP,                            -- 修改时间
    createtime                  TIMESTAMP,                            -- 创建时间
    lastupdatetime              TIMESTAMP,                            -- 最后修改时间
    biztime                     DATE,                                 -- 业务日期
    bookdate                    DATE,                                 -- 记账日期
    exratedate                  DATE,                                 -- 汇率日期
    comment                     VARCHAR(200),                                 -- 备注
    isvirtualbill               BOOLEAN,                              -- 内部交易单据
    billcretype                 VARCHAR(10),                          -- 单据生成类型 [0:手工, 1:导入, 2:后台, 3:webApi]
    billcretype_title           VARCHAR(50),                          -- 单据生成类型标题
    asyncstatus                 VARCHAR(10),                          -- 异步状态 [A:处理中, B:完成]
    asyncstatus_title           VARCHAR(50),                          -- 异步状态标题
    ischargeoffed               BOOLEAN,                              -- 已冲销
    ischargeoff                 BOOLEAN,                              -- 冲销
    isvoucher                   BOOLEAN,                              -- 已生成凭证
    unitsrctype                 VARCHAR(60),                          -- 计量单位来源 [MAINBILLUNIT, BIZUNIT]
    unitsrctype_title           VARCHAR(100),                         -- 计量单位来源标题
    exchangerate                NUMERIC(20, 6),                       -- 汇率
    istax                       BOOLEAN,                              -- 含税
    hasapbusbill                BOOLEAN,                              -- 是否有应付业务单
    acceptancestatus            VARCHAR(10),                          -- 验收状态 [0:未验收, 1:已验收]
    acceptancestatus_title      VARCHAR(50),                          -- 验收状态标题
    paymode                     VARCHAR(20),                          -- 付款方式 [CASH:现购, CREDIT:赊购]
    paymode_title               VARCHAR(50),                          -- 付款方式标题
    quotation                   VARCHAR(10),                          -- 报价方式 [0:直接报价, 1:间接报价]
    quotation_title             VARCHAR(50),                          -- 报价方式标题
    closestatus                 VARCHAR(10),                          -- 关闭状态 [A:未关, B:已关闭]
    closestatus_title           VARCHAR(50),                          -- 关闭状态标题
    closedate                   TIMESTAMP,                            -- 关闭日期
    ischangeqty                 BOOLEAN,                              -- 是否改变量
    iswholediscount             BOOLEAN,                              -- 录入整单折扣
    wholediscountamount         NUMERIC(20, 4),                       -- 整单折扣额
    supplier_number             VARCHAR(100),                         -- 供应商编码
    bizoperator_operatorname    VARCHAR(200),                         -- 采购员名称
    sync_time                   TIMESTAMPTZ     DEFAULT NOW()         -- 同步时间
);

COMMENT ON TABLE  jdhk.kingdee_purreceivebill                       IS '金蝶收料通知单主表';
COMMENT ON COLUMN jdhk.kingdee_purreceivebill.id                    IS '单据ID（金蝶内部ID）';
COMMENT ON COLUMN jdhk.kingdee_purreceivebill.billno                IS '单据编号';
COMMENT ON COLUMN jdhk.kingdee_purreceivebill.billstatus            IS '单据状态：A=暂存，B=已提交，C=已审核';
COMMENT ON COLUMN jdhk.kingdee_purreceivebill.biztime               IS '业务日期';
COMMENT ON COLUMN jdhk.kingdee_purreceivebill.acceptancestatus      IS '验收状态：0=未验收，1=已验收';
COMMENT ON COLUMN jdhk.kingdee_purreceivebill.paymode               IS '付款方式：CASH=现购，CREDIT=赊购';
COMMENT ON COLUMN jdhk.kingdee_purreceivebill.closestatus           IS '关闭状态：A=未关，B=已关闭';
COMMENT ON COLUMN jdhk.kingdee_purreceivebill.supplier_number       IS '供应商编码';
COMMENT ON COLUMN jdhk.kingdee_purreceivebill.bizoperator_operatorname IS '采购员名称';
COMMENT ON COLUMN jdhk.kingdee_purreceivebill.sync_time             IS '最近一次同步时间';

-- 主表索引
CREATE INDEX IF NOT EXISTS idx_purreceivebill_billno
    ON jdhk.kingdee_purreceivebill (billno);
CREATE INDEX IF NOT EXISTS idx_purreceivebill_biztime
    ON jdhk.kingdee_purreceivebill (biztime);
CREATE INDEX IF NOT EXISTS idx_purreceivebill_modifytime
    ON jdhk.kingdee_purreceivebill (modifytime);
CREATE INDEX IF NOT EXISTS idx_purreceivebill_billstatus
    ON jdhk.kingdee_purreceivebill (billstatus);
CREATE INDEX IF NOT EXISTS idx_purreceivebill_supplier
    ON jdhk.kingdee_purreceivebill (supplier_number);


-- -------------------------------------------------------------
-- 2. 单据明细表
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jdhk.kingdee_purreceivebill_entry (
    id                          BIGINT          PRIMARY KEY,          -- 明细行ID
    bill_id                     BIGINT          NOT NULL,             -- 关联主表ID（外键）
    seq                         INTEGER,                              -- 行序号

    -- 物料 & 仓库
    material_number             VARCHAR(100),                         -- 物料编码
    materialname                VARCHAR(500),                         -- 物料名称（历史快照）
    warehouse_number            VARCHAR(100),                         -- 仓库编码

    -- 数量
    qty                         NUMERIC(20, 6),                       -- 数量
    qtyunit2nd                  NUMERIC(20, 6),                       -- 辅助数量
    qtyunit3rd                  NUMERIC(20, 6),                       -- 辅助数量(2)
    baseqty                     NUMERIC(20, 6),                       -- 基本数量
    purqty                      NUMERIC(20, 6),                       -- 采购数量

    -- 日期
    producedate                 DATE,                                 -- 生产日期
    expirydate                  DATE,                                 -- 有效日期
    acceptancedate              DATE,                                 -- 验收日期
    expectcompletedate          DATE,                                 -- 预计完成日期

    -- 批次 / 属性
    lotnumber                   VARCHAR(200),                         -- 批号
    suplot                      VARCHAR(200),                         -- 供应商批次
    auxpty                      VARCHAR(200),                                 -- 辅助属性
    serialnumber                VARCHAR(500),                         -- 序列号
    materialmasterid            BIGINT,                               -- 物料业务主数据标识
    noupdateinvfields           VARCHAR(200),                                 -- 不更新库存字段

    -- 货主 / 保管方
    ownertype                   VARCHAR(50),                          -- 货主类型 [bos_org, bd_supplier, bd_customer]
    keepertype                  VARCHAR(50),                          -- 保管方类型
    outownertype                VARCHAR(50),                          -- 转出货主类型
    outkeepertype               VARCHAR(50),                          -- 转出保管方类型

    -- 价格 / 金额
    price                       NUMERIC(20, 6),                       -- 单价
    priceandtax                 NUMERIC(20, 6),                       -- 含税单价
    taxrate                     NUMERIC(10, 4),                       -- 税率%
    discounttype                VARCHAR(10),                          -- 折扣方式 [A:折扣率, B:单位折扣额, NULL:无]
    discounttype_title          VARCHAR(50),                          -- 折扣方式标题
    discountrate                NUMERIC(20, 6),                       -- 单位折扣(率)
    amount                      NUMERIC(20, 4),                       -- 金额
    curamount                   NUMERIC(20, 4),                       -- 金额(本位币)
    taxamount                   NUMERIC(20, 4),                       -- 税额
    curtaxamount                NUMERIC(20, 4),                       -- 税额(本位币)
    discountamount              NUMERIC(20, 4),                       -- 折扣额
    amountandtax                NUMERIC(20, 4),                       -- 含税合计
    curamountandtax             NUMERIC(20, 4),                       -- 含税合计(本位币)
    actualprice                 NUMERIC(20, 6),                       -- 实际单价
    actualtaxprice              NUMERIC(20, 6),                       -- 实际含税单价

    -- 入库情况
    invqty                      NUMERIC(20, 6),                       -- 已入库数量
    remaininvqty                NUMERIC(20, 6),                       -- 未入库数量
    invbaseqty                  NUMERIC(20, 6),                       -- 已入库基本数量
    remaininvbaseqty            NUMERIC(20, 6),                       -- 未入库基本数量

    -- 对账情况
    verifyqty                   NUMERIC(20, 6),                       -- 已对账数量
    verifybaseqty               NUMERIC(20, 6),                       -- 已对账基本数量
    unverifyqty                 NUMERIC(20, 6),                       -- 未对账数量
    unverifybaseqty             NUMERIC(20, 6),                       -- 未对账基本数量

    -- 转购买情况
    purchasedqty                NUMERIC(20, 6),                       -- 已转购买数量
    remainpurqty                NUMERIC(20, 6),                       -- 未转购买数量
    purchasedbaseqty            NUMERIC(20, 6),                       -- 已转购买基本数量
    remainpurbaseqty            NUMERIC(20, 6),                       -- 未转购买基本数量
    purchasedamount             NUMERIC(20, 4),                       -- 已转购含税合计(本位币)
    remainpuramount             NUMERIC(20, 4),                       -- 未转购含税合计(本位币)

    -- 应计价数量
    joinpriceqty                NUMERIC(20, 6),                       -- 应计价数量
    joinpricebaseqty            NUMERIC(20, 6),                       -- 应计价基本数量
    remainjoinpriceqty          NUMERIC(20, 6),                       -- 剩余应计价数量
    remainjoinpricebaseqty      NUMERIC(20, 6),                       -- 剩余应计价基本数量

    -- 验收质检数量
    acceptanceentrystatus       VARCHAR(10),                          -- 行验收状态 [0:未验收, 1:已验收]
    acceptanceentrystatus_title VARCHAR(50),                          -- 行验收状态标题
    qualifiedqty                NUMERIC(20, 6),                       -- 合格数量
    qualifiedbaseqty            NUMERIC(20, 6),                       -- 合格基本数量
    qualifiedunit2nd            NUMERIC(20, 6),                       -- 合格数量(辅助单位)
    unqualifiedqty              NUMERIC(20, 6),                       -- 不合格数量
    unqualifiedunit2nd          NUMERIC(20, 6),                       -- 不合格数量(辅助单位)
    unqualifiedbaseqty          NUMERIC(20, 6),                       -- 不合格基本数量
    concessionqty               NUMERIC(20, 6),                       -- 让步接收数量
    concessionbaseqty           NUMERIC(20, 6),                       -- 让步接收基本数量

    -- 合格品退货
    totalreturnqty              NUMERIC(20, 6),                       -- 合格品退货数量
    totalreturnbaseqty          NUMERIC(20, 6),                       -- 合格品退货基本数量
    remainreturnqty             NUMERIC(20, 6),                       -- 合格品未退货数量
    remainreturnbaseqty         NUMERIC(20, 6),                       -- 合格品未退货基本数量
    returntype                  VARCHAR(10),                          -- 退货类型 [A:合格品退货, B:不合格品退货]
    returntype_title            VARCHAR(50),                          -- 退货类型标题
    returnmaterialtype          VARCHAR(10),                          -- 退料方式 [0:, 1:换料, 2:退采购]
    returnmaterialtype_title    VARCHAR(50),                          -- 退料方式标题

    -- 送检情况
    isinspect                   BOOLEAN,                              -- 需检验
    emrelease                   BOOLEAN,                              -- 紧急放行
    totalinspqty                NUMERIC(20, 6),                       -- 送检数量
    totalinspbaseqty            NUMERIC(20, 6),                       -- 送检基本数量
    leftinspqty                 NUMERIC(20, 6),                       -- 未送检数量
    leftinspbaseqty             NUMERIC(20, 6),                       -- 未送检基本数量

    -- 不合格品退货
    totalunqualreturnqty        NUMERIC(20, 6),                       -- 不合格品退货数量
    totalunqualreturnbaseqty    NUMERIC(20, 6),                       -- 不合格品退货基本数量
    leftunqualreturnqty         NUMERIC(20, 6),                       -- 不合格品未退货数量
    leftunqualreturnbaseqty     NUMERIC(20, 6),                       -- 不合格品未退货基本数量

    -- 损耗
    damageqty                   NUMERIC(20, 6),                       -- 采购损耗数量
    damagebaseqty               NUMERIC(20, 6),                       -- 采购损耗基本数量
    joinstockdamageqty          NUMERIC(20, 6),                       -- 累计库存采购损耗数量
    joinstockdamagebaseqty      NUMERIC(20, 6),                       -- 累计库存采购损耗基本数量
    rejectdiscountamount        NUMERIC(20, 4),                       -- 拒绝品折让金额
    joinrejectdiscountamount    NUMERIC(20, 4),                       -- 累计拒绝品折让金额

    -- 据供应单情况
    joinbusqty                  NUMERIC(20, 6),                       -- 据供应单据数量
    joinbusbaseqty              NUMERIC(20, 6),                       -- 据供应单据基本数量
    joinbusunwoffqty            NUMERIC(20, 6),                       -- 据供应单未核销数量
    joinbusunwoffbaseqty        NUMERIC(20, 6),                       -- 据供应单未核销基本数量

    -- 来源单据信息
    srcbillentity               VARCHAR(100),                         -- 来源单据实体
    srcbillid                   BIGINT,                               -- 来源单据ID
    srcbillentryid              BIGINT,                               -- 来源单据行ID
    srcbillnumber               VARCHAR(100),                         -- 来源单据编号
    srcbillentryseq             BIGINT,                               -- 来源单据分录序号
    srcsystem                   VARCHAR(100),                         -- 来源系统
    srcsysbillid                VARCHAR(100),                         -- 来源系统单据ID
    srcsysbillentryid           VARCHAR(100),                         -- 来源系统单据分录ID
    srcsysbillno                VARCHAR(100),                         -- 来源系统单据编号

    -- 主单据信息（关联主单）
    mainbillentity              VARCHAR(100),                         -- 主单据实体
    mainbillid                  BIGINT,                               -- 主单据ID
    mainbillnumber              VARCHAR(100),                         -- 主单据编号
    mainbillentryid             BIGINT,                               -- 主单据行ID
    mainbillentryseq            BIGINT,                               -- 主单据分录序号

    -- 采购订单关联
    purbillentryid              BIGINT,                               -- 采购单据行号
    purorderbillnumber          VARCHAR(100),                         -- 采购订单号

    -- 委外工单信息
    mftorderid                  BIGINT,                               -- 委外工单ID
    mftordernumber              VARCHAR(100),                         -- 委外工单号
    mftorderentryid             BIGINT,                               -- 委外工单行ID
    mftorderentryseq            BIGINT,                               -- 委外工单行序号
    producttype                 VARCHAR(10),                          -- 产品类型 [C:成品, A:半成品, B:副产品]
    producttype_title           VARCHAR(50),                          -- 产品类型标题

    -- 合同信息
    conbillentryid              BIGINT,                               -- 合同行ID
    conbillid                   BIGINT,                               -- 合同ID
    conbillrownum               VARCHAR(50),                          -- 合同行号
    conbillnumber               VARCHAR(100),                         -- 合同号
    conbillentity_id            VARCHAR(100),                         -- 合同实体ID

    -- 关闭状态 & 其他标记
    rowclosestatus              VARCHAR(10),                          -- 行关闭状态 [A:未关, B:已关闭]
    rowclosestatus_title        VARCHAR(50),                          -- 行关闭状态标题
    hasgenapbusbill             BOOLEAN,                              -- 已产生应付业务单
    logisticsbill               BOOLEAN,                              -- 组织业务单
    ispresent                   BOOLEAN,                              -- 赠品
    urgent                      BOOLEAN,                              -- 是否急件

    -- 供货信息
    provideraddress             VARCHAR(200),                         -- 供货地址
    entrycomment                VARCHAR(200),                                 -- 行备注

    sync_time                   TIMESTAMPTZ     DEFAULT NOW()         -- 同步时间
);

COMMENT ON TABLE  jdhk.kingdee_purreceivebill_entry                 IS '金蝶收料通知单明细表';
COMMENT ON COLUMN jdhk.kingdee_purreceivebill_entry.id              IS '明细行ID（金蝶内部ID）';
COMMENT ON COLUMN jdhk.kingdee_purreceivebill_entry.bill_id         IS '关联主表 kingdee_purreceivebill.id';
COMMENT ON COLUMN jdhk.kingdee_purreceivebill_entry.seq             IS '行序号';
COMMENT ON COLUMN jdhk.kingdee_purreceivebill_entry.material_number IS '物料编码';
COMMENT ON COLUMN jdhk.kingdee_purreceivebill_entry.warehouse_number IS '仓库编码';
COMMENT ON COLUMN jdhk.kingdee_purreceivebill_entry.qty             IS '收料数量';
COMMENT ON COLUMN jdhk.kingdee_purreceivebill_entry.invqty          IS '已入库数量';
COMMENT ON COLUMN jdhk.kingdee_purreceivebill_entry.purorderbillnumber IS '关联采购订单号';
COMMENT ON COLUMN jdhk.kingdee_purreceivebill_entry.sync_time       IS '最近一次同步时间';

-- 明细表索引
CREATE INDEX IF NOT EXISTS idx_purreceivebill_entry_bill_id
    ON jdhk.kingdee_purreceivebill_entry (bill_id);
CREATE INDEX IF NOT EXISTS idx_purreceivebill_entry_material
    ON jdhk.kingdee_purreceivebill_entry (material_number);
CREATE INDEX IF NOT EXISTS idx_purreceivebill_entry_warehouse
    ON jdhk.kingdee_purreceivebill_entry (warehouse_number);
CREATE INDEX IF NOT EXISTS idx_purreceivebill_entry_purorder
    ON jdhk.kingdee_purreceivebill_entry (purorderbillnumber);
CREATE INDEX IF NOT EXISTS idx_purreceivebill_entry_lotnumber
    ON jdhk.kingdee_purreceivebill_entry (lotnumber);
