-- Jade — Full Database Schema Reference
--
-- This file documents the complete intended schema across all phases.
-- It is a reference only — the actual tables are created by numbered
-- migration files in app/migrations/.
--
-- Status key:
--   (created) = exists in a migration already applied
--   (planned) = will be created in a future migration
--
-- PRAGMAs set on every connection (handled in db.py):
--   PRAGMA journal_mode = WAL;
--   PRAGMA foreign_keys = ON;
--   PRAGMA busy_timeout = 5000;
--   PRAGMA synchronous = NORMAL;


-- ============================================================
-- schema_version  (created by migration runner in db.py)
-- ============================================================

CREATE TABLE schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT
);


-- ============================================================
-- TRANSACTIONS (Phase 1) — (created)
-- ============================================================

CREATE TABLE transactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    monzo_id        TEXT UNIQUE,                           -- Monzo Transaction ID (for dedup)
    date            TEXT NOT NULL,                          -- ISO 8601: 2024-01-15T12:20:18Z
    type            TEXT,                                   -- Card payment, Faster payment, Direct debit, etc.
    name            TEXT NOT NULL,                          -- Display name / merchant
    emoji           TEXT,                                   -- Monzo emoji
    category        TEXT NOT NULL DEFAULT 'general',        -- snake_case: eating_out, groceries, etc.
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

CREATE INDEX idx_transactions_date     ON transactions(date);
CREATE INDEX idx_transactions_category ON transactions(category);
CREATE INDEX idx_transactions_amount   ON transactions(amount);


-- ============================================================
-- CATEGORIES (Phase 1) — (created)
-- ============================================================

CREATE TABLE categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,                       -- snake_case key
    label       TEXT NOT NULL,                              -- Display name: "Eating Out"
    colour      TEXT NOT NULL DEFAULT '#6B7280',            -- Hex colour for charts
    icon        TEXT,                                       -- Optional emoji or icon name
    is_default  INTEGER NOT NULL DEFAULT 0,                 -- 1 if Monzo default category
    sort_order  INTEGER NOT NULL DEFAULT 0
);

-- Default categories seeded on first run (Phase 1.3):
--   general, eating_out, groceries, transport, shopping, entertainment,
--   bills, expenses, holidays, personal_care, family, charity,
--   finances, cash, income, savings


-- ============================================================
-- BUDGETS (Phase 3) — (planned)
-- ============================================================

CREATE TABLE budgets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT NOT NULL,                              -- FK to categories.name
    amount      INTEGER NOT NULL,                            -- Monthly budget limit in pence
    period      TEXT NOT NULL DEFAULT 'monthly',            -- monthly, weekly
    start_date  TEXT,                                       -- Optional: budget start date
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (category) REFERENCES categories(name)
);


-- ============================================================
-- TRADING ACCOUNTS (Phase 4) — (planned)
-- ============================================================

CREATE TABLE trading_accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,                          -- "Interactive Brokers", "Binance", etc.
    broker          TEXT,
    asset_class     TEXT NOT NULL,                          -- stocks, forex, crypto, options, multi
    currency        TEXT NOT NULL DEFAULT 'GBP',
    initial_balance INTEGER NOT NULL DEFAULT 0,              -- Balance in pence
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);


-- ============================================================
-- STRATEGIES (Phase 4) — (planned)
-- ============================================================

CREATE TABLE strategies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,                              -- "Breakout v1.2", "Mean Reversion"
    description TEXT,
    rules       TEXT,                                       -- Trading rules / checklist
    version     TEXT DEFAULT '1.0',
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);


-- ============================================================
-- TRADES (Phase 4) — (planned)
-- ============================================================

