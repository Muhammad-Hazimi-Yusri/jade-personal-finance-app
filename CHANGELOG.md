# Changelog

All notable changes to Jade are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> Pre-1.0 versions track development phases. Minor bumps (0.x.0) correspond
> to completed roadmap phases. Patch bumps (0.x.y) correspond to tasks within
> a phase.

---

## [Unreleased]

### Changed

#### Integer Pence Money Storage

- `app/migrations/001_initial.sql`: `amount` and `local_amount` columns changed from
  `REAL` to `INTEGER` (pence) for fresh installs
- `app/migrations/002_money_to_pence.sql`: new migration that recreates the
  `transactions` table with `INTEGER` money columns and converts existing decimal
  values to pence (× 100)
- `app/services/transactions.py`: added `_to_pence()` / `_from_pence()` conversion
  at the service boundary using `Decimal` for exact arithmetic:
  - Inbound: API decimal → integer pence before DB write
  - Outbound: integer pence → decimal float in `_row_to_dict()`
  - Amount filters (`min_amount`, `max_amount`) converted to pence before querying
  - `local_amount` converted on create and update
- `app/routes/transactions.py`: updated docstrings to clarify decimal API convention

---

## [0.1.6] — 2026-03-15

### Added

#### Phase 1.8 — Category Management

- `app/services/categories.py`: service layer with five public functions and
  private helpers for validation:
  - `list_categories()` — returns all categories ordered by sort_order then label
  - `get_category()` — single row lookup by primary key; returns `None` if not found
  - `create_category()` — INSERT with label/colour/icon validation; auto-generates
    snake_case `name` from label via `_slugify_label()`; auto-assigns `sort_order`
    as `MAX(sort_order) + 1`; catches `IntegrityError` for duplicate names
  - `update_category()` — partial UPDATE of label, colour, icon, sort_order;
    `name` is immutable once created
  - `delete_category()` — refuses default categories (`is_default = 1`) and
    categories in use by transactions (returns count of referencing transactions)
  - Private helpers: `_validate_label()`, `_validate_colour()`, `_slugify_label()`,
    `_row_to_dict()` (aliases DB column `label` → API field `display_name`)

- `app/routes/categories.py`: expanded from read-only to full CRUD Blueprint:
  - `GET /api/categories/` — list all categories (was broken: queried non-existent
    `display_name` column — fixed by delegating to service layer with alias)
  - `GET /api/categories/<id>` — single category or 404
  - `POST /api/categories/` — create custom category; returns 201 or 422
  - `PUT /api/categories/<id>` — update category; returns 200, 404, or 422
  - `DELETE /api/categories/<id>` — delete custom category; returns 204, 404,
    or 409 (default or in-use protection)

- `frontend/js/views/settings.js`: full category management UI replacing stub:
  - **Categories table**: colour swatch, icon + label, snake_case name (mono),
    type badge (Default/Custom), Edit/Delete action buttons
  - **Inline add/edit form**: label input (required), native `<input type="color">`
    with live swatch preview and hex readout, optional icon input, Save/Cancel
    buttons; Enter key submits
  - **Delete flow**: confirmation dialog; handles 409 (in-use) errors with
    inline error message showing transaction count
  - **State management**: `formMode` (add/edit/null) and `editId` track form state;
    table re-renders after every mutation

- `frontend/css/style.css`: new component styles:
  - `.colour-swatch` — 16px circle with border for displaying category colours
  - `.colour-input-group` — flex row for colour picker + preview swatch + hex label
  - `input[type="color"]` — styled native colour picker matching dark theme

### Fixed

- `app/routes/categories.py`: `GET /api/categories/` was querying `display_name`
  column which does not exist in the database (column is `label`). Fixed by
  moving query to service layer which aliases `label AS display_name`

---

## [0.1.5] — 2026-03-15

### Added

#### Phase 1.7 — Manual Transaction Add/Edit Forms

- `frontend/js/views/transaction-form.js`: dual-mode form view for creating and
  editing transactions:
  - **Add mode** (`#/transactions/new`): empty form with date defaulted to today;
    submits `POST /api/transactions/` on save
  - **Edit mode** (`#/transactions/edit/:id`): loads existing transaction via
    `GET /api/transactions/:id` and pre-populates all fields; submits
    `PUT /api/transactions/:id` on save; includes Delete button with
    confirmation dialog
  - **Primary fields**: Date (date input), Name (text), Amount (number with
    step="0.01" — negative for expenses, positive for income), Category (select
    populated from `/api/categories/`), Notes (textarea)
  - **Optional fields**: Type and Currency in a collapsible `<details>` section
  - **Client-side validation**: required field checks with `.form-group--error`
    red border highlighting and an error banner listing all issues
  - **Save state management**: disables save button and shows "Saving…" text
    during API call; re-enables on error
  - **Error handling**: displays server error messages inline; shows full error
    state if transaction not found in edit mode

- `frontend/js/views/transactions.js`: updated list view with navigation:
  - "+ Add Transaction" primary button in the page header
  - Table rows are clickable (`cursor: pointer`) — clicking navigates to
    `#/transactions/edit/:id` for inline editing

- `frontend/js/app.js`: routing updates:
  - Added `transactions/new` and `transactions/edit` routes pointing to
    `transaction-form.js`
  - Upgraded prefix matching in `handleRoute()` from single-segment to
    progressive multi-segment matching — tries `a/b` before `a`, enabling
    `transactions/edit/5` to resolve to the `transactions/edit` route

- `frontend/css/style.css`: new form component styles:
  - `.form-group--error` — red border on invalid inputs
  - `.form-hint` — small muted text below inputs
  - `.form-actions` — flex bar with top border for Save/Cancel/Delete buttons
  - `.tx-row-clickable` — pointer cursor for clickable table rows
  - `details summary` — styled collapsible section headers

