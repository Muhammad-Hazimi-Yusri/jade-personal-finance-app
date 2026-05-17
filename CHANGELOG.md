# Changelog

All notable changes to Jade are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> Pre-1.0 versions track development phases. Minor bumps (0.x.0) correspond
> to completed roadmap phases. Patch bumps (0.x.y) correspond to tasks within
> a phase.

---

## [Unreleased]

### Fixed

- **Dashboard expense totals no longer include internal transfers**
  Pot transfers, Flex repayments, and Faster Payments to Moneybox / Trading 212
  / Seccl were all being counted as "expenses" by the dashboard because the
  aggregations treated every negative-amount transaction as spending. For
  example, a 6-month window containing ~£13k of pot moves and investment
  contributions was showing expenses of £17.7k against actual consumer
  spending closer to £4k.
  - `csv_parser._detect_transfer_category` now standardises these rows into
    the `savings` and `transfers` categories at import time (new Tier 1b in
    the categorisation pipeline).
  - `dashboard.get_summary`, `get_income_vs_expenses`,
    `get_spending_by_category`, `get_cash_flow` and
    `reports.get_spending_comparison` exclude `savings` and `transfers` from
    income/expense sums (running balance is unaffected).
  - Migration `011_recategorize_transfers.sql` retroactively updates existing
    rows on next startup; **Settings → Maintenance → Re-categorise transfers**
    (POST `/api/transactions/recategorize-transfers`) provides the same fix
    on demand. Both paths skip rows where the user has set `custom_category`.
  - New test suite `tests/test_dashboard_transfers.py` (26 tests).

---

## [0.6.7] — 2026-04-18

### Added

#### Phase 6.7 — Cloudflare Access policy setup for production (demo is public)

- New **`cloudflared/access.yml`** — reference doc capturing the production
  Cloudflare Access application (`jade.muhammadhazimiyusri.uk`) and its
  `Allow owner` email policy (24h session, self-hosted, no IdP lock-in).
  Pairs with the existing `cloudflared/config.yml` ingress reference so the
  repo remains the single source of truth for deployment topology. Includes
  a dashboard runbook and an explicit `public_hostnames:` section noting
  that `jade-demo.muhammadhazimiyusri.uk` must NOT be placed behind Access.
- **`cloudflared/config.yml`** — added a cross-reference comment pointing at
  `access.yml` and reiterating that the demo hostname stays public.
- **README Cloudflare Access Setup** — links to the committed reference,
  adds the application name and session-duration fields that the dashboard
  expects, and calls out the "do not protect the demo" rule as an explicit
  step with an incognito-window verification tip.

### Fixed

- `__version__` in `app/__init__.py` and the `VERSION` file bumped to
  `0.6.7` alongside this task.

---

## [0.6.5] — 2026-04-18

### Added

#### Phase 6.5 — Build `seed.db` from seed script and configure daily reset container

- New **`demo-data/build_seed_db.py`** script — builds a clean, single-file
  `seed.db` snapshot from `seed.sql`. Wipes any existing `seed.db` (plus
  WAL/SHM sidecars), creates a fresh SQLite database via the real Flask
  `init_db()` pipeline (migrations + default categories + Monzo import
  profile), loads `seed.sql` into it, then checkpoints the WAL and switches
  to `journal_mode=DELETE` so the resulting file is a single compact
  artefact the reset sidecar can `cp` atomically. Prints a row-count summary
  per table on completion.
- **`jade-demo-reset` sidecar rewritten** to align to **03:00 UTC** instead
  of sleeping 24h from container start. Performs an initial reset on
  startup (so the demo always boots from a known state), then loops
  forever, sleeping until the next 03:00 UTC boundary and restoring
  `jade.db` from `seed.db`. Uses epoch-second arithmetic to stay portable
  across busybox `ash` (no bash-only `10#` base prefix). Every reset also
  removes `jade.db-wal` / `jade.db-shm` so the running Flask process
  reopens a pristine snapshot. Fails fast with a helpful message if
  `seed.db` is missing, pointing the operator at `build_seed_db.py`.
