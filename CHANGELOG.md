# Changelog

All notable changes to Jade are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> Pre-1.0 versions track development phases. Minor bumps (0.x.0) correspond
> to completed roadmap phases. Patch bumps (0.x.y) correspond to tasks within
> a phase.

---

## [Unreleased]

---

## [0.1.2] — 2026-03-01

### Added

#### Phase 1.4 — Transaction CRUD API

- `app/services/transactions.py`: service layer with five public functions and
  private helpers for validation:
  - `list_transactions()` — paginated, filtered query with dynamic WHERE clause;
    supports category, type, date range, full-text search (name/notes/description),
    amount range, sort field, and order direction
  - `get_transaction()` — single row lookup by primary key; returns `None` if not found
  - `create_transaction()` — INSERT with required-field checks, ISO 8601 date
    validation, non-zero amount validation, and category existence check;
    derives `is_income` automatically from the sign of `amount`
  - `update_transaction()` — partial UPDATE restricted to `_UPDATABLE_FIELDS`;
    re-derives `is_income` when `amount` changes; sets `updated_at = datetime('now')`
    via SQL literal for consistent UTC timestamps
  - `delete_transaction()` — DELETE by ID; returns `bool` indicating whether a row
    was actually removed
  - Private helpers: `_validate_iso_date()`, `_validate_amount()`,
    `_validate_category()`, `_row_to_dict()`

- `app/routes/transactions.py`: Blueprint registered at `/api/transactions`:
  - `GET /api/transactions` — list with pagination envelope
    (`transactions`, `pagination.page/per_page/total/total_pages/has_next/has_prev`)
    and all query-param filters
  - `GET /api/transactions/<id>` — single transaction or 404
  - `POST /api/transactions` — create; returns 201 with full created row
  - `PUT /api/transactions/<id>` — partial update; returns 200 with updated row,
    404 if not found, 422 on validation error
  - `DELETE /api/transactions/<id>` — returns 204 No Content or 404

- Blueprint registered in `app/__init__.py`

### Validation rules
- `sort` field whitelisted against `_SORTABLE_FIELDS` (prevents ORDER BY injection)
- `order` accepted only as `'asc'` or `'desc'`; route returns 400 for invalid values
- `date` validated with `datetime.fromisoformat()` (handles `Z`-suffix for Python 3.10 compat)
- `amount` validated as non-zero float; zero triggers 422
- `category` validated against `categories` table on create/update
- `name` validated as non-empty string after stripping whitespace
- `per_page` capped at 200 in the service layer

---

## [0.1.1] — 2026-03-01

### Added

#### Phase 1.3 — Default Category Seeding
- `_DEFAULT_CATEGORIES` constant in `app/db.py`: 16 Monzo-standard categories
  with name (snake_case), display label, hex colour, emoji icon, and sort order:

  | # | name | label | colour |
  |---|------|-------|--------|
  | 0 | `general` | General | `#6B7280` |
  | 1 | `eating_out` | Eating Out | `#F59E0B` |
  | 2 | `groceries` | Groceries | `#10B981` |
  | 3 | `transport` | Transport | `#3B82F6` |
  | 4 | `shopping` | Shopping | `#8B5CF6` |
  | 5 | `entertainment` | Entertainment | `#EC4899` |
  | 6 | `bills` | Bills | `#EF4444` |
  | 7 | `expenses` | Expenses | `#F97316` |
  | 8 | `holidays` | Holidays | `#14B8A6` |
  | 9 | `personal_care` | Personal Care | `#A855F7` |
  | 10 | `family` | Family | `#F43F5E` |
  | 11 | `charity` | Charity | `#6366F1` |
  | 12 | `finances` | Finances | `#0EA5E9` |
  | 13 | `cash` | Cash | `#84CC16` |
  | 14 | `income` | Income | `#22D3EE` |
  | 15 | `savings` | Savings | `#00A86B` |

- `seed_categories(app)` in `app/db.py`: inserts the 16 defaults using
  `INSERT OR IGNORE` — fully idempotent, safe to run on every startup
- `init_db(app)` updated: now calls `seed_categories(app)` after
  `run_migrations(app)`, so categories are always present before any
  request is served

---

## [0.1.0] — 2026-02-28

### Added

#### Phase 1.1 — Project Scaffolding
- `requirements.txt` pinning `flask==3.1.*` and `gunicorn==23.*`
- `app/__init__.py`: Flask app factory (`create_app()`) with:
  - `DATABASE_PATH` config from environment (defaults to `data/jade.db`)
  - `DEMO_MODE` config from environment (`DEMO_MODE=true` activates demo banner header)
  - `X-Demo-Mode: true` response header when demo mode is active
  - Defence-in-depth security headers on every response:
    `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`,
    `Referrer-Policy`, `Content-Security-Policy`
  - `GET /` and `GET /<path>` routes to serve the frontend SPA from `frontend/`
  - `teardown_appcontext` registration for `close_db`
  - Automatic DB initialisation (migration runner) on startup
- `app/db.py`: SQLite connection manager with:
  - `get_db()` — request-scoped connection via `flask.g`; sets `row_factory = sqlite3.Row`
  - PRAGMAs applied on every new connection:
    `journal_mode = WAL`, `foreign_keys = ON`, `busy_timeout = 5000`, `synchronous = NORMAL`
  - `close_db(e)` — teardown callback; pops and closes `g.db`
  - `init_db(app)` — ensures `data/` directory exists, then triggers migration runner
  - `run_migrations(app)` — numbered SQL file runner; bootstraps `schema_version` table;
    applies any `.sql` files in `app/migrations/` whose version exceeds the recorded max
- `app/routes/__init__.py`, `app/services/__init__.py`, `app/utils/__init__.py` — package skeletons
- `app/migrations/` — empty directory ready for migration files
- `data/` directory (gitignored for `*.db` files; `.gitkeep` tracks the directory)
- `.gitignore` covering database files, Python caches, virtualenvs, and `.env` files

#### Phase 1.2 — Database Schema
- `app/migrations/001_initial.sql`: idempotent (`CREATE TABLE IF NOT EXISTS`) migration creating:
  - `transactions` table — full Monzo-compatible schema with signed decimal `amount`,
    `monzo_id` unique constraint for deduplication, `is_income` derived flag,
    `custom_category` override, and ISO 8601 date fields
  - Indexes: `idx_transactions_date`, `idx_transactions_category`, `idx_transactions_amount`
  - `categories` table — `name` (snake_case key), `label` (display), `colour` (hex),
    `icon`, `is_default`, `sort_order`
- `app/schema.sql`: full schema reference document covering all planned tables across all
  six phases, with `(created)` / `(planned)` status annotations

### Fixed
- README Project Structure: corrected `frontend/` comment from "served by Caddy" to
  "served by Flask" (no Caddy/Nginx in this stack — Flask serves all static files directly)

### Infrastructure
- `VERSION` file tracking semver; `__version__` constant in `app/__init__.py`

---

[Unreleased]: https://github.com/jimi-coding/jade-personal-finance-app/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/jimi-coding/jade-personal-finance-app/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/jimi-coding/jade-personal-finance-app/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/jimi-coding/jade-personal-finance-app/releases/tag/v0.1.0