CREATE TABLE trades (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id          INTEGER NOT NULL,

    -- Instrument
    symbol              TEXT NOT NULL,                      -- AAPL, EUR/USD, BTC/USDT, etc.
    asset_class         TEXT NOT NULL,                      -- stocks, forex, crypto, options
    direction           TEXT NOT NULL,                      -- long, short

    -- Entry
    entry_date          TEXT NOT NULL,                      -- ISO 8601
    entry_price         INTEGER NOT NULL,                   -- Price in pence
    position_size       REAL NOT NULL,                      -- Quantity/lots/contracts
    entry_fee           INTEGER NOT NULL DEFAULT 0,         -- Fee in pence

    -- Exit (NULL if trade is open)
    exit_date           TEXT,
    exit_price          INTEGER,                            -- Price in pence
    exit_fee            INTEGER DEFAULT 0,                  -- Fee in pence

    -- Risk Management (set at entry)
    stop_loss           INTEGER,                            -- Planned stop loss price in pence
    take_profit         INTEGER,                            -- Planned take profit price in pence
    risk_amount         INTEGER,                            -- £ amount risked in pence (for R-multiple calc)

    -- Calculated fields (updated on close)
    pnl                 INTEGER,                            -- Gross P&L in pence
    pnl_net             INTEGER,                            -- Net P&L in pence (after fees)
    pnl_percentage      REAL,                               -- % return on position
    r_multiple          REAL,                               -- P&L / risk_amount
    mae                 INTEGER,                            -- Max Adverse Excursion in pence
    mfe                 INTEGER,                            -- Max Favourable Excursion in pence
    mae_percentage      REAL,                               -- MAE as % of entry price
    mfe_percentage      REAL,                               -- MFE as % of entry price
    duration_minutes    INTEGER,                            -- Time in trade

    -- Strategy & Context
    strategy_id         INTEGER,
    timeframe           TEXT,                               -- 1m, 5m, 15m, 1h, 4h, D, W
    setup_type          TEXT,                               -- breakout, pullback, reversal, etc.
    market_condition    TEXT,                               -- trending, ranging, volatile, choppy
    entry_reason        TEXT,
    exit_reason         TEXT,
    confidence          INTEGER CHECK(confidence BETWEEN 1 AND 10), -- Pre-trade confidence level

    -- Psychology (rated 1-5)
    emotion_before      INTEGER CHECK(emotion_before BETWEEN 1 AND 5),
    emotion_during      INTEGER CHECK(emotion_during BETWEEN 1 AND 5),
    emotion_after       INTEGER CHECK(emotion_after BETWEEN 1 AND 5),
    rules_followed_pct  REAL,                               -- % of trading rules followed (0-100)
    psychology_notes    TEXT,                               -- What went right/wrong psychologically
    post_trade_review   TEXT,                               -- Separate reflection: "what I'd do differently"

    -- Options-specific fields (NULL for non-options)
    option_type         TEXT,                               -- call, put
    strike_price        INTEGER,                            -- Strike price in pence
    expiry_date         TEXT,
    implied_volatility  REAL,

    -- Meta
    trade_type          TEXT NOT NULL DEFAULT 'trade',      -- trade, dividend, fee, interest, deposit, withdrawal
    notes               TEXT,
    screenshot_path     TEXT,
    is_open             INTEGER NOT NULL DEFAULT 1,         -- 1 = open, 0 = closed
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (account_id) REFERENCES trading_accounts(id),
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);

CREATE INDEX idx_trades_date     ON trades(entry_date);
CREATE INDEX idx_trades_symbol   ON trades(symbol);
CREATE INDEX idx_trades_account  ON trades(account_id);
CREATE INDEX idx_trades_strategy ON trades(strategy_id);
CREATE INDEX idx_trades_open     ON trades(is_open);


-- ============================================================
-- TAGS / TRADE_TAGS (Phase 4) — (planned)
-- ============================================================

CREATE TABLE tags (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    group_name  TEXT NOT NULL DEFAULT 'general'             -- Groups: general, setup, mistake, pattern, market
);

CREATE TABLE trade_tags (
    trade_id    INTEGER NOT NULL,
    tag_id      INTEGER NOT NULL,
    PRIMARY KEY (trade_id, tag_id),
    FOREIGN KEY (trade_id) REFERENCES trades(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id)   REFERENCES tags(id)   ON DELETE CASCADE
);


-- ============================================================
-- DAILY JOURNAL (Phase 4) — (planned)
-- ============================================================

CREATE TABLE daily_journal (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL UNIQUE,                   -- YYYY-MM-DD
    market_outlook  TEXT,
    plan            TEXT,
    review          TEXT,
    mood            INTEGER CHECK(mood BETWEEN 1 AND 5),
    lessons         TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);


-- ============================================================
-- ACCOUNT SNAPSHOTS (Phase 5) — (planned)
-- ============================================================

CREATE TABLE account_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id  INTEGER NOT NULL,
    date        TEXT NOT NULL,                              -- YYYY-MM-DD
    balance     INTEGER NOT NULL,                            -- Balance in pence
    equity      INTEGER,                                    -- Balance + unrealised P&L (pence)
    note        TEXT,
    FOREIGN KEY (account_id) REFERENCES trading_accounts(id),
    UNIQUE(account_id, date)
);

CREATE INDEX idx_snapshots_date ON account_snapshots(date);


-- ============================================================
-- CATEGORY RULES (Phase 2) — (created)
-- ============================================================

CREATE TABLE category_rules (
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

CREATE INDEX idx_category_rules_active ON category_rules(is_active, priority DESC);


-- ============================================================
-- IMPORT PROFILES (Phase 2) — (created)
-- ============================================================

CREATE TABLE import_profiles (
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
