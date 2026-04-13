-- =========================================================
-- 金蝶销售订单 → PostgreSQL 建表语句（完整版）
-- 接口: /v2/sm/sm_salorder/query
-- 文档: https://dev.kingdee.com/open/detail/api/1769178924861893632
--
-- 表结构（三张表，层级关系）：
--   sm_salorder               — 销售订单主表（单据头）
--     └─ sm_salorder_entry    — 销售订单明细行（billentry）
--          └─ sm_salorder_deliver_entry — 交货计划子行（orderdeliverentry）
--
-- 说明：
--   auxpty 为弹性域字段，key 为弹性域名称（中文），value 为对象或字符串，
--   结构不固定，采用 JSONB 列存储，便于灵活查询。
--
-- 主键均使用金蝶返回的 id（BIGINT）
-- sync_time 为同步写入时间，由程序自动写入 NOW()
-- =========================================================

-- ---------------------------------------------------------
-- 1. 销售订单主表（单据头）
--    对应接口 rows[] 顶层字段
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS sm_salorder (

-- ===== 单据基本标识 =====
id BIGINT PRIMARY KEY, -- 金蝶内部 ID
billno VARCHAR(100), -- 单据编号，如 XSDD202406240001
billstatus VARCHAR(10), -- 单据状态：A=保存 B=提交 C=审核
billstatusname VARCHAR(50), -- 单据状态名称（文字）
closestatus VARCHAR(10), -- 关闭状态
closedate TIMESTAMP, -- 关闭时间
changestatus VARCHAR(10), -- 变更状态
changedate TIMESTAMP, -- 变更时间

-- ===== 业务日期 =====
bizdate DATE, -- 业务日期（订单日期）
auditdate TIMESTAMP, -- 审核时间
createtime TIMESTAMP, -- 创建时间
modifytime TIMESTAMP, -- 最后修改时间

-- ===== 单据类型 =====
billtype BIGINT, -- 单据类型 ID
billtype_number VARCHAR(100),
billtype_name VARCHAR(200),
biztype BIGINT, -- 业务类型 ID
biztype_number VARCHAR(100),
biztype_name VARCHAR(200),
billcretype VARCHAR(50), -- 单据创建方式
billsource VARCHAR(50), -- 单据来源

-- ===== 销售组织 / 结算组织 =====
org BIGINT, -- 销售组织 ID（结算组织）
org_number VARCHAR(100),
org_name VARCHAR(200),

-- ===== 客户 =====
customer BIGINT,
customer_number VARCHAR(100),
customer_name VARCHAR(200),

-- ===== 部门 =====
dept BIGINT,
dept_number VARCHAR(100),
dept_name VARCHAR(200),

-- ===== 业务员 =====
salesman BIGINT,
salesman_number VARCHAR(100),
salesman_name VARCHAR(200),

-- ===== 操作人 =====
operator BIGINT,
operator_number VARCHAR(100),
operator_name VARCHAR(200),

-- ===== 创建人 / 修改人 / 审核人 / 变更人 =====
creator BIGINT,
creator_number VARCHAR(100),
creator_name VARCHAR(200),
modifier BIGINT,
modifier_number VARCHAR(100),
modifier_name VARCHAR(200),
auditor BIGINT,
auditor_number VARCHAR(100),
auditor_name VARCHAR(200),
changer BIGINT,
changer_number VARCHAR(100),
changer_name VARCHAR(200),

-- ===== 币别 / 汇率 =====
settlecurrency BIGINT,
settlecurrency_number VARCHAR(50),
settlecurrency_name VARCHAR(100),
exchangerate NUMERIC(18, 8),
exchangetype VARCHAR(10), -- 汇率类型

-- ===== 价格表 / 收款条件 =====
pricelist BIGINT,
pricelist_number VARCHAR(100),
pricelist_name VARCHAR(200),
reccondition BIGINT, -- 收款条件
reccondition_number VARCHAR(100),
reccondition_name VARCHAR(200),

-- ===== 含税标志 =====
istax BOOLEAN, -- 是否含税

-- ===== 金额合计 =====
totalamount NUMERIC(24, 6), -- 不含税总金额
totaltaxamount NUMERIC(24, 6), -- 税额合计
totalallamount NUMERIC(24, 6), -- 价税合计
prereceiptamount NUMERIC(24, 6), -- 预收款金额
receiptamount NUMERIC(24, 6), -- 已收款金额

-- ===== 付款方式 =====
paymode VARCHAR(50), -- 付款方式

-- ===== 收货 / 联系人 =====
receiveaddress VARCHAR(500), -- 收货地址（文本）
address VARCHAR(500), -- 地址
comment TEXT, -- 备注/摘要
deliveryway BIGINT, -- 发货方式 ID
deliveryway_number VARCHAR(100),
deliveryway_name VARCHAR(200),
deliveraddressf7 BIGINT, -- 收货地址(F7) ID
deliveraddressf7_number VARCHAR(200),
deliveraddressf7_name VARCHAR(500),

-- ===== 联系人 =====
linkman VARCHAR(200),
reclinkman VARCHAR(200),

-- ===== 同步时间 =====
sync_time TIMESTAMP NOT NULL DEFAULT NOW() );

