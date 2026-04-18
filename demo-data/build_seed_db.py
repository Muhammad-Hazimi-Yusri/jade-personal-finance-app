"""Build ``demo-data/seed.db`` from ``demo-data/seed.sql``.

Creates a fresh SQLite database, applies every migration, seeds the
default categories and Monzo import profile, then loads the deterministic
demo dataset from ``seed.sql``.  The resulting ``seed.db`` is the reset
source used by the demo sidecar container to restore the public demo
instance to a known state every 24 hours.

Run from the project root::

    python demo-data/build_seed_db.py

Existing ``seed.db`` (and any stray WAL/SHM sidecars) are removed first so
the output is always a clean, deterministic snapshot.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from flask import Flask  # noqa: E402

from app.db import init_db  # noqa: E402

SEED_DB_PATH = ROOT / "demo-data" / "seed.db"
SEED_SQL_PATH = ROOT / "demo-data" / "seed.sql"


def _remove_stale_db_files() -> None:
    """Delete any previous seed.db and its WAL/SHM sidecars."""
    for suffix in ("", "-wal", "-shm"):
        path = Path(str(SEED_DB_PATH) + suffix)
        if path.exists():
            path.unlink()


def _init_schema() -> None:
    """Run migrations and seed default reference data into seed.db."""
    app = Flask(__name__)
    app.config["DATABASE_PATH"] = str(SEED_DB_PATH)
    with app.app_context():
        init_db(app)


def _load_seed_sql() -> None:
    """Execute seed.sql against seed.db to populate the demo dataset."""
    seed_sql = SEED_SQL_PATH.read_text(encoding="utf-8")
    conn = sqlite3.connect(SEED_DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(seed_sql)
        conn.commit()
    finally:
        conn.close()


def _checkpoint_and_compact() -> None:
    """Merge the WAL back into the main file so seed.db is a single file.

    The reset sidecar copies only ``seed.db`` — any pending WAL pages would
    be lost.  Switching back to ``DELETE`` journal mode forces a full
    checkpoint and removes the WAL/SHM files.
    """
    conn = sqlite3.connect(SEED_DB_PATH)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("PRAGMA journal_mode = DELETE")
        conn.commit()
    finally:
        conn.close()


def _summarise() -> None:
    """Print a short summary of what ended up in seed.db."""
    conn = sqlite3.connect(SEED_DB_PATH)
    try:
        tables = (
            "transactions",
            "budgets",
            "trading_accounts",
            "strategies",
            "tags",
            "trades",
            "account_snapshots",
            "daily_journal",
        )
        rows = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    finally:
        conn.close()

    size_bytes = SEED_DB_PATH.stat().st_size
    rel_path = SEED_DB_PATH.relative_to(ROOT)
    print(f"Built {rel_path} ({size_bytes:,} bytes)")
    for table, count in rows.items():
        print(f"  {table:20} {count:>6}")


def main() -> None:
    """Build seed.db from seed.sql and report the result."""
    if not SEED_SQL_PATH.exists():
        print(
            f"error: {SEED_SQL_PATH.relative_to(ROOT)} not found — "
            f"run `python demo-data/generate_seed.py` first",
            file=sys.stderr,
        )
        sys.exit(1)

    _remove_stale_db_files()
    _init_schema()
    _load_seed_sql()
    _checkpoint_and_compact()
    _summarise()


if __name__ == "__main__":
    main()
