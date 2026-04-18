-- Migration 010: Trades table (Phase 4)
-- The trades table was designed in schema.sql but never added as a migration.
-- This migration creates it so init_db() applies it on a fresh database.

CREATE TABLE IF NOT EXISTS trades (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id          INTEGER NOT NULL,

    -- Instrument
    symbol              TEXT NOT NULL,
    asset_class         TEXT NOT NULL,          -- stocks, forex, crypto, options
    direction           TEXT NOT NULL,          -- long, short

    -- Entry
    entry_date          TEXT NOT NULL,          -- ISO 8601
    entry_price         INTEGER NOT NULL,       -- Price in pence
    position_size       REAL NOT NULL,          -- Quantity / lots / contracts
    entry_fee           INTEGER NOT NULL DEFAULT 0,

    -- Exit (NULL if trade is open)
    exit_date           TEXT,
    exit_price          INTEGER,
    exit_fee            INTEGER DEFAULT 0,

    -- Risk management (set at entry)
    stop_loss           INTEGER,
    take_profit         INTEGER,
    risk_amount         INTEGER,               -- £ amount risked in pence

    -- Calculated fields (populated on close)
    pnl                 INTEGER,               -- Gross P&L in pence
    pnl_net             INTEGER,               -- Net P&L in pence (after fees)
    pnl_percentage      REAL,                  -- % return on position
    r_multiple          REAL,                  -- pnl_net / risk_amount
    mae                 INTEGER,               -- Max Adverse Excursion in pence
    mfe                 INTEGER,               -- Max Favourable Excursion in pence
    mae_percentage      REAL,
    mfe_percentage      REAL,
    duration_minutes    INTEGER,

    -- Strategy & context
    strategy_id         INTEGER,
    timeframe           TEXT,                  -- 1m, 5m, 15m, 1h, 4h, D, W
    setup_type          TEXT,                  -- breakout, pullback, reversal, news
    market_condition    TEXT,                  -- trending, ranging, volatile, choppy
    entry_reason        TEXT,
    exit_reason         TEXT,
    confidence          INTEGER CHECK(confidence BETWEEN 1 AND 10),

    -- Psychology (rated 1-5)
    emotion_before      INTEGER CHECK(emotion_before BETWEEN 1 AND 5),
    emotion_during      INTEGER CHECK(emotion_during BETWEEN 1 AND 5),
    emotion_after       INTEGER CHECK(emotion_after BETWEEN 1 AND 5),
    rules_followed_pct  REAL,
    psychology_notes    TEXT,
    post_trade_review   TEXT,

    -- Options-specific (NULL for non-options)
    option_type         TEXT,
    strike_price        INTEGER,
    expiry_date         TEXT,
    implied_volatility  REAL,

    -- Meta
    trade_type          TEXT NOT NULL DEFAULT 'trade',
    notes               TEXT,
    screenshot_path     TEXT,
    is_open             INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (account_id)  REFERENCES trading_accounts(id),
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);

CREATE INDEX IF NOT EXISTS idx_trades_date     ON trades(entry_date);
CREATE INDEX IF NOT EXISTS idx_trades_symbol   ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_account  ON trades(account_id);
CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_id);
CREATE INDEX IF NOT EXISTS idx_trades_open     ON trades(is_open);