- Documented the build-and-reset flow in the README (Demo Seed Data and
  Daily Reset Mechanism sections).

### Fixed

- `__version__` in `app/__init__.py` and the `VERSION` file drifted from
  the v0.6.4 release; bumped to `0.6.5` alongside this task.

---

## [0.6.3] — 2026-04-05

### Added

#### Phase 6.3 — DEMO_MODE flag: banner display + response header

- New **`GET /api/meta`** endpoint — returns `{"version": "...", "demo_mode": true/false}`.
  Used by the frontend to detect demo mode without parsing response headers.
- **Demo mode banner** — a full-width warning bar rendered above the app layout
  when `DEMO_MODE=true`. Displays "Demo Mode — data resets daily. All changes
  are discarded." Implemented via `initDemoBanner()` in `app.js`, which fetches
  `/api/meta` once on startup and removes the `hidden` attribute if `demo_mode`
  is enabled.
- **`X-Demo-Mode: true`** response header already applied to all responses via
  `after_request` hook (present since 0.6.2 scaffold); now surfaced to users via
  the banner.
- Documented `DEMO_MODE=false` in `.env.example`.

---

## [0.5.7] — 2026-04-04

### Added

#### Phase 5.7 — Win rate by strategy breakdown

- New **`GET /api/reports/win-rate-by-strategy`** endpoint — returns win/loss
  counts and win rate percentage grouped by strategy for closed trades.
  Accepts the same filter params as other report endpoints
  (`account_id`, `strategy_id`, `asset_class`, `start_date`, `end_date`).
- New **`get_win_rate_by_strategy()`** function in
  `app/services/metrics_calculator.py` — queries trades joined with the
  strategies table (LEFT JOIN), groups by `strategy_id`, and computes
  `win_rate` per group in Python.  Trades with no strategy are labelled
  `"No strategy"`.
- New **Win Rate by Strategy** card on the analytics dashboard — Chart.js
  horizontal bar chart showing win rate (%) per strategy.  Bar colour
  indicates performance: green (≥60%), amber (40–59%), red (<40%).
  Tooltip shows wins, losses, and total trade count per strategy.

---

## [0.5.4] — 2026-04-03

### Added

#### Phase 5.4 — Equity curve with TradingView Lightweight Charts

- New **`GET /api/reports/equity-curve`** endpoint — returns cumulative P&L
  data points from closed trades, grouped by exit date, ordered chronologically.
  Accepts the same filter params as `/api/reports/trading-performance`
  (`account_id`, `strategy_id`, `asset_class`, `start_date`, `end_date`).
- New **`get_equity_curve()`** function in `app/services/metrics_calculator.py` —
  groups closed trades by `exit_date`, sums `pnl_net` per day (integer pence),
  then builds the running cumulative sum, converting to decimal at the API
  boundary. Trades with `NULL` `exit_date` or `pnl_net` are excluded.
- **Equity curve card** added to the trading analytics dashboard
  (`frontend/js/views/trade-analytics.js`) — appears above the KPI cards.
  Rendered with TradingView Lightweight Charts (area series, jade-green line,
  dark theme matching the design system). Chart respects all existing filters
  and auto-resizes via `ResizeObserver`. Handles empty data, fetch errors, and
  missing CDN gracefully with inline fallback messages.

---

## [0.3.9] — 2026-03-26

### Added

#### Phase 3.9 — Date range selector component

- New **reusable date range selector** component
  (`frontend/js/components/date-range-selector.js`) — the app's first shared
  UI component. Preset quick-selects (This Month, Last Month, 3M, 6M, 12M,
  YTD) plus custom date range with Apply button.
- Dashboard and reports APIs now accept `start_date` / `end_date` query
  parameters (ISO 8601) for flexible date-range filtering.
- Reports API auto-computes the comparison "previous period" by shifting the
  selected range back by its duration.

### Changed

- **Dashboard** — replaced per-chart 3m/6m/12m period selectors with a single
  page-level date range selector that controls all charts and KPIs at once.
  KPI labels now reflect the selected period dynamically.
- **Spending by Category** donut chart now respects the selected date range
  (previously locked to current month).
