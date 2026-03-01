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
    amount          REAL NOT NULL,                          -- Signed decimal in GBP (negative = debit)
    currency        TEXT NOT NULL DEFAULT 'GBP',
    local_amount    REAL,                                   -- Foreign currency amount
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
    amount      REAL NOT NULL,                              -- Monthly budget limit in GBP
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
    initial_balance REAL NOT NULL DEFAULT 0,
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
    entry_price         REAL NOT NULL,
    position_size       REAL NOT NULL,                      -- Quantity/lots/contracts
    entry_fee           REAL NOT NULL DEFAULT 0,

    -- Exit (NULL if trade is open)
    exit_date           TEXT,
    exit_price          REAL,
    exit_fee            REAL DEFAULT 0,

    -- Risk Management (set at entry)
    stop_loss           REAL,                               -- Planned stop loss price
    take_profit         REAL,                               -- Planned take profit price
    risk_amount         REAL,                               -- £ amount risked (for R-multiple calc)

    -- Calculated fields (updated on close)
    pnl                 REAL,                               -- Gross P&L in account currency
    pnl_net             REAL,                               -- Net P&L (after fees)
    pnl_percentage      REAL,                               -- % return on position
    r_multiple          REAL,                               -- P&L / risk_amount
    mae                 REAL,                               -- Max Adverse Excursion
    mfe                 REAL,                               -- Max Favourable Excursion
    duration_minutes    INTEGER,                            -- Time in trade

    -- Strategy & Context
    strategy_id         INTEGER,
    timeframe           TEXT,                               -- 1m, 5m, 15m, 1h, 4h, D, W
    setup_type          TEXT,                               -- breakout, pullback, reversal, etc.
    market_condition    TEXT,                               -- trending, ranging, volatile, choppy
    entry_reason        TEXT,
    exit_reason         TEXT,

    -- Psychology (rated 1-5)
    emotion_before      INTEGER CHECK(emotion_before BETWEEN 1 AND 5),
    emotion_during      INTEGER CHECK(emotion_during BETWEEN 1 AND 5),
    emotion_after       INTEGER CHECK(emotion_after BETWEEN 1 AND 5),
    followed_plan       INTEGER DEFAULT 1,                  -- Boolean
    discipline_notes    TEXT,

    -- Options-specific fields (NULL for non-options)
    option_type         TEXT,                               -- call, put
    strike_price        REAL,
    expiry_date         TEXT,
    implied_volatility  REAL,

    -- Meta
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
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL UNIQUE
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
    balance     REAL NOT NULL,
    equity      REAL,                                       -- Balance + unrealised P&L
    note        TEXT,
    FOREIGN KEY (account_id) REFERENCES trading_accounts(id),
    UNIQUE(account_id, date)
);

CREATE INDEX idx_snapshots_date ON account_snapshots(date);
