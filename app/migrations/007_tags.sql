-- Migration 007: Tags and trade-tag association (Phase 4.3)

CREATE TABLE IF NOT EXISTS tags (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    group_name  TEXT NOT NULL DEFAULT 'general'
);

CREATE INDEX IF NOT EXISTS idx_tags_group ON tags(group_name);

CREATE TABLE IF NOT EXISTS trade_tags (
    trade_id    INTEGER NOT NULL,
    tag_id      INTEGER NOT NULL,
    PRIMARY KEY (trade_id, tag_id),
    FOREIGN KEY (trade_id) REFERENCES trades(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id)   REFERENCES tags(id)   ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_trade_tags_trade ON trade_tags(trade_id);
CREATE INDEX IF NOT EXISTS idx_trade_tags_tag   ON trade_tags(tag_id);