COMMENT ON TABLE sm_salorder IS '金蝶销售订单主表（单据头）';

COMMENT ON COLUMN sm_salorder.id IS '金蝶内部 ID';

COMMENT ON COLUMN sm_salorder.billno IS '单据编号';

COMMENT ON COLUMN sm_salorder.billstatus IS '单据状态：A=保存 B=提交 C=审核';

COMMENT ON COLUMN sm_salorder.bizdate IS '业务日期（订单日期）';

COMMENT ON COLUMN sm_salorder.totalamount IS '不含税总金额';

COMMENT ON COLUMN sm_salorder.totaltaxamount IS '税额合计';

COMMENT ON COLUMN sm_salorder.totalallamount IS '价税合计';

COMMENT ON COLUMN sm_salorder.istax IS '是否含税';

COMMENT ON COLUMN sm_salorder.prereceiptamount IS '预收款金额';

COMMENT ON COLUMN sm_salorder.receiptamount IS '已收款金额';

COMMENT ON COLUMN sm_salorder.sync_time IS '最后同步时间（程序写入）';

-- 常用查询索引
CREATE INDEX IF NOT EXISTS idx_sm_salorder_billno ON sm_salorder (billno);

CREATE INDEX IF NOT EXISTS idx_sm_salorder_bizdate ON sm_salorder (bizdate);

CREATE INDEX IF NOT EXISTS idx_sm_salorder_modifytime ON sm_salorder (modifytime);

CREATE INDEX IF NOT EXISTS idx_sm_salorder_billstatus ON sm_salorder (billstatus);

CREATE INDEX IF NOT EXISTS idx_sm_salorder_customer ON sm_salorder (customer_number);

CREATE INDEX IF NOT EXISTS idx_sm_salorder_org ON sm_salorder (org_number);

CREATE INDEX IF NOT EXISTS idx_sm_salorder_auditdate ON sm_salorder (auditdate);

CREATE INDEX IF NOT EXISTS idx_sm_salorder_closestatus ON sm_salorder (closestatus);

