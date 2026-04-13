-- =========================================================
-- sync_state：同步状态记录表
--
-- 用途：记录每个 API / 目标表的最后同步时间
-- 主键：(api_name, table_name) 联合唯一
-- 更新策略：每次同步完成后 UPSERT 一条记录
-- =========================================================

CREATE TABLE IF NOT EXISTS sync_state (
    api_name        VARCHAR(200)  NOT NULL,          -- 调用的 API 路径或名称
    table_name      VARCHAR(200)  NOT NULL,          -- 目标表名
    last_sync_time  TIMESTAMP     NOT NULL,          -- 本次同步完成时间
    sync_rows       INTEGER       DEFAULT 0,         -- 本次同步写入/更新的行数
    modifytime_start VARCHAR(30)  DEFAULT NULL,      -- 本次同步使用的起始时间（增量）
    modifytime_end   VARCHAR(30)  DEFAULT NULL,      -- 本次同步使用的结束时间（增量）
    created_at      TIMESTAMP     DEFAULT NOW(),     -- 首次记录时间
    updated_at      TIMESTAMP     DEFAULT NOW(),     -- 最近更新时间

    PRIMARY KEY (api_name, table_name)
);

-- 注释
COMMENT ON TABLE  sync_state                  IS '数据同步状态记录表';
COMMENT ON COLUMN sync_state.api_name         IS '调用的 API 路径，例如 /v2/im/getInventoryDetail';
COMMENT ON COLUMN sync_state.table_name       IS '数据写入的目标表名';
COMMENT ON COLUMN sync_state.last_sync_time   IS '最近一次同步完成的时间';
COMMENT ON COLUMN sync_state.sync_rows        IS '最近一次同步写入/更新的总行数';
COMMENT ON COLUMN sync_state.modifytime_start IS '最近一次同步使用的增量起始时间（全量同步时为 NULL）';
COMMENT ON COLUMN sync_state.modifytime_end   IS '最近一次同步使用的增量结束时间（全量同步时为 NULL）';
COMMENT ON COLUMN sync_state.created_at       IS '该记录首次创建时间';
COMMENT ON COLUMN sync_state.updated_at       IS '该记录最近更新时间';
