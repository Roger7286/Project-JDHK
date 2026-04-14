"""
load_purreceivebill_to_pg.py
============================
职责：接收外部传入的原始 rows，拆分主表/明细并批量 upsert 到 PostgreSQL。
      【增减字段只需修改此文件中的映射函数】

对外暴露：
    upsert_rows(conn, rows) → tuple[int, int]
        将 rows（每条为一张单据）解析后写入主表和明细表。
        返回 (upserted_bills, upserted_entries)。

拆分逻辑：
    每条 API row 包含：
      - 主表字段（billno, billstatus, supplier_number 等）
      - billentry：list[dict]，明细行列表

写入策略：
    - 主表  ON CONFLICT (id)  → 全字段覆盖更新
    - 明细  ON CONFLICT (id)  → 全字段覆盖更新
    - 主表 upsert 完成后再 upsert 明细（保证 FK 引用已存在）

依赖：
    - psycopg2（数据库驱动）
    - config.py（由 main.py 传入连接，此文件不直接读取）
"""

import datetime
import psycopg2
import psycopg2.extras

# ---------- 目标表名 ----------
TABLE_BILL  = "jdhk.kingdee_purreceivebill"
TABLE_ENTRY = "jdhk.kingdee_purreceivebill_entry"


# =========================================================
# 辅助转换函数
# =========================================================

def _to_dt(val):
    """字符串 → datetime，None 安全。"""
    if not val:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(val, fmt)
        except ValueError:
            continue
    return None


def _to_date(val):
    """字符串 → date，None 安全。"""
    if not val:
        return None
    try:
        return datetime.datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _str(val):
    """转字符串，None 保持 None。"""
    return str(val) if val is not None else None


# =========================================================
# 主表字段映射：API row → PG dict
# ✏️  增减字段只改这里
# =========================================================

def _bill_to_pg(row: dict) -> dict:
    """将接口返回的单条 row（主表部分）映射为 PG 字段 dict。"""
    g = row.get

    return {
        "id":                           _str(g("id")),
        "billno":                       g("billno"),
        "billstatus":                   g("billstatus"),
        "billstatus_title":             g("billstatus_title"),
        "auditdate":                    _to_dt(g("auditdate")),
        "modifytime":                   _to_dt(g("modifytime")),
        "createtime":                   _to_dt(g("createtime")),
        "lastupdatetime":               _to_dt(g("lastupdatetime")),
        "biztime":                      _to_date(g("biztime")),
        "bookdate":                     _to_date(g("bookdate")),
        "exratedate":                   _to_date(g("exratedate")),
        "comment":                      g("comment"),
        "isvirtualbill":                g("isvirtualbill"),
        "billcretype":                  g("billcretype"),
        "billcretype_title":            g("billcretype_title"),
        "asyncstatus":                  g("asyncstatus"),
        "asyncstatus_title":            g("asyncstatus_title"),
        "ischargeoffed":                g("ischargeoffed"),
        "ischargeoff":                  g("ischargeoff"),
        "isvoucher":                    g("isvoucher"),
        "unitsrctype":                  g("unitsrctype"),
        "unitsrctype_title":            g("unitsrctype_title"),
        "exchangerate":                 g("exchangerate"),
        "istax":                        g("istax"),
        "hasapbusbill":                 g("hasapbusbill"),
        "acceptancestatus":             g("acceptancestatus"),
        "acceptancestatus_title":       g("acceptancestatus_title"),
        "paymode":                      g("paymode"),
        "paymode_title":                g("paymode_title"),
        "quotation":                    g("quotation"),
        "quotation_title":              g("quotation_title"),
        "closestatus":                  g("closestatus"),
        "closestatus_title":            g("closestatus_title"),
        "closedate":                    _to_dt(g("closedate")),
        "ischangeqty":                  g("ischangeqty"),
        "iswholediscount":              g("iswholediscount"),
        "wholediscountamount":          g("wholediscountamount"),
        "supplier_number":              g("supplier_number"),
        "bizoperator_operatorname":     g("bizoperator_operatorname"),
    }


# =========================================================
# 明细行字段映射：entry dict → PG dict
# ✏️  增减字段只改这里
# =========================================================

