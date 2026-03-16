-- Migration 003: Category rules and import profiles (Phase 2)
-- Creates: category_rules, import_profiles

-- ============================================================
-- CATEGORY RULES
-- ============================================================

CREATE TABLE IF NOT EXISTS category_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    field       TEXT NOT NULL,                              -- 'name', 'description', 'notes'
    operator    TEXT NOT NULL DEFAULT 'contains',           -- 'contains', 'equals', 'starts_with'
    value       TEXT NOT NULL,                              -- Match pattern, e.g. 'Tesco'
    category    TEXT NOT NULL,                              -- Target category snake_case
    priority    INTEGER NOT NULL DEFAULT 0,                 -- Higher = checked first
    is_active   INTEGER NOT NULL DEFAULT 1,
    source      TEXT NOT NULL DEFAULT 'manual',             -- 'manual', 'learned' (auto-created on correction)
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (category) REFERENCES categories(name)
);

CREATE INDEX IF NOT EXISTS idx_category_rules_active
    ON category_rules(is_active, priority DESC);


-- ============================================================
-- IMPORT PROFILES
-- ============================================================

CREATE TABLE IF NOT EXISTS import_profiles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,                   -- 'Monzo', 'Starling', etc.
    file_type       TEXT NOT NULL DEFAULT 'csv',            -- csv, json
    column_mapping  TEXT NOT NULL,                          -- JSON: maps source columns to transaction fields
    date_format     TEXT,                                   -- strptime format string (NULL = ISO 8601)
    delimiter       TEXT NOT NULL DEFAULT ',',
    has_header      INTEGER NOT NULL DEFAULT 1,
    dedup_field     TEXT,                                   -- Column used for deduplication
    notes           TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
