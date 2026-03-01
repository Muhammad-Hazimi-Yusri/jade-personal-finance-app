"""SQLite connection manager for Jade.

Provides a request-scoped database connection with WAL mode and the
required PRAGMAs set on every connection. Also contains the migration
runner that applies numbered SQL files from app/migrations/.
"""

import sqlite3
from pathlib import Path

from flask import Flask, g


def get_db() -> sqlite3.Connection:
    """Return the request-scoped SQLite connection, creating it if needed.

    PRAGMAs are applied on every new connection:
        - journal_mode = WAL      (concurrent readers, single writer)
        - foreign_keys = ON       (enforce FK constraints)
        - busy_timeout = 5000     (wait up to 5s before raising SQLITE_BUSY)
        - synchronous = NORMAL    (safe with WAL, faster than FULL)

    Returns:
        An open sqlite3.Connection with row_factory set to sqlite3.Row.
    """
    if "db" not in g:
        from flask import current_app

        db_path = current_app.config["DATABASE_PATH"]
        g.db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row

        g.db.execute("PRAGMA journal_mode = WAL")
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA busy_timeout = 5000")
        g.db.execute("PRAGMA synchronous = NORMAL")

    return g.db


def close_db(e: BaseException | None = None) -> None:
    """Close the request-scoped database connection.

    Registered as a teardown_appcontext callback in the app factory.

    Args:
        e: Exception that triggered teardown, if any (unused).
    """
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app: Flask) -> None:
    """Ensure the database directory exists and run pending migrations.

    Args:
        app: The Flask application instance (used to read DATABASE_PATH).
    """
    db_path = Path(app.config["DATABASE_PATH"])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    run_migrations(app)


def run_migrations(app: Flask) -> None:
    """Apply any pending numbered SQL migration files.

    Migration files live in app/migrations/ and are named like:
        001_initial.sql
        002_add_budgets.sql

    The schema_version table tracks which migrations have been applied.
    Migrations are forward-only — never rolled back.

    Args:
        app: The Flask application instance (used to read DATABASE_PATH).
    """
    db_path = app.config["DATABASE_PATH"]
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version     INTEGER PRIMARY KEY,
                applied_at  TEXT NOT NULL DEFAULT (datetime('now')),
                description TEXT
            )
        """)
        conn.commit()

        current_version: int = conn.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_version"
        ).fetchone()[0]

        migration_dir = Path(__file__).parent / "migrations"
        migration_files = sorted(migration_dir.glob("*.sql"))

        for migration_file in migration_files:
            version = int(migration_file.stem.split("_")[0])
            if version > current_version:
                print(f"Applying migration {migration_file.name}...")
                conn.executescript(migration_file.read_text(encoding="utf-8"))
                conn.execute(
                    "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                    (version, migration_file.stem),
                )
                conn.commit()
    finally:
        conn.close()
