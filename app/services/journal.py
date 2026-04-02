"""Journal service layer for Jade.

All SQL queries and business logic for daily journal entries live here.
Route handlers call these functions and never access the database directly.
"""

import re
import sqlite3


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_JOURNAL_FIELDS: tuple[str, ...] = (
    "market_outlook",
    "plan",
    "review",
    "mood",
    "lessons",
)


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row)


def _validate_date(date: str) -> None:
    """Validate a YYYY-MM-DD date string.

    Raises:
        ValueError: If the format is wrong.
    """
    if not _DATE_RE.match(date):
        raise ValueError("date must be in YYYY-MM-DD format")


def _validate_mood(mood: object) -> int:
    """Validate and coerce mood to an integer between 1 and 5.

    Raises:
        ValueError: If mood is out of range or non-numeric.
    """
    try:
        m = int(mood)
    except (TypeError, ValueError):
        raise ValueError("mood must be an integer")
    if not (1 <= m <= 5):
        raise ValueError("mood must be between 1 and 5")
    return m


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def list_entries(db: sqlite3.Connection, limit: int = 50, offset: int = 0) -> list[dict]:
    """Return journal entries ordered by date descending.

    Args:
        limit: Maximum number of entries to return (default 50, max 200).
        offset: Number of entries to skip for pagination.

    Returns:
        List of journal entry dicts.
    """
    limit = min(200, max(1, int(limit)))
    offset = max(0, int(offset))

    rows = db.execute(
        "SELECT * FROM daily_journal ORDER BY date DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_entry(db: sqlite3.Connection, date: str) -> dict | None:
    """Return the journal entry for a specific date, or None if not found.

    Args:
        date: ISO 8601 date string (YYYY-MM-DD).

    Returns:
        Journal entry dict, or None.
    """
    row = db.execute(
        "SELECT * FROM daily_journal WHERE date = ?",
        (date,),
    ).fetchone()
    return _row_to_dict(row) if row is not None else None


def upsert_entry(db: sqlite3.Connection, date: str, data: dict) -> dict:
    """Create or update the journal entry for the given date.

    Uses INSERT OR REPLACE so the caller does not need to check existence.
    The ``updated_at`` timestamp is always refreshed.

    Args:
        date: ISO 8601 date string (YYYY-MM-DD).
        data: Dict with any combination of: market_outlook, plan, review,
              mood, lessons.

    Returns:
        The created or updated journal entry dict.

    Raises:
        ValueError: On validation failure.
    """
    _validate_date(date)

    mood = None
    if data.get("mood") is not None:
        mood = _validate_mood(data["mood"])

    market_outlook = data.get("market_outlook") or None
    plan = data.get("plan") or None
    review = data.get("review") or None
    lessons = data.get("lessons") or None

    # Fetch existing so we can preserve created_at on update
    existing = get_entry(db, date)

    if existing is None:
        db.execute(
            """
            INSERT INTO daily_journal
                (date, market_outlook, plan, review, mood, lessons)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (date, market_outlook, plan, review, mood, lessons),
        )
    else:
        db.execute(
            """
            UPDATE daily_journal
            SET market_outlook = ?,
                plan = ?,
                review = ?,
                mood = ?,
                lessons = ?,
                updated_at = datetime('now')
            WHERE date = ?
            """,
            (market_outlook, plan, review, mood, lessons, date),
        )

    db.commit()
    return get_entry(db, date)


def delete_entry(db: sqlite3.Connection, date: str) -> bool:
    """Delete the journal entry for the given date.

    Args:
        date: ISO 8601 date string (YYYY-MM-DD).

    Returns:
        True if an entry was deleted, False if no entry existed.
    """
    cursor = db.execute(
        "DELETE FROM daily_journal WHERE date = ?",
        (date,),
    )
    db.commit()
    return cursor.rowcount > 0