def _entry_to_pg(entry: dict, bill_id) -> dict:
    """将 billentry 中的单条明细行映射为 PG 字段 dict。"""
    g = entry.get

    return {
        "id":                           _str(g("id")),
        "bill_id":                      _str(bill_id),
        "seq":                          g("seq"),

        # 物料 & 仓库
        "material_number":              g("material_number"),
        "materialname":                 g("materialname"),
        "warehouse_number":             g("warehouse_number"),

        # 数量
        "qty":                          g("qty"),
        "qtyunit2nd":                   g("qtyunit2nd"),
        "qtyunit3rd":                   g("qtyunit3rd"),
        "baseqty":                      g("baseqty"),
        "purqty":                       g("purqty"),

        # 日期
        "producedate":                  _to_date(g("producedate")),
        "expirydate":                   _to_date(g("expirydate")),
        "acceptancedate":               _to_date(g("acceptancedate")),
        "expectcompletedate":           _to_date(g("expectcompletedate")),

        # 批次 / 属性
        "lotnumber":                    g("lotnumber"),
        "suplot":                       g("suplot"),
        "auxpty":                       _str(g("auxpty")),
        "serialnumber":                 g("serialnumber"),
        "materialmasterid":             _str(g("materialmasterid")),
        "noupdateinvfields":            g("noupdateinvfields"),

        # 货主 / 保管方
        "ownertype":                    g("ownertype"),
        "keepertype":                   g("keepertype"),
        "outownertype":                 g("outownertype"),
        "outkeepertype":                g("outkeepertype"),

        # 价格 / 金额
        "price":                        g("price"),
        "priceandtax":                  g("priceandtax"),
        "taxrate":                      g("taxrate"),
        "discounttype":                 g("discounttype"),
        "discounttype_title":           g("discounttype_title"),
        "discountrate":                 g("discountrate"),
        "amount":                       g("amount"),
        "curamount":                    g("curamount"),
        "taxamount":                    g("taxamount"),
        "curtaxamount":                 g("curtaxamount"),
        "discountamount":               g("discountamount"),
        "amountandtax":                 g("amountandtax"),
        "curamountandtax":              g("curamountandtax"),
        "actualprice":                  g("actualprice"),
        "actualtaxprice":               g("actualtaxprice"),

        # 入库情况
        "invqty":                       g("invqty"),
        "remaininvqty":                 g("remaininvqty"),
        "invbaseqty":                   g("invbaseqty"),
        "remaininvbaseqty":             g("remaininvbaseqty"),

        # 对账
        "verifyqty":                    g("verifyqty"),
        "verifybaseqty":                g("verifybaseqty"),
        "unverifyqty":                  g("unverifyqty"),
        "unverifybaseqty":              g("unverifybaseqty"),

        # 转购买
        "purchasedqty":                 g("purchasedqty"),
        "remainpurqty":                 g("remainpurqty"),
        "purchasedbaseqty":             g("purchasedbaseqty"),
        "remainpurbaseqty":             g("remainpurbaseqty"),
        "purchasedamount":              g("purchasedamount"),
        "remainpuramount":              g("remainpuramount"),

        # 应计价
        "joinpriceqty":                 g("joinpriceqty"),
        "joinpricebaseqty":             g("joinpricebaseqty"),
        "remainjoinpriceqty":           g("remainjoinpriceqty"),
        "remainjoinpricebaseqty":       g("remainjoinpricebaseqty"),

        # 验收质检
        "acceptanceentrystatus":        g("acceptanceentrystatus"),
        "acceptanceentrystatus_title":  g("acceptanceentrystatus_title"),
        "qualifiedqty":                 g("qualifiedqty"),
        "qualifiedbaseqty":             g("qualifiedbaseqty"),
        "qualifiedunit2nd":             g("qualifiedunit2nd"),
        "unqualifiedqty":               g("unqualifiedqty"),
        "unqualifiedunit2nd":           g("unqualifiedunit2nd"),
        "unqualifiedbaseqty":           g("unqualifiedbaseqty"),
        "concessionqty":                g("concessionqty"),
        "concessionbaseqty":            g("concessionbaseqty"),

        # 合格品退货
        "totalreturnqty":               g("totalreturnqty"),
        "totalreturnbaseqty":           g("totalreturnbaseqty"),
        "remainreturnqty":              g("remainreturnqty"),
        "remainreturnbaseqty":          g("remainreturnbaseqty"),
        "returntype":                   g("returntype"),
        "returntype_title":             g("returntype_title"),
        "returnmaterialtype":           g("returnmaterialtype"),
        "returnmaterialtype_title":     g("returnmaterialtype_title"),

        # 送检
        "isinspect":                    g("isinspect"),
        "emrelease":                    g("emrelease"),
        "totalinspqty":                 g("totalinspqty"),
        "totalinspbaseqty":             g("totalinspbaseqty"),
        "leftinspqty":                  g("leftinspqty"),
        "leftinspbaseqty":              g("leftinspbaseqty"),

        # 不合格品退货
        "totalunqualreturnqty":         g("totalunqualreturnqty"),
        "totalunqualreturnbaseqty":     g("totalunqualreturnbaseqty"),
        "leftunqualreturnqty":          g("leftunqualreturnqty"),
        "leftunqualreturnbaseqty":      g("leftunqualreturnbaseqty"),

        # 损耗
        "damageqty":                    g("damageqty"),
        "damagebaseqty":                g("damagebaseqty"),
        "joinstockdamageqty":           g("joinstockdamageqty"),
        "joinstockdamagebaseqty":       g("joinstockdamagebaseqty"),
        "rejectdiscountamount":         g("rejectdiscountamount"),
        "joinrejectdiscountamount":     g("joinrejectdiscountamount"),

        # 据供应单
        "joinbusqty":                   g("joinbusqty"),
        "joinbusbaseqty":               g("joinbusbaseqty"),
        "joinbusunwoffqty":             g("joinbusunwoffqty"),
        "joinbusunwoffbaseqty":         g("joinbusunwoffbaseqty"),

        # 来源单据
        "srcbillentity":                g("srcbillentity"),
        "srcbillid":                    _str(g("srcbillid")),
        "srcbillentryid":               _str(g("srcbillentryid")),
        "srcbillnumber":                g("srcbillnumber"),
        "srcbillentryseq":              _str(g("srcbillentryseq")),
        "srcsystem":                    g("srcsystem"),
        "srcsysbillid":                 g("srcsysbillid"),
        "srcsysbillentryid":            g("srcsysbillentryid"),
        "srcsysbillno":                 g("srcsysbillno"),

        # 主单据
        "mainbillentity":               g("mainbillentity"),
        "mainbillid":                   _str(g("mainbillid")),
        "mainbillnumber":               g("mainbillnumber"),
        "mainbillentryid":              _str(g("mainbillentryid")),
        "mainbillentryseq":             _str(g("mainbillentryseq")),

        # 采购订单
        "purbillentryid":               _str(g("purbillentryid")),
        "purorderbillnumber":           g("purorderbillnumber"),

        # 委外工单
        "mftorderid":                   _str(g("mftorderid")),
        "mftordernumber":               g("mftordernumber"),
        "mftorderentryid":              _str(g("mftorderentryid")),
        "mftorderentryseq":             _str(g("mftorderentryseq")),
        "producttype":                  g("producttype"),
        "producttype_title":            g("producttype_title"),

        # 合同
        "conbillentryid":               _str(g("conbillentryid")),
        "conbillid":                    _str(g("conbillid")),
        "conbillrownum":                g("conbillrownum"),
        "conbillnumber":                g("conbillnumber"),
        "conbillentity_id":             g("conbillentity_id"),

        # 标记 & 其他
        "rowclosestatus":               g("rowclosestatus"),
        "rowclosestatus_title":         g("rowclosestatus_title"),
        "hasgenapbusbill":              g("hasgenapbusbill"),
        "logisticsbill":                g("logisticsbill"),
        "ispresent":                    g("ispresent"),
        "urgent":                       g("urgent"),
        "provideraddress":              g("provideraddress"),
        "entrycomment":                 g("entrycomment"),
    }