- **Reports view** — added date range selector; users can now compare any
  period, not just current vs last month.
- Dashboard summary response keys renamed: `month_income` → `income`,
  `month_expenses` → `expenses`, `month_net` → `net`.

---

## [0.3.8] — 2026-03-26

### Added

#### Phase 3.8 — Spending reports with period comparison

- New **Spending Reports** view at `#/reports` comparing this month vs last
  month spending by category.
- Backend: `GET /api/reports/spending` endpoint with period comparison query
  using conditional aggregation — returns per-category current/previous
  totals, change amounts, and percentage variance.
- Frontend: summary KPI cards (current month, last month, change with
  directional arrow), horizontal grouped bar chart (current vs previous per
  category, top 10), and full category breakdown table with change indicators.
- Colour-coded change indicators: green when spending decreased (good),
  red when spending increased (bad), muted when unchanged.
- "Reports" nav link added under Finance section in sidebar.
- New service layer `app/services/reports.py` and route blueprint
  `app/routes/reports.py`.

---

## [0.3.7] — 2026-03-25

### Changed

#### Phase 3.7 — Budget progress bars with warnings at 80%/100%

- Added warning badges on budget bars: "Caution" (amber) at 80% and "Over"
  (red) at 100%+ thresholds.
- Budgets now sorted by urgency — highest spend percentage appears first.
- Added summary headline above bars showing "X of Y on track" with caution/over
  count badges.
- Each bar now shows "£X left" or "£X over" beneath the spent/budget amounts.
- Added subtle pulse animation on over-budget bar fills to draw attention.
- Removed plain ⚠ emoji in favour of styled badge indicators.

---

## [0.3.6] — 2026-03-25

### Changed

#### Phase 3.6 — Enhanced cash flow area chart

- Replaced basic single-line area chart with a mixed bar+line chart: monthly
  net cash flow as green/red bars (positive/negative) with a cumulative running
  balance line overlay in blue.
- Backend `get_cash_flow()` now returns `income`, `expenses`, `net`, and
  `cumulative` per month (previously only `net`).
- Added 3m/6m/12m period selector that re-fetches data from the API.
- Added summary stats below chart: total inflow, total outflow, net change,
  and end balance for the selected period.
- Tooltips now show net, cumulative, income, and expenses simultaneously on
  hover using Chart.js index interaction mode.
- Added empty state handling when no cash flow data exists for the selected
  period.

---

## [0.3.5] — 2026-03-25

### Changed

#### Phase 3.5 — Enhanced income vs expenses bar chart

- Enhanced income vs expenses bar chart with a net income/loss line overlay
  (jade green, computed as income − expenses per month), a 3m/6m/12m period
  selector that re-fetches data from the API, and summary stats below the chart
  showing total income, total expenses, and average monthly net for the period.
- Current month bars are highlighted with higher opacity for visual distinction.
- Tooltips now show all three values (income, expenses, net) simultaneously on
  hover using Chart.js index interaction mode.
- Added empty state handling when no income or expense data exists for the
  selected period.

---

## [0.3.4] — 2026-03-25

### Changed

#### Phase 3.4 — Spending by category donut chart

- Enhanced spending doughnut chart with grand total displayed in the centre
  hollow, percentage in tooltips alongside pound amounts, and a clickable
  category breakdown list replacing the default Chart.js legend. Each list
  item shows a colour swatch, category name, amount, and percentage. Clicking
  a row toggles that segment's visibility on the chart.
- `app/services/dashboard.py`: `get_spending_by_category()` now returns a
  `percentage` field (0–100) for each category item, computed server-side.

---

## [0.3.3] — 2026-03-25

### Added

#### Phase 3.3 — Finance dashboard view with Chart.js integration

- `frontend/js/views/dashboard.js`: full dashboard view replacing stub. Fetches
  `/api/dashboard/finance` and `/api/categories/` in parallel. Renders five
  sections: KPI summary cards (balance, income, expenses, net, savings rate),
  income vs expenses grouped bar chart, budget progress bars with colour-coded
  thresholds (green/warning/danger at 80%/100%), spending by category doughnut
  chart using category colours from the database, cash flow area chart with
  jade-green fill, and a clickable recent transactions table.

