# 💎 Jade

**Personal Finance & Trading Journal**

> A lightweight, self-hosted web application for managing personal finances and tracking trading behavior across all asset classes. Built with Flask, SQLite, and vanilla JavaScript.

**Live:** [jade.muhammadhazimiyusri.uk](https://jade.muhammadhazimiyusri.uk)

---

## Table of Contents

- [Overview](#overview)
- [Branding](#branding)
- [Tech Stack](#tech-stack)
- [Inspiration & References](#inspiration--references)
- [Project Structure](#project-structure)
- [Database Schema](#database-schema)
- [API Endpoints](#api-endpoints)
- [Frontend Architecture](#frontend-architecture)
- [Authentication & Security](#authentication--security)
- [Monzo CSV Import](#monzo-csv-import)
- [Trading Journal](#trading-journal)
- [Dashboard & Charts](#dashboard--charts)
- [Deployment](#deployment)
- [Database Migrations](#database-migrations)
- [Development Roadmap](#development-roadmap)
- [Development Guidelines](#development-guidelines)

---

## Overview

Jade combines two financial tools into one unified interface:

1. **Personal Finance Tracker** — Import Monzo bank transactions via CSV, categorise spending, track budgets, and visualise income vs expenses over time.
2. **Trading Journal** — Log trades across stocks, forex, crypto, and options. Track win rate, R-multiples, profit factor, drawdown, emotional discipline, and more.

This is a **single-user, self-hosted** application. There is no multi-user support, no public registration, and no SaaS features. Authentication is handled at the reverse proxy level.

---

## Branding

### Name
**Jade** — clean, short, memorable. Represents clarity and value.

### Colour Palette

| Role | Hex | Usage |
|------|-----|-------|
| Primary | `#00A86B` | Jade green — buttons, links, active states |
| Primary Dark | `#007A4D` | Hover states, emphasis |
| Background | `#0F1117` | Main dark background |
| Surface | `#1A1D27` | Cards, panels, modals |
| Surface Light | `#252830` | Hover on surface, table rows |
| Border | `#2E3140` | Subtle borders, dividers |
| Text Primary | `#E8E9ED` | Main body text |
| Text Secondary | `#9CA3AF` | Labels, secondary info |
| Text Muted | `#6B7280` | Placeholders, disabled |
| Success | `#10B981` | Profit, positive change |
| Danger | `#EF4444` | Loss, negative change, errors |
| Warning | `#F59E0B` | Caution, pending states |
| Info | `#3B82F6` | Informational, links |

### Typography

- **Headings:** `Inter` (loaded from Google Fonts, fallback: `system-ui, -apple-system, sans-serif`)
- **Body:** `Inter`
- **Monospace/Numbers:** `JetBrains Mono` (for financial figures, code, tables)

### Design Principles

- Dark mode only (finance apps are frequently checked in low light)
- Minimal, clean UI — no visual clutter
- Numbers are always right-aligned and use monospace font
- Currency values always show 2 decimal places with £ symbol
- Positive values in green (`#10B981`), negative in red (`#EF4444`)
- Cards with subtle borders, no heavy shadows
- Consistent 8px spacing grid

---

## Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Backend** | Flask (Python) | Simple, native SQLite support, excellent CSV parsing |
| **Database** | SQLite (WAL mode) | Zero-config, single file, perfect for single-user |
| **WSGI Server** | Gunicorn (1 worker) | Production-grade, no concurrency concerns |
| **Tunnel** | Cloudflare Tunnel (`cloudflared`) | No open ports, automatic HTTPS, DDoS protection |
| **Frontend** | Vanilla JS (ES6 modules) | No build tools, hash-based SPA routing |
| **CSS** | Custom (design system above) | Full control, dark mode, ~5KB |
| **Charts (Finance)** | Chart.js | Pie, bar, line, area — best docs, ~68KB gzipped |
| **Charts (Trading)** | TradingView Lightweight Charts | Candlestick, equity curves — ~12KB gzipped |
| **Auth** | Cloudflare Access (Zero Trust) | Free, zero app code, email/OTP login gate |
| **Backup** | Litestream → S3/R2 | Continuous streaming replication |
| **Deployment** | Docker Compose | Single `docker-compose up -d` |

### External CDN Dependencies

```html
<!-- Fonts -->
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">

<!-- Charts -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
```

---

## Inspiration & References

Jade's design draws from these open-source projects:

| Project | What We Borrowed |
|---------|-----------------|
| [Firefly III](https://github.com/firefly-iii/firefly-iii) | Rule engine for auto-categorisation, CSV import profiles |
| [Actual Budget](https://github.com/actualbudget/actual) | Validation that SQLite is excellent for personal finance |
| [Maybe Finance](https://github.com/maybe-finance/maybe) | Polymorphic Entry model concept (transactions + trades share patterns) |
| [Ghostfolio](https://github.com/ghostfolio/ghostfolio) | Multi-asset activity schema, trade_type field design |
| [TradeNote](https://github.com/Eleven-Trading/TradeNote) | MFE tracking, tag groups, daily diary linked to trades |
| [riccorohl/trading-journal](https://github.com/riccorohl/trading-journal) | Psychology-enriched trade schema, confidence rating, rules_followed_pct |

**What we deliberately didn't adopt:**
- Double-entry accounting (Firefly III) — overkill for single-user
- Polymorphic Entry model — keep transactions and trades as separate tables for clarity
- CRDT sync (Actual Budget) — not needed for single-user

---

## Project Structure

> **Status Key:** ✅ = exists, 🔲 = planned

```
jade/
├── ✅ README.md                 # THIS FILE — single source of truth
├── ✅ CLAUDE.md                 # Claude Code instructions and context
├── ✅ CHANGELOG.md              # Version history (Keep a Changelog format)
├── ✅ VERSION                   # Semver version string
├── ✅ .gitignore
├── 🔲 docker-compose.yml        # Deployment orchestration (Phase 6)
├── 🔲 Dockerfile                # Flask app container (Phase 6)
├── 🔲 .env.example              # Environment variable template (Phase 6)
├── 🔲 litestream.yml            # Database backup config (Phase 6)
├── ✅ requirements.txt          # Python dependencies (Phase 1)
│
├── ✅ app/                      # Flask application (Phase 1)
│   ├── ✅ __init__.py           # App factory, register blueprints
│   ├── ✅ db.py                 # SQLite connection manager, PRAGMAs
│   ├── ✅ schema.sql            # Full database schema
│   ├── ✅ migrations/           # Numbered migration files
│   │   └── ✅ 001_initial.sql
│   │
│   ├── ✅ routes/               # API route blueprints
│   │   ├── ✅ __init__.py
│   │   ├── ✅ transactions.py   # GET/POST/PUT/DELETE transactions (Phase 1)
│   │   ├── 🔲 upload.py         # Monzo CSV import endpoint (Phase 2)
│   │   ├── ✅ categories.py     # Category list endpoint (Phase 1.6)
│   │   ├── 🔲 budgets.py        # Budget CRUD (Phase 3)
│   │   ├── 🔲 category_rules.py # Category rules CRUD (Phase 2)
│   │   ├── 🔲 trades.py         # Trading journal CRUD (Phase 4)
│   │   ├── 🔲 accounts.py       # Trading account management (Phase 4)
│   │   ├── 🔲 strategies.py     # Strategy management (Phase 4)
│   │   ├── 🔲 reports.py        # Aggregated analytics & stats (Phase 5)
│   │   └── 🔲 dashboard.py      # Dashboard summary data (Phase 3)
│   │
│   ├── ✅ services/             # Business logic layer
│   │   ├── ✅ __init__.py
│   │   ├── ✅ transactions.py   # Transaction CRUD logic & validation (Phase 1)
│   │   ├── 🔲 csv_parser.py     # Monzo CSV parsing & validation (Phase 2)
│   │   ├── 🔲 category_rules.py # Category rules engine (Phase 2)
│   │   ├── 🔲 trade_calculator.py # R-multiples, win rate, etc. (Phase 4)
│   │   └── 🔲 analytics.py      # Spending analytics (Phase 3)
│   │
│   └── ✅ utils/                # Shared utilities
│       ├── ✅ __init__.py
│       └── 🔲 formatters.py     # Currency formatting, date helpers
│
├── ✅ frontend/                 # Static frontend (served by Flask)
│   ├── ✅ index.html            # Shell HTML — SPA entry point (Phase 1)
│   ├── ✅ css/
│   │   └── ✅ style.css         # Full design system (Phase 1)
│   ├── ✅ js/
│   │   ├── ✅ app.js            # Router, navigation, initialisation (Phase 1)
│   │   ├── ✅ api.js            # Fetch wrapper for all API calls (Phase 1)
│   │   ├── ✅ utils.js          # Shared formatting, helpers
│   │   ├── 🔲 components/       # Reusable UI components
│   │   │   ├── 🔲 modal.js
│   │   │   ├── 🔲 toast.js
│   │   │   ├── 🔲 table.js
│   │   │   ├── 🔲 chart-helpers.js
│   │   │   └── 🔲 form-helpers.js
│   │   └── ✅ views/            # Page-level view modules
│   │       ├── ✅ dashboard.js
│   │       ├── ✅ transactions.js
│   │       ├── ✅ upload.js
│   │       ├── ✅ budgets.js
│   │       ├── ✅ trades.js
│   │       ├── ✅ trade-form.js
│   │       ├── ✅ trade-analytics.js
│   │       ├── ✅ journal.js
│   │       └── ✅ settings.js
│   └── 🔲 assets/
│       └── 🔲 jade-logo.svg     # App logo
│
├── ✅ data/                     # SQLite database files (gitignored)
│   └── 🔲 jade.db
│
├── 🔲 demo-data/                # Demo instance data (Phase 6)
│   ├── 🔲 seed.sql              # SQL script to generate fake data
│   └── 🔲 seed.db               # Pre-built seed database (reset source)
│
└── 🔲 tests/                    # Test suite
    ├── 🔲 conftest.py
    ├── 🔲 test_csv_parser.py
    ├── 🔲 test_trade_calculator.py
    ├── 🔲 test_transactions_api.py
    └── 🔲 test_trades_api.py
```

---

## Database Schema

### SQLite PRAGMAs (set on every connection)

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;
```

### Money Storage Convention

All monetary values are stored as **integers in pence** (1/100 of GBP). This avoids IEEE 754 floating-point rounding errors (e.g., `£0.10 + £0.20 ≠ £0.30` with floats).

| Example | Stored Value | Display |
|---------|-------------|---------|
| £5.10   | `510`       | £5.10   |
| -£3.50  | `-350`      | -£3.50  |
| £0.00   | `0`         | £0.00   |
| £1,234.56 | `123456`  | £1,234.56 |

- **SQLite type:** `INTEGER` for all money columns
- **API layer:** Accepts and returns decimal values (e.g., `5.10`). Conversion happens at the service layer boundary
- **Frontend:** Receives decimals from API, formats with `£` symbol and 2 decimal places

### Tables

#### `schema_version`
Tracks applied migrations.

```sql
CREATE TABLE schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT
);
```

#### `transactions` (Personal Finance)

```sql
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

CREATE INDEX idx_transactions_date ON transactions(date);
CREATE INDEX idx_transactions_category ON transactions(category);
CREATE INDEX idx_transactions_amount ON transactions(amount);
```

> **Migration note:** The `transactions` table was originally created in `001_initial.sql` with `amount REAL` and `local_amount REAL`. Migration `002_money_to_pence.sql` converts these columns to `INTEGER` storing pence (recreates the table and multiplies existing values by 100).

#### `categories`

```sql
CREATE TABLE categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,                       -- snake_case key
    label       TEXT NOT NULL,                              -- Display name: "Eating Out"
    colour      TEXT NOT NULL DEFAULT '#6B7280',            -- Hex colour for charts
    icon        TEXT,                                       -- Optional emoji or icon name
    is_default  INTEGER NOT NULL DEFAULT 0,                 -- 1 if Monzo default category
    sort_order  INTEGER NOT NULL DEFAULT 0
);
```

**Default categories (seeded on first run):**

| name | label | colour |
|------|-------|--------|
| `general` | General | `#6B7280` |
| `eating_out` | Eating Out | `#F59E0B` |
| `groceries` | Groceries | `#10B981` |
| `transport` | Transport | `#3B82F6` |
| `shopping` | Shopping | `#8B5CF6` |
| `entertainment` | Entertainment | `#EC4899` |
| `bills` | Bills | `#EF4444` |
| `expenses` | Expenses | `#F97316` |
| `holidays` | Holidays | `#14B8A6` |
| `personal_care` | Personal Care | `#A855F7` |
| `family` | Family | `#F43F5E` |
| `charity` | Charity | `#6366F1` |
| `finances` | Finances | `#0EA5E9` |
| `cash` | Cash | `#84CC16` |
| `income` | Income | `#22D3EE` |
| `savings` | Savings | `#00A86B` |

#### `budgets`

```sql
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
```

#### `trading_accounts`

```sql
CREATE TABLE trading_accounts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,                              -- "Interactive Brokers", "Binance", etc.
    broker      TEXT,
    asset_class TEXT NOT NULL,                              -- stocks, forex, crypto, options, multi
    currency    TEXT NOT NULL DEFAULT 'GBP',
    initial_balance INTEGER NOT NULL DEFAULT 0,              -- Balance in pence
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```

#### `trades`

```sql
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
    entry_reason        TEXT,                               -- Why you entered
    exit_reason         TEXT,                               -- Why you exited
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

CREATE INDEX idx_trades_date ON trades(entry_date);
CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_account ON trades(account_id);
CREATE INDEX idx_trades_strategy ON trades(strategy_id);
CREATE INDEX idx_trades_open ON trades(is_open);
```

#### `strategies`

```sql
CREATE TABLE strategies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,                              -- "Breakout v1.2", "Mean Reversion"
    description TEXT,
    rules       TEXT,                                       -- Trading rules / checklist
    version     TEXT DEFAULT '1.0',
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```

#### `tags` and `trade_tags`

```sql
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
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);
```

#### `daily_journal`

```sql
CREATE TABLE daily_journal (
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
```

#### `account_snapshots`

```sql
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
```

#### `category_rules` *(planned — Phase 2)*

```sql
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
```

Rules are applied during CSV import to auto-categorise transactions. See [Categorisation Strategy](#categorisation-strategy) below.

#### `import_profiles` *(planned — Phase 2)*

```sql
CREATE TABLE import_profiles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,                   -- 'Monzo', 'Starling', etc.
    file_type       TEXT NOT NULL DEFAULT 'csv',            -- csv, json
    column_mapping  TEXT NOT NULL,                          -- JSON: maps source columns to transaction fields
    date_format     TEXT,                                   -- strptime format string (NULL = ISO 8601)
    delimiter       TEXT NOT NULL DEFAULT ',',
    has_header      INTEGER NOT NULL DEFAULT 1,
    dedup_field     TEXT,                                   -- Column used for deduplication (e.g. 'Transaction ID')
    notes           TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Pre-seeded Monzo profile:** A Monzo import profile will be seeded on first run alongside default categories, mapping all 16 Monzo CSV columns to transaction fields.

---

## API Endpoints

Base URL: `/api`

All responses use JSON. All monetary values are returned as decimals (e.g., `5.10` not `510`) — the API handles pence-to-decimal conversion. Dates are ISO 8601 strings.

### Transactions (Personal Finance)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/transactions` | List transactions (paginated, filterable) |
| `GET` | `/api/transactions/:id` | Get single transaction |
| `POST` | `/api/transactions` | Create manual transaction |
| `PUT` | `/api/transactions/:id` | Update transaction |
| `DELETE` | `/api/transactions/:id` | Delete transaction |

**Query parameters for `GET /api/transactions`:**

| Param | Type | Description |
|-------|------|-------------|
| `page` | int | Page number (default: 1) |
| `per_page` | int | Items per page (default: 50, max: 200) |
| `category` | string | Filter by category (snake_case) |
| `type` | string | Filter by transaction type |
| `start_date` | string | ISO 8601 start date |
| `end_date` | string | ISO 8601 end date |
| `search` | string | Search name, notes, description |
| `min_amount` | float | Minimum amount filter |
| `max_amount` | float | Maximum amount filter |
| `sort` | string | Sort field (default: `date`) |
| `order` | string | `asc` or `desc` (default: `desc`) |

### Upload

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/upload/monzo` | Upload Monzo CSV file |

**Response includes:** `imported` count, `skipped` count (duplicates), `errors` array.

### Categories

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/categories` | List all categories |
| `POST` | `/api/categories` | Create custom category |
| `PUT` | `/api/categories/:id` | Update category |
| `DELETE` | `/api/categories/:id` | Delete custom category (not defaults) |

### Budgets

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/budgets` | List all budgets |
| `GET` | `/api/budgets/status` | Current month budget status with spending |
| `POST` | `/api/budgets` | Create budget |
| `PUT` | `/api/budgets/:id` | Update budget |
| `DELETE` | `/api/budgets/:id` | Delete budget |

### Trades

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/trades` | List trades (paginated, filterable) |
| `GET` | `/api/trades/:id` | Get single trade with full details |
| `POST` | `/api/trades` | Create new trade |
| `PUT` | `/api/trades/:id` | Update trade (including close) |
| `DELETE` | `/api/trades/:id` | Delete trade |
| `POST` | `/api/trades/:id/close` | Close a trade (shortcut) |

**Query parameters for `GET /api/trades`:**

| Param | Type | Description |
|-------|------|-------------|
| `page` | int | Page number |
| `per_page` | int | Items per page |
| `account_id` | int | Filter by account |
| `asset_class` | string | stocks, forex, crypto, options |
| `symbol` | string | Filter by symbol |
| `strategy_id` | int | Filter by strategy |
| `is_open` | int | 0 = closed, 1 = open |
| `start_date` | string | Filter by entry date |
| `end_date` | string | Filter by entry date |
| `direction` | string | long, short |

### Trading Accounts

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/accounts` | List trading accounts |
| `POST` | `/api/accounts` | Create account |
| `PUT` | `/api/accounts/:id` | Update account |
| `DELETE` | `/api/accounts/:id` | Delete account |

### Strategies

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/strategies` | List strategies |
| `POST` | `/api/strategies` | Create strategy |
| `PUT` | `/api/strategies/:id` | Update strategy |
| `DELETE` | `/api/strategies/:id` | Delete strategy |

### Tags

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/tags` | List all tags |
| `POST` | `/api/tags` | Create tag |
| `DELETE` | `/api/tags/:id` | Delete tag |
| `POST` | `/api/trades/:id/tags` | Add tags to trade |
| `DELETE` | `/api/trades/:id/tags/:tag_id` | Remove tag from trade |

### Daily Journal

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/journal` | List journal entries |
| `GET` | `/api/journal/:date` | Get journal for specific date |
| `POST` | `/api/journal` | Create/update journal entry |
| `DELETE` | `/api/journal/:date` | Delete journal entry |

### Reports & Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/reports/spending` | Spending breakdown by category & period |
| `GET` | `/api/reports/income-vs-expenses` | Income vs expenses over time |
| `GET` | `/api/reports/net-worth` | Net worth trend (account snapshots) |
| `GET` | `/api/reports/trading-performance` | Win rate, profit factor, expectancy, etc. |
| `GET` | `/api/reports/equity-curve` | Equity curve data for chart |
| `GET` | `/api/reports/trade-distribution` | P&L distribution, R-multiple histogram |
| `GET` | `/api/reports/discipline` | Psychology/discipline correlation analysis |
| `GET` | `/api/reports/streaks` | Win/loss streak tracking |

**Common query parameters for reports:**

| Param | Type | Description |
|-------|------|-------------|
| `period` | string | `week`, `month`, `quarter`, `year`, `all` |
| `start_date` | string | Custom start date |
| `end_date` | string | Custom end date |
| `account_id` | int | Filter by trading account |
| `asset_class` | string | Filter by asset class |
| `strategy_id` | int | Filter by strategy |

### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/dashboard/finance` | Finance overview: balance, income, expenses, budget status |
| `GET` | `/api/dashboard/trading` | Trading overview: open trades, today's P&L, key metrics |

---

## Frontend Architecture

### SPA Routing

Hash-based routing using vanilla JS. No build tools, no bundler.

```
#/                      → Dashboard (combined finance + trading overview)
#/transactions          → Transaction list with filters
#/transactions/:id      → Transaction detail
#/upload                → Monzo CSV upload page
#/budgets               → Budget management
#/trades                → Trade log with filters
#/trades/new            → New trade form
#/trades/:id            → Trade detail view
#/trades/:id/edit       → Edit trade
#/analytics             → Trading analytics & reports
#/journal               → Daily trading journal
#/settings              → Account management, strategies, categories
```

### View Module Pattern

Each view is an ES6 module exporting a `render()` function:

```javascript
// js/views/dashboard.js
export async function render(container) {
    const data = await api.get('/api/dashboard/finance');
    container.innerHTML = `...`;
    // Initialise charts, attach event listeners
}
```

### Router Implementation

```javascript
// js/app.js
const routes = {
    '':                 () => import('./views/dashboard.js'),
    'transactions':     () => import('./views/transactions.js'),
    'upload':           () => import('./views/upload.js'),
    'budgets':          () => import('./views/budgets.js'),
    'trades':           () => import('./views/trades.js'),
    'trades/new':       () => import('./views/trade-form.js'),
    'analytics':        () => import('./views/trade-analytics.js'),
    'journal':          () => import('./views/journal.js'),
    'settings':         () => import('./views/settings.js'),
};

window.addEventListener('hashchange', handleRoute);
```

### Navigation Structure

```
┌─ Sidebar ──────────────┐
│  💎 Jade               │
│                        │
│  FINANCE               │
│  ├─ Dashboard          │
│  ├─ Transactions       │
│  ├─ Upload CSV         │
│  └─ Budgets            │
│                        │
│  TRADING               │
│  ├─ Trade Log          │
│  ├─ New Trade          │
│  ├─ Analytics          │
│  └─ Journal            │
│                        │
│  ──────────            │
│  Settings              │
└────────────────────────┘
```

---

## Authentication & Security

### Approach: Cloudflare Access (Zero Trust)

Authentication is handled entirely by Cloudflare Access — **zero auth code in the Flask app**. Cloudflare Access acts as a gatekeeper: before anyone can reach Jade (any page, any API endpoint), they must authenticate through Cloudflare's login screen. Only approved emails can access the app.

This is the same Cloudflare Tunnel (`cloudflared`) infrastructure used to serve Jellyfin and other services from this home server.

### How It Works

```
User visits jade.muhammadhazimiyusri.uk
  → Cloudflare Access intercepts the request
  → User sees Cloudflare login page (email OTP or other provider)
  → If authorised → request passes through Cloudflare Tunnel
  → cloudflared on home PC forwards to Flask on localhost:8000
  → Flask handles the request (no auth code needed)
```

### Cloudflare Access Setup

1. **In Cloudflare Zero Trust Dashboard → Access → Applications:**
   - Create a new **Self-hosted** application
   - Application domain: `jade.muhammadhazimiyusri.uk`
   - Set a policy:
     - Policy name: `Allow owner`
     - Action: **Allow**
     - Include rule: **Emails** — `your-email@example.com`

2. **In Cloudflare Zero Trust Dashboard → Networks → Tunnels:**
   - Use your existing tunnel (the one serving Jellyfin)
   - Add a new **Public Hostname**:
     - Subdomain: `jade`
     - Domain: `muhammadhazimiyusri.uk`
     - Service: `http://localhost:8000`

### Cloudflare Headers

When a request passes through Cloudflare Access, it includes these headers that Flask can optionally read:

| Header | Value |
|--------|-------|
| `Cf-Access-Authenticated-User-Email` | The authenticated user's email |
| `Cf-Access-Jwt-Assertion` | JWT token (can be verified) |

Flask does **not** need to check these for basic security (Cloudflare blocks unauthenticated requests before they reach Flask). But they can be useful for logging or displaying "Logged in as: you@email.com" in the UI.

### Security Checklist

- [x] HTTPS enforced by Cloudflare (automatic)
- [x] Zero Trust auth gate — no unauthenticated traffic reaches Flask
- [x] No open ports on home network (cloudflared outbound-only)
- [x] DDoS protection via Cloudflare
- [x] SQL parameterised queries everywhere (no string concatenation)
- [x] File upload validation (CSV only, size limit 10MB)
- [x] No CORS needed (same-origin only)
- [x] CSP headers set by Flask for defence-in-depth

### Flask Security Headers (defence-in-depth)

Even though Cloudflare handles the perimeter, Flask should still set basic security headers:

```python
@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' cdn.jsdelivr.net unpkg.com; "
        "style-src 'self' 'unsafe-inline' fonts.googleapis.com; "
        "font-src fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'"
    )
    return response
```

---

## Demo Mode (Portfolio Showcase)

### Overview

A public demo instance runs at `jade-demo.muhammadhazimiyusri.uk` with **no authentication**. It uses the same codebase as the real app but runs against a pre-seeded database of realistic fake data. The database resets to its original state every 24 hours via a cron job.

### How It Works

```
Visitor hits jade-demo.muhammadhazimiyusri.uk
  → No Cloudflare Access (public)
  → Cloudflare Tunnel → cloudflared → Flask on localhost:8001
  → Flask runs with DEMO_MODE=true
  → Serves pre-seeded fake data
  → Database resets daily at 03:00 UTC
```

### Demo vs Production Differences

| Behaviour | Production (`jade.`) | Demo (`jade-demo.`) |
|-----------|---------------------|---------------------|
| Auth | Cloudflare Access (email gate) | None (public) |
| Data | Real financial data | Pre-seeded fake data |
| Port | `8000` | `8001` |
| DB path | `./data/jade.db` | `./demo-data/jade.db` |
| Banner | None | "Demo Mode — sample data, resets daily" |
| CSV upload | Works normally | Works (resets daily anyway) |
| Database | Persistent | Resets to seed state daily at 03:00 UTC |

### `DEMO_MODE` Environment Variable

When `DEMO_MODE=true`, Flask should:

1. **Show a banner** at the top of every page: `"🔶 Demo Mode — You're viewing sample data. This instance resets daily."`
2. **Set `X-Demo-Mode: true` response header** (useful for testing)
3. Everything else works normally — full CRUD, uploads, trading, analytics

### Demo Seed Data (`demo-data/seed.sql`)

The seed script should populate realistic-looking data:

- **~6 months of transactions** (~500 rows) across all Monzo categories with realistic amounts, names, and dates
- **1 trading account** ("Demo Trading Account", multi-asset, £10,000 starting balance)
- **3 strategies** ("Breakout v1.0", "Mean Reversion", "Trend Following")
- **~80 closed trades** across stocks, forex, crypto, and options with a ~55% win rate and ~1.6 profit factor
- **5 open trades**
- **3 months of daily journal entries** (~60 entries)
- **Account snapshots** for equity curve data
- **Budgets** for 6 categories
- **Tags** like "earnings", "news-driven", "overtraded", "A+ setup", "revenge-trade"

All names, amounts, and dates should look realistic but be entirely fictional.

### Daily Reset Mechanism

A simple cron job or Docker restart policy resets the demo database:

```bash
# Cron job on host (add to crontab)
0 3 * * * cp /path/to/jade/demo-data/seed.db /path/to/jade/demo-data/jade.db && docker restart jade-demo
```

Or use a sidecar container in Docker Compose:

```yaml
jade-demo-reset:
  image: alpine:3
  container_name: jade-demo-reset
  restart: unless-stopped
  volumes:
    - ./demo-data:/data
  entrypoint: /bin/sh
  command: >
    -c "while true; do
      sleep 86400;
      cp /data/seed.db /data/jade.db;
      echo 'Demo database reset at $$(date)';
    done"
```

### Cloudflare Tunnel Config for Demo

Add a second public hostname in your tunnel (no Access policy):

- Subdomain: `jade-demo`
- Domain: `muhammadhazimiyusri.uk`
- Type: `HTTP`
- URL: `localhost:8001`

Or in `config.yml`:

```yaml
ingress:
  - hostname: jade.muhammadhazimiyusri.uk
    service: http://localhost:8000
  - hostname: jade-demo.muhammadhazimiyusri.uk
    service: http://localhost:8001
  - service: http_status:404
```

---

## Monzo CSV Import

### CSV Format (16 Columns)

Monzo Plus/Premium exports contain these columns:

```
Transaction ID, Date, Time, Type, Name, Emoji, Category, Amount, Currency,
Local amount, Local currency, Notes and #tags, Address, Receipt, Description,
Category split
```

### Parsing Rules

1. **Date** is ISO 8601 with UTC suffix: `2024-01-15T12:20:18Z`
2. **Amount** is a signed decimal in pounds (not pence): `-5.10` for debits, `250.00` for credits
3. **Category** is snake_case: `eating_out`, `personal_care`, `groceries`
4. **Transaction ID** is used for deduplication — skip rows with existing `monzo_id`
5. **Type** values: `Card payment`, `Faster payment`, `Direct debit`, `Standing order`, `Pot transfer`, `Bank transfer`
6. **is_income** is derived: `1` if `amount > 0`, else `0`
7. **Time** column is often empty — ignore it, use Date column
8. **Local amount/currency** are only populated for foreign transactions
9. **Category split** is rarely used — store as-is if present

### Import Flow

```
User uploads CSV
  → Validate file (CSV format, expected headers)
  → Parse rows with csv.DictReader
  → For each row:
    → Check monzo_id doesn't exist (dedup)
    → Map columns to transactions table
    → Determine is_income from amount sign
    → Insert into database
  → Return summary: { imported: N, skipped: N, errors: [] }
```

### Categorisation Strategy

Transactions are auto-categorised using a three-tier system:

| Tier | Source | Description |
|------|--------|-------------|
| **Tier 1: Monzo defaults** | CSV `Category` column | The category assigned by Monzo (e.g., `eating_out`, `groceries`). Used as-is on import. Covers ~90% of transactions. |
| **Tier 2: Keyword rules** | `category_rules` table | If a rule's keyword matches the transaction name/description, override the Monzo category. Higher-priority rules win. |
| **Tier 3: Learned corrections** | User manual edits | When a user manually changes a transaction's category, auto-create a keyword rule (`source = 'learned'`) so future imports of the same merchant are categorised correctly. Can be toggled off in Settings. |

**Resolution order:** Tier 3 rules (learned, highest priority) → Tier 2 rules (manual) → Tier 1 (Monzo default).

The system gets smarter over time: correct a category once, and all future imports of that merchant are automatically categorised.

---

## Trading Journal

### Calculated Metrics (computed in `trade_calculator.py`)

#### Per-Trade (calculated when trade is closed)

| Metric | Formula |
|--------|---------|
| **P&L (Gross)** | `(exit_price - entry_price) × position_size × direction_multiplier` |
| **P&L (Net)** | `pnl - entry_fee - exit_fee` |
| **P&L %** | `pnl_net / (entry_price × position_size) × 100` |
| **R-Multiple** | `pnl_net / risk_amount` |
| **Duration** | `exit_date - entry_date` in minutes |

*Direction multiplier: `1` for long, `-1` for short*

#### Aggregate (calculated across filtered trade set)

| Metric | Formula |
|--------|---------|
| **Win Rate** | `winning_trades / total_closed_trades × 100` |
| **Profit Factor** | `sum(winning_pnl) / abs(sum(losing_pnl))` |
| **Expectancy** | `(win_rate × avg_win) - (loss_rate × avg_loss)` |
| **Avg R-Multiple** | `sum(r_multiples) / total_trades` |
| **Max Drawdown** | `(peak_equity - trough_equity) / peak_equity × 100` |
| **Sharpe Ratio** | `(mean_return - risk_free_rate) / std_dev_returns` |
| **Max Consecutive Wins** | Longest winning streak |
| **Max Consecutive Losses** | Longest losing streak |
| **Avg Win** | `sum(winning_pnl) / winning_trades` |
| **Avg Loss** | `sum(losing_pnl) / losing_trades` |
| **Largest Win** | `max(pnl_net)` |
| **Largest Loss** | `min(pnl_net)` |
| **Avg Duration (Winners)** | Mean duration of winning trades |
| **Avg Duration (Losers)** | Mean duration of losing trades |
| **Discipline Score** | `avg(rules_followed_pct)` across filtered trade set |

### Psychology Tracking

Emotion scale (1-5):
- 1 = Very negative (fearful, anxious, tilted, revenge trading)
- 2 = Negative (uncertain, hesitant)
- 3 = Neutral (calm, focused)
- 4 = Positive (confident, clear-headed)
- 5 = Very positive (in the zone, excellent focus)

The **discipline correlation report** cross-references emotion scores with trade outcomes to reveal patterns (e.g., "Your win rate drops 30% when emotion_before ≤ 2").

---

## Dashboard & Charts

### Finance Dashboard (`#/`)

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  Current Balance: £X,XXX.XX        This Month: -£X,XXX.XX       │
│                                                                  │
├─────────────────────────────┬────────────────────────────────────┤
│                             │                                    │
│  Income vs Expenses         │  Budget Progress                   │
│  [Bar Chart - 6 months]     │  Housing    ████████░░  80%        │
│                             │  Groceries  ██████░░░░  60%        │
│  Income:   £X,XXX           │  Transport  ████░░░░░░  40%        │
│  Expenses: £X,XXX           │  Dining     ██████████  100% ⚠     │
│  Savings:  £X,XXX           │                                    │
│                             │                                    │
├─────────────────────────────┼────────────────────────────────────┤
│                             │                                    │
│  Spending by Category       │  Cash Flow Timeline                │
│  [Donut Chart]              │  [Area Chart - 6 months]           │
│                             │                                    │
├─────────────────────────────┴────────────────────────────────────┤
│                                                                  │
│  Recent Transactions                                             │
│  Date       | Name                | Category    | Amount         │
│  15 Jan     | The Deli            | Eating Out  | -£5.10         │
│  15 Jan     | Salary              | Income      | +£2,500.00     │
│  14 Jan     | Tesco               | Groceries   | -£34.50        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Trading Dashboard (accessed via tabs or `#/analytics`)

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  Win Rate    Profit Factor    Expectancy    Max Drawdown         │
│  58.3%       1.85             £45.20        -12.4%               │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Equity Curve                                                    │
│  [TradingView Lightweight Chart - Line/Area]                     │
│                                                                  │
├─────────────────────────────┬────────────────────────────────────┤
│                             │                                    │
│  P&L Distribution           │  R-Multiple Histogram              │
│  [Bar Chart]                │  [Bar Chart]                       │
│                             │                                    │
├─────────────────────────────┼────────────────────────────────────┤
│                             │                                    │
│  Win Rate by Strategy       │  Discipline vs Performance         │
│  [Horizontal Bar]           │  [Scatter Chart]                   │
│                             │                                    │
├─────────────────────────────┴────────────────────────────────────┤
│                                                                  │
│  Recent Trades                                                   │
│  Date    | Symbol | Direction | P&L      | R    | Strategy       │
│  15 Jan  | AAPL   | Long      | +£120    | 2.4R | Breakout       │
│  14 Jan  | EUR/USD| Short     | -£50     | -1R  | Mean Rev       │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Chart Library Usage

| Chart Type | Library | Usage |
|------------|---------|-------|
| Donut / Pie | Chart.js | Spending by category |
| Bar | Chart.js | Income vs expenses, P&L distribution, win rate by strategy |
| Line / Area | Chart.js | Cash flow timeline, net worth trend |
| Horizontal Bar | Chart.js | Budget progress |
| Scatter | Chart.js | Discipline vs performance correlation |
| Equity Curve (Line) | TradingView Lightweight | Account equity over time |
| Candlestick | TradingView Lightweight | Price charts (future: trade entry/exit overlay) |

---

## Deployment

### Host Environment

- **Machine:** Home PC (Windows 10) running alongside Jellyfin and other services
- **Tunnel:** Existing Cloudflare Tunnel via `cloudflared`
- **Runtime:** Docker Desktop for Windows (or WSL2)

### Docker Compose

```yaml
version: '3.8'

services:
  # === PRODUCTION (behind Cloudflare Access) ===
  jade-app:
    build: .
    container_name: jade-app
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./frontend:/app/frontend
    environment:
      - FLASK_ENV=production
      - DATABASE_PATH=/app/data/jade.db

  # === PUBLIC DEMO (no auth, resets daily) ===
  jade-demo:
    build: .
    container_name: jade-demo
    restart: unless-stopped
    ports:
      - "8001:8000"
    volumes:
      - ./demo-data:/app/data
      - ./frontend:/app/frontend
    environment:
      - FLASK_ENV=production
      - DATABASE_PATH=/app/data/jade.db
      - DEMO_MODE=true

  jade-demo-reset:
    image: alpine:3
    container_name: jade-demo-reset
    restart: unless-stopped
    volumes:
      - ./demo-data:/data
    entrypoint: /bin/sh
    command: >
      -c "while true; do
        sleep 86400;
        cp /data/seed.db /data/jade.db;
        echo 'Demo database reset at $$(date)';
      done"
    depends_on:
      - jade-demo

  # === BACKUP ===
  litestream:
    image: litestream/litestream:latest
    container_name: jade-litestream
    restart: unless-stopped
    volumes:
      - ./data:/app/data
      - ./litestream.yml:/etc/litestream.yml
    environment:
      - LITESTREAM_ACCESS_KEY_ID=${S3_ACCESS_KEY}
      - LITESTREAM_SECRET_ACCESS_KEY=${S3_SECRET_KEY}
    command: replicate
    depends_on:
      - jade-app
```

> **Note:** No Caddy/Nginx container needed. Cloudflare Tunnel handles HTTPS and routing. Flask serves both the API and static frontend files.

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Flask serves static files in production too (cloudflared handles the rest)
COPY frontend/ ./frontend/

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "app:create_app()"]
```

### requirements.txt

```
flask==3.1.*
gunicorn==23.*
```

### Cloudflare Tunnel Configuration

Add Jade to your existing tunnel. In the Cloudflare Zero Trust dashboard:

1. **Networks → Tunnels → your tunnel → Public Hostname → Add**
   - Subdomain: `jade`
   - Domain: `muhammadhazimiyusri.uk`
   - Type: `HTTP`
   - URL: `localhost:8000`

Or if you manage your tunnel config via `config.yml`:

```yaml
# Add to your existing cloudflared config.yml
ingress:
  # ... your existing services (Jellyfin, etc.) ...
  - hostname: jade.muhammadhazimiyusri.uk
    service: http://localhost:8000
  - service: http_status:404
```

### Litestream Config (`litestream.yml`)

```yaml
dbs:
  - path: /app/data/jade.db
    replicas:
      - type: s3
        bucket: jade-backups
        path: db
        endpoint: https://YOUR_R2_ENDPOINT
```

### Deployment Steps

```bash
# 1. Clone repo on home PC
git clone <repo> ~/jade && cd ~/jade

# 2. Create data directory
mkdir -p data

# 3. Set environment variables (only needed if using Litestream)
cp .env.example .env
# Edit .env with S3/R2 credentials

# 4. Launch
docker-compose up -d

# 5. Add public hostname in Cloudflare Zero Trust dashboard
#    (see Cloudflare Tunnel Configuration above)

# 6. Set up Cloudflare Access policy
#    (see Authentication & Security section)

# 7. Verify
curl http://localhost:8000/api/dashboard/finance   # local test
# Then visit https://jade.muhammadhazimiyusri.uk   # through tunnel
```

### Local Development (without Docker)

For day-to-day development, run Flask directly:

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Run development server
flask --app app run --debug --port 8000

# Frontend is served by Flask at http://localhost:8000
```

---

## Database Migrations

### Strategy

Numbered SQL migration files in `app/migrations/`. The `schema_version` table tracks which migrations have been applied.

### Migration Runner (in `db.py`)

```python
def run_migrations(db_path):
    """Apply any pending migrations in order."""
    conn = get_db(db_path)

    # Ensure schema_version table exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now')),
            description TEXT
        )
    """)

    current_version = conn.execute(
        "SELECT COALESCE(MAX(version), 0) FROM schema_version"
    ).fetchone()[0]

    migration_dir = Path(__file__).parent / 'migrations'
    for migration_file in sorted(migration_dir.glob('*.sql')):
        version = int(migration_file.stem.split('_')[0])
        if version > current_version:
            print(f"Applying migration {migration_file.name}...")
            conn.executescript(migration_file.read_text())
            conn.execute(
                "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                (version, migration_file.stem)
            )
            conn.commit()
```

### Migration File Naming

```
001_initial.sql          # Full schema creation
002_money_to_pence.sql   # Convert amount/local_amount from REAL to INTEGER pence
003_add_budgets.sql      # New feature tables
004_add_trade_tags.sql   # Schema additions
```

### Rules

- Migrations are **forward-only** — no rollbacks
- Each migration file must be idempotent where possible (`CREATE TABLE IF NOT EXISTS`)
- Never modify an existing migration file — always create a new one
- Test migrations on a copy of production database before deploying

---

## Development Roadmap

> **Current Phase: Phase 1 — working on 1.7**
>
> When completing a task, update this README: check the box `[x]` and update the Project Structure status icons from 🔲 to ✅ for any files created.

### Phase 1: Foundation ✦ PRIORITY
> Personal finance core — get transactions in, display them, categorise them.

- [x] **1.1** Project scaffolding: Flask app factory, SQLite setup, PRAGMA config
- [x] **1.2** Database schema: `schema_version`, `transactions`, `categories` tables
- [x] **1.3** Seed default categories on first run
- [x] **1.4** Transaction CRUD API endpoints
- [x] **1.5** Frontend shell: `index.html`, CSS design system, router, sidebar nav
- [x] **1.6** Transactions list view with pagination, sorting, filtering
- [ ] **1.7** Manual transaction add/edit forms
- [ ] **1.8** Category management (list, create custom, assign colours)

### Phase 2: Monzo Integration
> CSV upload, parsing, dedup, and import flow.

- [ ] **2.1** CSV parser service with Monzo 16-column format validation and saved import profile
- [ ] **2.2** Upload API endpoint with file validation (CSV, ≤10MB)
- [ ] **2.3** Deduplication via `monzo_id`
- [ ] **2.4** Upload UI with drag-and-drop, progress indicator, import summary
- [ ] **2.5** Post-import transaction review (highlight new imports)
- [ ] **2.6** Category rules engine — auto-categorise on import using keyword matching

### Phase 3: Finance Dashboard
> Charts, budgets, and spending insights.

- [ ] **3.1** Budget CRUD API and UI
- [ ] **3.2** Dashboard API: balance, income/expenses, budget status
- [ ] **3.3** Finance dashboard view with Chart.js integration
- [ ] **3.4** Spending by category donut chart
- [ ] **3.5** Income vs expenses bar chart (monthly, 6-month view)
- [ ] **3.6** Cash flow area chart
- [ ] **3.7** Budget progress bars with warnings at 80%/100%
- [ ] **3.8** Spending reports with period comparison (this month vs last)
- [ ] **3.9** Date range selector component

### Phase 4: Trading Journal
> Trade logging, accounts, strategies, and the full trade form.

- [ ] **4.1** Trading accounts CRUD API and UI
- [ ] **4.2** Strategies CRUD API and UI
- [ ] **4.3** Tags CRUD and trade-tag association
- [ ] **4.4** Trade CRUD API with all fields
- [ ] **4.5** Trade form (new/edit) — multi-step or tabbed for all fields
- [ ] **4.6** Trade list view with filters (account, asset class, symbol, strategy, open/closed)
- [ ] **4.7** Trade detail view with full info
- [ ] **4.8** Close trade flow (enter exit price/date → auto-calculate P&L, R-multiple)
- [ ] **4.9** `trade_calculator.py` — all per-trade calculations
- [ ] **4.10** Daily journal CRUD API and UI

### Phase 5: Trading Analytics
> Performance metrics, equity curves, and discipline tracking.

- [ ] **5.1** Aggregate metrics calculator (win rate, profit factor, expectancy, etc.)
- [ ] **5.2** Account snapshots: daily balance recording
- [ ] **5.3** Trading dashboard: KPI cards (win rate, PF, expectancy, max DD)
- [ ] **5.4** Equity curve with TradingView Lightweight Charts
- [ ] **5.5** P&L distribution histogram
- [ ] **5.6** R-multiple histogram
- [ ] **5.7** Win rate by strategy breakdown
- [ ] **5.8** Discipline vs performance scatter chart
- [ ] **5.9** Streak tracking (consecutive wins/losses)
- [ ] **5.10** Filterable reports by period, account, asset class, strategy

### Phase 6: Deployment & Polish
> Docker, Cloudflare Tunnel, demo mode, backups, and final touches.

- [ ] **6.1** Dockerfile and docker-compose.yml (production + demo containers)
- [ ] **6.2** Flask static file serving (frontend served by Flask, no separate web server)
- [ ] **6.3** `DEMO_MODE` flag: banner display + response header
- [ ] **6.4** Demo seed data script (`demo-data/seed.sql`) with ~500 transactions, ~85 trades, journals
- [ ] **6.5** Build `seed.db` from seed script, configure daily reset container
- [ ] **6.6** Cloudflare Tunnel public hostname config (production + demo)
- [ ] **6.7** Cloudflare Access policy setup for production (demo is public)
- [ ] **6.8** Litestream backup configuration (production only)
- [ ] **6.9** Settings page (manage accounts, strategies, categories, data export)
- [ ] **6.10** Toast notifications for actions
- [ ] **6.11** Loading states and empty states
- [ ] **6.12** Mobile responsive layout
- [ ] **6.13** Error handling (API errors, network failures, form validation)
- [ ] **6.14** README cleanup and final documentation

### Future Ideas (Post-MVP)

- [ ] Recurring transaction detection and budget forecasting
- [ ] Trade screenshot upload and attachment to trades
- [ ] CSV/JSON data export
- [ ] Trade import from broker CSV exports
- [ ] Webhook for Monzo real-time transaction sync
- [ ] PWA support for mobile home screen
- [ ] Multi-currency support with exchange rate conversion

---

## Development Guidelines

### For Claude Code

This README is the **single source of truth**. When developing:

1. **Always read this README first** before implementing any feature
2. **Follow the phase order** — don't skip ahead
3. **Match the file structure exactly** as defined above
4. **Use the exact database schema** — column names, types, and constraints as specified
5. **API endpoints must match** the specification above
6. **Follow the branding** — colours, fonts, spacing as defined
7. **No external dependencies** beyond what's listed in the tech stack
8. **SQL queries must use parameterised statements** — never string formatting
9. **All monetary values stored as integer pence in SQLite** — converted to/from decimal at the API boundary
10. **Test each endpoint** before moving to the next task

### README Maintenance (CRITICAL)

**The README must always reflect the actual state of the project.** After every task:

1. **Project Structure:** Change 🔲 to ✅ for any files you just created
2. **Roadmap:** Check the box `[x]` for completed tasks
3. **Current Phase:** Update the "Current Phase" line at the top of the roadmap
4. **Never add planned items as if they exist** — only mark ✅ when the file is real
5. **If you change a schema, API, or structure** — update the relevant README section to match
6. **The README describes what IS, not what WILL BE** — planned items are explicitly marked as planned

### Code Style

- **Python:** Follow PEP 8, use type hints, docstrings on all functions
- **JavaScript:** ES6 modules, `const`/`let` (never `var`), template literals for HTML
- **CSS:** Custom properties (CSS variables) for all colours, BEM-ish naming
- **SQL:** Uppercase keywords, lowercase identifiers, 4-space indentation

### Commit Convention

```
feat(transactions): add pagination to GET /api/transactions
fix(csv-parser): handle empty Amount field in Monzo export
style(dashboard): align budget progress bars
refactor(db): extract connection management to db.py
docs: update README roadmap checkboxes
```

---

*Built with 💎 by Jade — your finances, your data, your control.*