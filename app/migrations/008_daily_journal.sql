-- Migration 008: Daily journal table
CREATE TABLE IF NOT EXISTS daily_journal (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL UNIQUE,                   -- YYYY-MM-DD
    market_outlook  TEXT,                                   -- Overall market view for the day
    plan            TEXT,                                   -- What you planned to do
    review          TEXT,                                   -- End-of-day review
    mood            INTEGER CHECK(mood BETWEEN 1 AND 5),   -- 1=terrible, 5=great
    lessons         TEXT,                                   -- Key takeaways
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_journal_date ON daily_journal(date DESC);