- `frontend/css/style.css`: dashboard-specific CSS — `.kpi-grid` (5-column
  responsive grid), `.kpi-card` with label/value layout, `.dash-grid` (2-column
  chart layout), `.budget-bar` progress components with track/fill, `.chart-wrap`
  for Chart.js canvas containers, responsive breakpoints at 900px and 600px.

- Chart.js dark-mode defaults: muted axis text, border colour matching design
  system, Inter font family. All three charts (bar, doughnut, line) configured
  with dark-mode-appropriate colours and tooltips with £ formatting.

- Empty and loading states: spinner while fetching, friendly empty message when
  no transactions exist, per-section empty handling for spending chart and
  budget bars.

---

## [0.3.2] — 2026-03-21

### Added

#### Phase 3.2 — Dashboard API: balance, income/expenses, budget status

- `app/services/dashboard.py`: dashboard aggregation service with six data
  sections — summary KPIs (balance, income, expenses, net, savings rate),
  income vs expenses by month, spending by category with colours, cash flow
  timeline, budget status (reuses `get_budget_status()`), and recent
  transactions. Uses `date <` (exclusive end) for correct timestamp
  boundaries. All money converted from pence to decimal at the service layer.

- `app/routes/dashboard.py`: blueprint at `/api/dashboard` with single
  `GET /finance` endpoint. Accepts optional `months` (1–24, default 6) and
  `limit` (1–50, default 10) query parameters. Returns all dashboard data
  in a single JSON response.

- Registered dashboard blueprint in `app/__init__.py`.

---

## [0.3.1] — 2026-03-21

### Added

#### Phase 3.1 — Budget CRUD API and UI

- `app/migrations/004_budgets.sql`: budgets table with `UNIQUE(category, period)`
  constraint, FK to `categories.name`, amount stored as integer pence

- `app/services/budgets.py`: budget CRUD service with pence boundary conversion,
  validation (positive amount, valid category FK, period enum), toggle active,
  and `get_budget_status()` endpoint computing current-period spending per
  category by joining budgets with transactions

- `app/routes/budgets.py`: REST API blueprint at `/api/budgets` with 7 endpoints
  — list (filterable by active), status (current month/week spending), get,
  create, update, delete, and toggle active/inactive

- `frontend/js/views/budgets.js`: full budget management UI replacing the stub —
  inline add/edit form with category dropdown, amount input (pounds), period
  selector, start date; sortable table with category colour swatches, formatted
  amounts, active toggle, edit and delete actions

---

## [0.2.4] — 2026-03-21

### Added

#### Phase 2.6 — Category Rules Engine (Auto-categorise on Import)

- `app/services/category_rules.py`: new service module with full CRUD for
  category rules, a matching engine (`apply_rules`) that processes transactions
  against active rules in priority order, and `create_learned_rule` for Tier 3
  auto-rule creation when users manually change a transaction's category

- `app/routes/category_rules.py`: REST API blueprint at `/api/category-rules`
  with 6 endpoints — list (filterable by active), get, create, update, delete,
  and toggle active/inactive

- `app/services/csv_parser.py`: after parsing rows, applies category rules via
  `apply_rules()` to override Monzo defaults; adds `rules_applied` count to
  the parse result

- `app/routes/upload.py`: upload response now includes `rules_applied` count
  so the frontend can display how many transactions were auto-categorised

- `app/services/transactions.py`: `update_transaction()` now auto-creates a
  learned rule (Tier 3) when a user changes a transaction's category, so
  future imports of the same merchant are auto-categorised

- `app/services/categories.py`: `delete_category()` now checks for category
  rules referencing the category before allowing deletion (FK protection)

- `frontend/js/views/settings.js`: full category rules management UI added
  below the categories table — inline add/edit form with field, operator,
  value, category dropdown, and priority inputs; rules table with toggle,
  edit, and delete actions; empty state when no rules exist

