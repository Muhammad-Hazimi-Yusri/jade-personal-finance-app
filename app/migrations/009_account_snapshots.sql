-- Migration 009: account snapshots for equity curve and net-worth trend

CREATE TABLE IF NOT EXISTS account_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id  INTEGER NOT NULL,
    date        TEXT NOT NULL,
    balance     INTEGER NOT NULL,
    equity      INTEGER,
    note        TEXT,
    FOREIGN KEY (account_id) REFERENCES trading_accounts(id),
    UNIQUE(account_id, date)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_date ON account_snapshots(date);