-- ---------------------------------------------------------
-- 2. 销售订单明细行（billentry）
--    每张主表对应 1..N 条明细行
--    auxpty（弹性域）因 key 为弹性域名称（中文）且结构不固定，
--    整体存为 JSONB；其余字段均做结构化映射。
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS sm_salorder_entry (

-- ===== 行标识 =====
id BIGINT PRIMARY KEY, -- 金蝶明细行 ID
order_id BIGINT NOT NULL REFERENCES sm_salorder (id) ON DELETE CASCADE,
seq INT, -- 行序号（API 返回的 seq 字段）

-- ===== 物料 =====
material BIGINT, -- 物料内部 ID（material_id）
material_number VARCHAR(200), -- 物料编码（material_masterid_number）
material_name VARCHAR(500), -- 物料名称（material_masterid_name）
material_modelnum VARCHAR(500), -- 规格型号（material_masterid_modelnum）
materialversion BIGINT, -- 物料版本 ID
materialversion_number VARCHAR(100),
materialversion_name VARCHAR(200),

-- ===== 辅助属性（弹性域）=====
-- auxpty 在 API 返回中以 "弹性域名称" 为 key，value 为对象({id,number,name})
-- 或字符串（其他类型），结构由业务配置决定，使用 JSONB 灵活存储
auxpty JSONB, -- 弹性域整体 JSON；另见 auxpty_id
auxpty_id BIGINT, -- auxpty.id（辅助属性组 ID）

-- ===== 数量 / 库存单位 =====
unit BIGINT,
unit_number VARCHAR(50),
unit_name VARCHAR(100),
qty NUMERIC(24, 6), -- 数量（库存单位）

-- ===== 辅助数量 / 辅助单位 =====
auxunit BIGINT,
auxunit_number VARCHAR(50),
auxunit_name VARCHAR(100),
auxqty NUMERIC(24, 6), -- 辅助数量

-- ===== 基本单位 =====
baseqty NUMERIC(24, 6), -- 基本单位数量

-- ===== 价格 =====
price NUMERIC(24, 8), -- 不含税单价
priceandtax NUMERIC(24, 8), -- 含税单价
discounttype VARCHAR(50), -- 折扣类型
discountrate NUMERIC(10, 6), -- 折扣率 (%)

-- ===== 税率 =====
taxrateid BIGINT,
taxrateid_number VARCHAR(50),
taxrateid_name VARCHAR(100),

-- ===== 金额 =====
taxamount NUMERIC(24, 6), -- 税额
curtaxamount NUMERIC(24, 6), -- 本币税额
curamount NUMERIC(24, 6), -- 本币不含税金额
amount NUMERIC(24, 6), -- 不含税金额（原币）
discountamount NUMERIC(24, 6), -- 折扣金额
amountandtax NUMERIC(24, 6), -- 含税金额（原币）
curamountandtax NUMERIC(24, 6), -- 本币含税金额

-- ===== 库存组织 =====
e_stockorg BIGINT,
e_stockorg_number VARCHAR(100),
e_stockorg_name VARCHAR(200),

-- ===== 仓库 =====
warehouse BIGINT,
warehouse_number VARCHAR(100),
warehouse_name VARCHAR(200),

-- ===== 货位 =====
location BIGINT,
location_number VARCHAR(100),
location_name VARCHAR(200),

-- ===== 货主 =====
ownertype VARCHAR(50),
owner BIGINT,
owner_number VARCHAR(100),
owner_name VARCHAR(200),

-- ===== 结算组织（行级）=====
entrysettleorg BIGINT,
entrysettleorg_number VARCHAR(100),
entrysettleorg_name VARCHAR(200),

-- ===== 交货控制 =====
deliverydate DATE, -- 计划交货日期（行级）
iscontrolday BOOLEAN, -- 是否按天控制
deliveradvdays INT, -- 提前交货天数
deliverdelaydays INT, -- 延迟交货天数
ispresent BOOLEAN, -- 是否赠品
iscontrolqty BOOLEAN, -- 是否控制数量

-- ===== 交货进度 =====
deliveratedown NUMERIC(10, 6), -- 交货率下限
deliverateup NUMERIC(10, 6), -- 交货率上限
deliverqtydown NUMERIC(24, 6), -- 可交货数量下限
deliverqtyup NUMERIC(24, 6), -- 可交货数量上限

-- ===== 批次 / 批号 =====
lotnumber VARCHAR(200), -- 批号

-- ===== 项目 =====
project BIGINT,
project_number VARCHAR(100),
project_name VARCHAR(200),

-- ===== 来源合同 =====
conbillnumber VARCHAR(100), -- 来源合同单据号
conbillrownum VARCHAR(50), -- 来源合同行号

-- ===== 关闭 / 终止状态 =====
rowclosestatus VARCHAR(10), -- 行关闭状态
rowterminatestatus VARCHAR(10), -- 行终止状态

-- ===== 同步时间 =====
sync_time TIMESTAMP NOT NULL DEFAULT NOW() );