- `frontend/js/views/upload.js`: import summary stats grid now shows a 4th
  "Auto-categorised" stat in jade green

- `frontend/css/style.css`: upload summary stats grid expanded from 3 to 4
  columns

---

## [0.2.3] — 2026-03-20

### Added

#### Phase 2.5 — Post-import Transaction Review (Highlight New Imports)

- `app/routes/upload.py`: upload response now includes `imported_ids` array —
  after bulk insert, queries the database for the auto-generated IDs of the
  newly inserted transactions using their `monzo_id` values

- `app/services/transactions.py`: `list_transactions()` gains an `ids` parameter
  (list of ints) — when provided, filters with `WHERE id IN (...)` to return
  only the specified transactions; enables the post-import review view

- `app/routes/transactions.py`: `GET /api/transactions` accepts an optional `ids`
  query parameter (comma-separated integers, e.g. `?ids=1,2,3`); validates that
  all values are integers (returns 400 otherwise); passes to service layer

- `frontend/js/views/upload.js`: on successful import, stores `imported_ids` in
  `sessionStorage` under key `import_review` with `reviewMode: true`; "View
  Transactions" button text changes to "Review Imports" when new transactions
  were imported (unchanged when all rows are duplicates)

- `frontend/js/views/transactions.js`: two-mode post-import review system:
  - **Review mode** (entered from upload): transactions list is filtered to show
    only the imported rows via `?ids=...` API filter; sorted by `created_at desc`;
    green banner reads "Reviewing N imported transactions" with "Show All
    Transactions" and "Dismiss" buttons
  - **Highlight mode** (after clicking "Show All"): all transactions shown with
    normal filters; imported rows get a green left-border and "NEW" badge next to
    the date; banner changes to "N recently imported transactions highlighted"
    with a "Dismiss" button
  - **Dismiss**: clears `sessionStorage`, removes banner, returns to normal view
  - State persists across page navigations until explicitly dismissed
  - Module-level `importIds` (Set) and `importReviewMode` (boolean) track state;
    `sessionStorage` provides persistence across view transitions

- `frontend/css/style.css`: new component styles:
  - `.import-review-banner` — flex row with green-tinted background, border, and
    text/actions layout; `--highlight` modifier for the lighter highlight-mode variant
  - `.tx-row--imported` — 3px solid green left border on first `<td>`
  - `.badge-new` — small uppercase "NEW" pill badge in success green, 10px font,
    positioned after the date cell

---

## [0.2.2] — 2026-03-17

### Added

#### Phase 2.4 — Upload UI with Drag-and-Drop, Progress Indicator, Import Summary

- `frontend/js/views/upload.js`: full upload view replacing stub:
  - **Drag-and-drop zone**: dashed-border drop area with visual feedback on dragover
    (green border + tinted background); also clickable to open native file picker
  - **Client-side validation**: checks `.csv` extension and file size ≤ 10 MB before
    uploading; displays inline error messages for invalid files
  - **Upload state machine**: `idle` → `uploading` (spinner) → `success` / `error`
    with clean transitions between states
  - **Import summary**: 3-stat grid showing imported (green), skipped (amber), and
    total (blue) counts; row-level errors listed below if any
  - **Actions**: "View Transactions" navigates to `#/transactions`; "Upload Another"
    resets the view to idle state; "Try Again" on error resets to idle
  - **Drag counter technique**: prevents `dragleave` flicker when cursor moves over
    child elements inside the drop zone
  - Uses `escHtml()` for all user-derived content in error messages

- `frontend/js/api.js`: added `upload(path, file)` method:
  - Uses `FormData` and native `fetch()` without `Content-Type` header (browser
    auto-sets the multipart boundary)
  - Error handling mirrors the existing `request()` pattern: extracts `error`/`message`
    from JSON response body on non-2xx status codes

- `frontend/css/style.css`: new upload component styles:
  - `.drop-zone` with `--dragover` and `--has-file` modifier states
  - `.file-info` bar showing filename and formatted size
  - `.upload-spinner` with CSS `@keyframes spin` rotation animation
  - `.upload-summary__header`, `__stats`, `__errors` for the import results display
  - `.upload-stat` cards with large monospace values and uppercase labels

