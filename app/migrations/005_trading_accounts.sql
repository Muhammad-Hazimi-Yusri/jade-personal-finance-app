-- Migration 005: Trading Accounts (Phase 4)
-- Creates the trading_accounts table for the trading journal.

CREATE TABLE IF NOT EXISTS trading_accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,                              -- "Interactive Brokers", "Binance", etc.
    broker          TEXT,                                       -- Optional broker name
    asset_class     TEXT NOT NULL,                              -- stocks, forex, crypto, options, multi
    currency        TEXT NOT NULL DEFAULT 'GBP',
    initial_balance INTEGER NOT NULL DEFAULT 0,                 -- Balance in pence
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Active account lookup (used for dropdowns in trade form)
CREATE INDEX IF NOT EXISTS idx_trading_accounts_active
    ON trading_accounts(is_active);