COMMENT ON
TABLE sm_salorder_entry IS '金蝶销售订单明细行（billentry）';

COMMENT ON COLUMN sm_salorder_entry.id IS '金蝶明细行内部 ID';

COMMENT ON COLUMN sm_salorder_entry.order_id IS '关联主表 ID（sm_salorder.id）';

COMMENT ON COLUMN sm_salorder_entry.seq IS '行序号（API seq 字段）';

COMMENT ON COLUMN sm_salorder_entry.auxpty IS '弹性域辅助属性（JSONB，key=弹性域名称）';

COMMENT ON COLUMN sm_salorder_entry.auxpty_id IS '辅助属性组 ID';

COMMENT ON COLUMN sm_salorder_entry.price IS '不含税单价（原币）';

COMMENT ON COLUMN sm_salorder_entry.priceandtax IS '含税单价（原币）';

COMMENT ON COLUMN sm_salorder_entry.amount IS '不含税金额（原币）';

COMMENT ON COLUMN sm_salorder_entry.amountandtax IS '含税金额（原币）';

COMMENT ON COLUMN sm_salorder_entry.curamount IS '本币不含税金额';

COMMENT ON COLUMN sm_salorder_entry.curamountandtax IS '本币含税金额';

COMMENT ON COLUMN sm_salorder_entry.deliveratedown IS '交货率下限（%）';

COMMENT ON COLUMN sm_salorder_entry.deliverateup IS '交货率上限（%）';

COMMENT ON COLUMN sm_salorder_entry.sync_time IS '最后同步时间（程序写入）';

CREATE INDEX IF NOT EXISTS idx_sm_salorder_entry_order_id ON sm_salorder_entry (order_id);

CREATE INDEX IF NOT EXISTS idx_sm_salorder_entry_material ON sm_salorder_entry (material_number);

CREATE INDEX IF NOT EXISTS idx_sm_salorder_entry_warehouse ON sm_salorder_entry (warehouse_number);

CREATE INDEX IF NOT EXISTS idx_sm_salorder_entry_delivery ON sm_salorder_entry (deliverydate);

CREATE INDEX IF NOT EXISTS idx_sm_salorder_entry_seq ON sm_salorder_entry (order_id, seq);

CREATE INDEX IF NOT EXISTS idx_sm_salorder_entry_auxpty ON sm_salorder_entry USING GIN (auxpty);

-- ---------------------------------------------------------
-- 3. 交货计划子表（orderdeliverentry）
--    每条明细行对应 0..N 条交货计划（d_ 前缀字段）
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS sm_salorder_deliver_entry (

-- ===== 行标识 =====
id VARCHAR(100) PRIMARY KEY, -- 金蝶交货计划 ID（或合成 entry_id_seq）
entry_id BIGINT NOT NULL REFERENCES sm_salorder_entry (id) ON DELETE CASCADE,
order_id BIGINT NOT NULL, -- 冗余 FK，便于查询（sm_salorder.id）
seq INT NOT NULL, -- 计划行序号（从 1 开始）

-- ===== 收货地址 =====
d_receiveaddress VARCHAR(500), -- 收货地址（文本）
d_receiveaddressf7 BIGINT, -- 收货地址(F7) ID
d_receiveaddressf7_number VARCHAR(200), -- 收货地址(F7) 编码
d_receiveaddressf7_name VARCHAR(500), -- 收货地址(F7) 名称

-- ===== 计划交货 =====
d_plandate DATE, -- 计划日期
d_plandeliverydate DATE, -- 计划发货日期
d_transportleadtime INT, -- 运输提前期（天）

-- ===== 计划数量 =====
d_planqty NUMERIC(24, 6), -- 计划发货数量（库存单位）
d_planbaseqty NUMERIC(24, 6), -- 计划基本数量（基本单位）

-- ===== 计划单位 =====
d_planunit BIGINT,
d_planunit_number VARCHAR(50), -- 计划单位 编码
d_planunit_name VARCHAR(100), -- 计划单位 名称

-- ===== 备注 =====
d_remark TEXT, -- 备注

-- ===== 同步时间 =====
sync_time TIMESTAMP NOT NULL DEFAULT NOW() );