# =========================================================
# 动态生成 Upsert SQL
# =========================================================

def _build_upsert_sql(table: str, columns: list) -> str:
    """根据表名和字段列表动态生成 INSERT ... ON CONFLICT (id) DO UPDATE 语句。"""
    col_list   = ", ".join(columns)
    val_list   = ", ".join([f"%({c})s" for c in columns])
    update_set = ", ".join([f"{c} = EXCLUDED.{c}" for c in columns if c != "id"])
    return f"""
        INSERT INTO {table} ({col_list}, sync_time)
        VALUES ({val_list}, NOW())
        ON CONFLICT (id) DO UPDATE
        SET {update_set},
            sync_time = NOW()
    """


# =========================================================
# 批量 Upsert（对外接口）
# =========================================================

def upsert_rows(conn, rows: list) -> tuple:
    """
    将 rows 批量 upsert 到主表和明细表。

    参数：
        conn  psycopg2 连接对象
        rows  list[dict]，fetch_purreceivebill.fetch_all_pages() 的返回值
              每个 dict 代表一张收料通知单，内含 billentry 列表。

    返回：
        (int, int)  (写入主表行数, 写入明细行数)
    """
    if not rows:
        print("[PG] 无数据需要写入。")
        return 0, 0

    # ── 1. 构建主表和明细行数据 ──────────────────────────────
    bill_rows  = []
    entry_rows = []

    for row in rows:
        bill_id = row.get("id")
        bill_rows.append(_bill_to_pg(row))

        entries = row.get("billentry") or []
        for entry in entries:
            entry_rows.append(_entry_to_pg(entry, bill_id))

    # ── 2. Upsert 主表 ────────────────────────────────────────
    bill_columns = list(bill_rows[0].keys())
    bill_sql     = _build_upsert_sql(TABLE_BILL, bill_columns)

    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, bill_sql, bill_rows, page_size=500)
    conn.commit()
    print(f"[PG] 主表 upsert {len(bill_rows)} 条。")

    # ── 3. Upsert 明细（主表已落库后，FK 引用安全） ────────────
    entry_count = 0
    if entry_rows:
        entry_columns = list(entry_rows[0].keys())
        entry_sql     = _build_upsert_sql(TABLE_ENTRY, entry_columns)

        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, entry_sql, entry_rows, page_size=500)
        conn.commit()
        entry_count = len(entry_rows)
        print(f"[PG] 明细表 upsert {entry_count} 条。")
    else:
        print("[PG] 本批次无明细行数据。")

    return len(bill_rows), entry_count
