-- Migration 001: Initial schema
-- Creates: transactions, categories
-- schema_version is managed by the migration runner in db.py


-- ============================================================
-- TRANSACTIONS (personal finance)
-- ============================================================

CREATE TABLE IF NOT EXISTS transactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    monzo_id        TEXT UNIQUE,                           -- Monzo Transaction ID (for dedup)
    date            TEXT NOT NULL,                          -- ISO 8601: 2024-01-15T12:20:18Z
    type            TEXT,                                   -- Card payment, Faster payment, etc.
    name            TEXT NOT NULL,                          -- Display name / merchant
    emoji           TEXT,                                   -- Monzo emoji
    category        TEXT NOT NULL DEFAULT 'general',        -- snake_case: eating_out, groceries
    amount          INTEGER NOT NULL,                        -- Signed pence (negative = debit). £5.10 = 510
    currency        TEXT NOT NULL DEFAULT 'GBP',
    local_amount    INTEGER,                                -- Foreign currency amount in minor units
    local_currency  TEXT,                                   -- Foreign currency code
    notes           TEXT,                                   -- Notes and #tags
    address         TEXT,
    description     TEXT,                                   -- Raw merchant string
    is_income       INTEGER NOT NULL DEFAULT 0,             -- 1 if credit, 0 if debit
    custom_category TEXT,                                   -- User override of Monzo category
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_transactions_date     ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_transactions_amount   ON transactions(amount);


-- ============================================================
-- CATEGORIES
-- ============================================================

CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,                       -- snake_case key
    label       TEXT NOT NULL,                              -- Display name: "Eating Out"
    colour      TEXT NOT NULL DEFAULT '#6B7280',            -- Hex colour for charts
    icon        TEXT,                                       -- Optional emoji or icon name
    is_default  INTEGER NOT NULL DEFAULT 0,                 -- 1 if Monzo default category
    sort_order  INTEGER NOT NULL DEFAULT 0
);