---

## [0.1.4] — 2026-03-01

### Added

#### Phase 1.6 — Transactions List View

- `app/routes/categories.py`: read-only Blueprint at `/api/categories`:
  - `GET /api/categories/` — returns all 16 categories ordered by `display_name`;
    each object includes `id`, `name`, `display_name`, `colour`, `icon`, `is_default`
  - Registered in `app/__init__.py` alongside the transactions blueprint

- `frontend/js/views/transactions.js`: full transactions list view:
  - **Filter bar** (card): live search (debounced 300ms) across name/notes/description;
    category dropdown populated from `/api/categories/`; start/end date pickers;
    Clear button resets all filters
  - **Sortable table**: columns Date, Name, Category, Amount — clicking a header sorts
    by that column (`desc` first); clicking the active column toggles `asc`/`desc`;
    active column highlighted with `↑`/`↓` indicator in primary colour
  - **Category display**: resolves raw `category` snake_case name to human `display_name`
    via the cached categories response; falls back to raw name gracefully
  - **Amount formatting**: uses `formatCurrency()` — coloured red (expense) / green (income),
    monospaced, typographic minus sign
  - **Pagination bar**: shows `start–end of total` count; Page X of Y; Prev/Next buttons
    disabled at boundaries
  - **Empty state**: friendly message when no transactions match current filters
  - **Error state**: displays API error message inline if fetch fails
  - Module-level state (`page`, `sort`, `order`, `search`, `category`, `startDate`,
    `endDate`) reset on each `render()` call for clean navigation

---

## [0.1.3] — 2026-03-01

### Added

#### Phase 1.5 — Frontend Shell

- `frontend/index.html`: SPA entry point with:
  - Google Fonts CDN (`Inter`, `JetBrains Mono`)
  - Chart.js and TradingView Lightweight Charts CDN `<script defer>` (used from Phase 3+)
  - `.app-layout` flex container: fixed sidebar + scrollable main content area
  - Two-section sidebar nav: **Finance** (Dashboard, Transactions, Upload CSV, Budgets)
    and **Trading** (Trade Log, New Trade, Analytics, Journal), plus Settings
  - `<script type="module">` bootstrap for `js/app.js`

- `frontend/css/style.css`: full design system (~280 lines):
  - CSS custom properties for all colours, fonts, spacing (8px grid), and border radii
    from README Branding section
  - CSS reset (box-sizing, margins)
  - Layout: `.app-layout`, `.sidebar` (240px, `var(--color-surface)`, border-right),
    `.sidebar-header`, `.main-content` (flex-grow, overflow-y scroll)
  - Navigation: `.nav-list`, `.nav-section-label`, `.nav-link` with active state
    (left border accent + primary colour background tint), `.nav-divider`
  - Base components: `.card`, `.card-title`, `.page-header`, `.btn` / `.btn-primary` /
    `.btn-ghost` / `.btn-danger`, `.badge` variants (success/danger/warning/info/neutral)
  - Form elements: `.form-group`, `input`, `select`, `textarea` with focus border
  - Table: `table`, `thead th`, `tbody td` with hover rows, `.td-right` alignment
  - Utility classes: `.text-success/danger/warning/info/muted/secondary`, `.mono`,
    `.font-medium/semibold`, `.flex`, `.grid-2/3/4`, `.gap-*`, `.mt-*/mb-*`
  - State classes: `.loading`, `.error-state`, `.empty-state`

- `frontend/js/app.js`: hash-based SPA router:
  - Route map for all 9 views using dynamic `import()` for code splitting
  - `handleRoute()`: parses `window.location.hash`, resolves route (exact + prefix
    fallback for nested paths like `trades/123`), dynamically imports view module,
    calls `render(container)`, handles errors with inline error state display
  - `updateActiveNav()`: applies `.active` class to matching sidebar link on each route change
  - Initialises on `DOMContentLoaded`; defaults empty hash to `#/`

- `frontend/js/api.js`: fetch wrapper (`api.get/post/put/del`):
  - Sets `Content-Type: application/json` on all requests
  - Parses JSON response body; extracts `error`/`message` field for readable error throws
  - Throws `Error` on any non-2xx response

- `frontend/js/utils.js`: shared formatting helpers:
  - `formatCurrency(amount, coloured)` — `£1,234.56` with `text-success`/`text-danger`
    colour classes and typographic minus sign; `mono` font class applied
  - `formatDate(isoString)` — `15 Jan 2024` (en-GB locale)
  - `formatDateShort(isoString)` — `15/01/24`
  - `escHtml(str)` — HTML entity escaping for safe template literal interpolation

- `frontend/js/views/*.js`: stub view modules for all 9 routes so navigation works
  without JS errors before views are fully implemented:
  `dashboard.js`, `transactions.js`, `upload.js`, `budgets.js`, `trades.js`,
  `trade-form.js`, `trade-analytics.js`, `journal.js`, `settings.js` —
  each exports `async function render(container)` with a placeholder message

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
  - `transactions` table — full Monzo-compatible schema with signed integer pence `amount`,
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

[Unreleased]: https://github.com/jimi-coding/jade-personal-finance-app/compare/v0.1.6...HEAD
[0.1.6]: https://github.com/jimi-coding/jade-personal-finance-app/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/jimi-coding/jade-personal-finance-app/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/jimi-coding/jade-personal-finance-app/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/jimi-coding/jade-personal-finance-app/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/jimi-coding/jade-personal-finance-app/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/jimi-coding/jade-personal-finance-app/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/jimi-coding/jade-personal-finance-app/releases/tag/v0.1.0