---

## [0.2.1] — 2026-03-16

### Added

#### Phase 2.2 — Upload API Endpoint with File Validation

- `app/routes/upload.py`: Blueprint at `/api/upload` with one endpoint:
  - `POST /api/upload/monzo` — accepts multipart CSV upload (<=10 MB, .csv only);
    validates headers via `validate_csv()`, parses and deduplicates via
    `parse_monzo_csv()`, bulk-inserts new transactions in a single DB transaction
    via `executemany()`; returns `{imported, skipped, errors, total}`
  - Blueprint-level 413 error handler returns JSON instead of HTML
  - UTF-8 and UTF-8-BOM decoding support
- `app/__init__.py`: registered upload blueprint; added `MAX_CONTENT_LENGTH = 10 MB`
  for Flask-level upload size enforcement

#### Phase 2.3 — Deduplication via `monzo_id`

- Deduplication was already implemented in Phase 2.1's `parse_monzo_csv()` (two-pass
  batch dedup). Phase 2.2's upload endpoint exercises it end-to-end: re-uploading
  the same CSV returns `imported: 0, skipped: N`.

---

## [0.2.0] — 2026-03-16

### Added

#### Phase 2.1 — CSV Parser Service & Import Infrastructure

- `app/migrations/003_category_rules_import_profiles.sql`: migration creating two
  new tables for Phase 2:
  - `category_rules` — keyword-based auto-categorisation rules with field, operator,
    value, priority, source (manual/learned), and FK to `categories(name)`
  - `import_profiles` — saved CSV import profiles with column mapping (JSON),
    delimiter, date format, dedup field, and header flag
  - Index: `idx_category_rules_active` on `(is_active, priority DESC)`

- `app/services/csv_parser.py`: Monzo CSV parsing and validation service:
  - `validate_csv(file_stream)` — validates file is CSV, checks for all 16 expected
    Monzo headers, counts data rows; extra headers tolerated (Monzo may add columns);
    returns `{valid, headers, missing_headers, extra_headers, row_count, error}`
  - `parse_monzo_csv(file_stream, db)` — full parse with two-pass approach: first pass
    collects all `monzo_id` values for a single batch dedup query, second pass parses
    each row into a transaction dict with amounts as integer pence; per-row errors
    collected (don't abort the whole parse); returns `{rows, duplicates, errors, total,
    new_count, duplicate_count, error_count}`
  - Private helpers: `_to_pence()` (Decimal conversion), `_normalize_header()` (BOM
    stripping), `_parse_monzo_date()` (ISO 8601 validation), `_get_monzo_profile()`,
    `_get_valid_categories()`, `_get_existing_monzo_ids()` (batched at 500),
    `_parse_monzo_row()` (maps CSV columns → transaction fields, falls back to
    'general' for unknown categories, appends category split to notes)

- `app/db.py`: Monzo import profile seeding:
  - `_MONZO_COLUMN_MAPPING` dict mapping all 16 Monzo CSV headers to transaction
    table fields (Time, Receipt, Category split mapped to `None`)
  - `seed_import_profiles(app)` — inserts the default Monzo profile using
    `INSERT OR IGNORE` (idempotent); called from `init_db()` after `seed_categories()`

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

[Unreleased]: https://github.com/jimi-coding/jade-personal-finance-app/compare/v0.2.3...HEAD
[0.2.3]: https://github.com/jimi-coding/jade-personal-finance-app/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/jimi-coding/jade-personal-finance-app/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/jimi-coding/jade-personal-finance-app/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/jimi-coding/jade-personal-finance-app/compare/v0.1.6...v0.2.0
[0.1.6]: https://github.com/jimi-coding/jade-personal-finance-app/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/jimi-coding/jade-personal-finance-app/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/jimi-coding/jade-personal-finance-app/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/jimi-coding/jade-personal-finance-app/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/jimi-coding/jade-personal-finance-app/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/jimi-coding/jade-personal-finance-app/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/jimi-coding/jade-personal-finance-app/releases/tag/v0.1.0
