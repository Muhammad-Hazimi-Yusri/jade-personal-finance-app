-- Migration 002: Convert monetary columns from REAL to INTEGER (pence)
-- Multiplies existing amount and local_amount by 100 and casts to INTEGER.
-- SQLite cannot ALTER COLUMN, so we recreate the table.

-- Step 1: Rename the old table
ALTER TABLE transactions RENAME TO _transactions_old;

-- Step 2: Recreate with INTEGER money columns (matches updated 001_initial.sql)
CREATE TABLE transactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    monzo_id        TEXT UNIQUE,
    date            TEXT NOT NULL,
    type            TEXT,
    name            TEXT NOT NULL,
    emoji           TEXT,
    category        TEXT NOT NULL DEFAULT 'general',
    amount          INTEGER NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'GBP',
    local_amount    INTEGER,
    local_currency  TEXT,
    notes           TEXT,
    address         TEXT,
    description     TEXT,
    is_income       INTEGER NOT NULL DEFAULT 0,
    custom_category TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Step 3: Copy data, converting decimal to pence (× 100)
INSERT INTO transactions (
    id, monzo_id, date, type, name, emoji, category, amount, currency,
    local_amount, local_currency, notes, address, description,
    is_income, custom_category, created_at, updated_at
)
SELECT
    id, monzo_id, date, type, name, emoji, category,
    CAST(ROUND(amount * 100) AS INTEGER),
    currency,
    CASE WHEN local_amount IS NOT NULL
         THEN CAST(ROUND(local_amount * 100) AS INTEGER)
         ELSE NULL
    END,
    local_currency, notes, address, description,
    is_income, custom_category, created_at, updated_at
FROM _transactions_old;

-- Step 4: Drop old table
DROP TABLE _transactions_old;

-- Step 5: Recreate indexes
CREATE INDEX IF NOT EXISTS idx_transactions_date     ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_transactions_amount   ON transactions(amount);