COMMENT ON
TABLE sm_salorder_deliver_entry IS '金蝶销售订单交货计划子表（orderdeliverentry）';

COMMENT ON COLUMN sm_salorder_deliver_entry.id IS '计划行 ID（金蝶 ID 或合成 entry_id_seq）';

COMMENT ON COLUMN sm_salorder_deliver_entry.entry_id IS '关联明细行 ID（sm_salorder_entry.id）';

COMMENT ON COLUMN sm_salorder_deliver_entry.order_id IS '关联主表 ID（冗余，sm_salorder.id）';

COMMENT ON COLUMN sm_salorder_deliver_entry.d_receiveaddress IS '收货地址文本';

COMMENT ON COLUMN sm_salorder_deliver_entry.d_receiveaddressf7_number IS '收货地址(F7) 编码';

COMMENT ON COLUMN sm_salorder_deliver_entry.d_plandate IS '计划日期';

COMMENT ON COLUMN sm_salorder_deliver_entry.d_plandeliverydate IS '计划发货日期';

COMMENT ON COLUMN sm_salorder_deliver_entry.d_transportleadtime IS '运输提前期（天）';

COMMENT ON COLUMN sm_salorder_deliver_entry.d_planqty IS '计划发货数量（库存单位）';

COMMENT ON COLUMN sm_salorder_deliver_entry.d_planbaseqty IS '计划基本数量（基本单位）';

COMMENT ON COLUMN sm_salorder_deliver_entry.d_remark IS '备注';

COMMENT ON COLUMN sm_salorder_deliver_entry.sync_time IS '最后同步时间（程序写入）';

CREATE INDEX IF NOT EXISTS idx_sm_deliver_entry_entry_id ON sm_salorder_deliver_entry (entry_id);

CREATE INDEX IF NOT EXISTS idx_sm_deliver_entry_order_id ON sm_salorder_deliver_entry (order_id);

CREATE INDEX IF NOT EXISTS idx_sm_deliver_entry_plandate ON sm_salorder_deliver_entry (d_plandeliverydate);

-- ---------------------------------------------------------
-- 常用视图：展平三表为宽表
-- ---------------------------------------------------------
CREATE OR REPLACE VIEW v_sm_salorder_flat AS
SELECT
    -- 主表
    h.id AS order_id,
    h.billno,
    h.billstatus,
    h.billstatusname,
    h.bizdate,
    h.auditdate,
    h.modifytime,
    h.closestatus,
    h.org_number,
    h.org_name,
    h.customer_number,
    h.customer_name,
    h.dept_name,
    h.salesman_name,
    h.settlecurrency_number,
    h.exchangerate,
    h.istax,
    h.totalamount,
    h.totaltaxamount,
    h.totalallamount,
    h.paymode,
    h.receiveaddress,

-- 明细行
e.id AS entry_id,
e.seq AS entry_seq,
e.material_number,
e.material_name,
e.material_modelnum,
e.unit_name,
e.qty,
e.auxqty,
e.auxunit_name,
e.baseqty,
e.price,
e.priceandtax,
e.taxrateid_number,
e.amount,
e.taxamount,
e.amountandtax,
e.curamount,
e.curamountandtax,
e.discountrate,
e.e_stockorg_number,
e.warehouse_number,
e.warehouse_name,
e.lotnumber,
e.deliverydate AS entry_deliverydate,
e.deliverqtyup,
e.rowclosestatus,
e.rowterminatestatus,
e.auxpty,

-- 交货计划
d.id AS deliver_id,
d.seq AS deliver_seq,
d.d_plandeliverydate,
d.d_planqty,
d.d_planbaseqty,
d.d_planunit_name,
d.d_transportleadtime,
d.d_receiveaddressf7_name,
d.d_remark
FROM
    sm_salorder h
    JOIN sm_salorder_entry e ON e.order_id = h.id
    LEFT JOIN sm_salorder_deliver_entry d ON d.entry_id = e.id;

COMMENT ON VIEW v_sm_salorder_flat IS '销售订单三表展平视图（主表+明细+交货计划）';