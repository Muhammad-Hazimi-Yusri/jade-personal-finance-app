-- Migration 004: Budgets (Phase 3)
-- Creates the budgets table for monthly/weekly spending limits per category.

CREATE TABLE IF NOT EXISTS budgets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT NOT NULL,                              -- FK to categories.name
    amount      INTEGER NOT NULL,                           -- Budget limit in pence
    period      TEXT NOT NULL DEFAULT 'monthly',            -- monthly, weekly
    start_date  TEXT,                                       -- Optional: budget start date (ISO 8601)
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (category) REFERENCES categories(name)
);

-- One budget per category per period type
CREATE UNIQUE INDEX IF NOT EXISTS idx_budgets_category_period
    ON budgets(category, period);

-- FK lookup performance (used by status endpoint joining transactions)
CREATE INDEX IF NOT EXISTS idx_budgets_category
    ON budgets(category);
