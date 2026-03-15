# CLAUDE.md

## Project: Jade — Personal Finance & Trading Journal

You are building **Jade**, a self-hosted personal finance and trading journal web app.

## First Steps (EVERY session)

1. **Read `README.md` completely** — it is the single source of truth for this entire project
2. Check the **Development Roadmap** section to find the current phase and the next unchecked task
3. Work on that task and only that task
4. When finished, update the README (see below)

## README Maintenance (MANDATORY)

After completing ANY task, you MUST update `README.md`:

1. In **Project Structure**: change `🔲` to `✅` for every file you created
2. In **Development Roadmap**: change `[ ]` to `[x]` for the completed task
3. Update the **"Current Phase"** line if you've moved to a new phase
4. If you deviated from the planned schema, API, or structure — update those sections to match what you actually built
5. **Never leave the README out of sync with reality**

## Architecture Rules

- **Backend:** Flask (Python). App factory pattern in `app/__init__.py`
- **Database:** SQLite with WAL mode. Connection managed in `app/db.py`. Set PRAGMAs on every connection
- **Frontend:** Vanilla JS with ES6 modules. Hash-based SPA routing. No build tools, no bundler, no npm
- **CSS:** Custom design system (dark mode). No CSS frameworks. Colours and fonts defined in README branding section
- **Charts:** Chart.js for finance charts, TradingView Lightweight Charts for trading/equity curves. Both from CDN
- **Auth:** Handled by Cloudflare Access (Zero Trust) — zero auth code in Flask
- **Tunnel:** Cloudflare Tunnel (`cloudflared`) — no Caddy, no Nginx, no reverse proxy in the app
- **No extra dependencies** unless absolutely necessary. If you think you need one, justify it

## Code Quality

- Python: PEP 8, type hints, docstrings
- JavaScript: ES6 modules, const/let only, template literals for HTML generation
- SQL: Uppercase keywords, parameterised queries ALWAYS (never f-strings or .format())
- All monetary values stored as integer pence in SQLite, converted to/from decimal at the API boundary
- All dates as ISO 8601 strings

## Workflow

- Work in small, testable increments — one roadmap task at a time
- Create the file structure as you go, matching the planned structure in README
- Test API endpoints with curl or the Flask test client before moving on
- If something in the README doesn't make sense or needs changing, update it with the correction — don't silently deviate

## Do NOT

- Skip phases or jump ahead in the roadmap
- Add features not in the README without asking
- Install npm, webpack, vite, or any JS build tools
- Use any CSS framework (no Tailwind, Bootstrap, Pico)
- Add multi-user auth to the Flask app (Cloudflare Access handles this)
- Add Caddy, Nginx, or any reverse proxy — cloudflared handles tunnelling
- Use REAL/float for currency storage — always integer pence in SQLite, decimal in API
- Leave the README out of date after making changes