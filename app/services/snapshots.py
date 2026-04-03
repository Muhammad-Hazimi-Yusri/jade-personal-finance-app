"""Account snapshot service layer for Jade.

All SQL queries and business logic for account balance snapshots live here.
Route handlers call these functions and never access the database directly.

Money convention: balance and equity are stored as integer pence in the
database. This module converts inbound decimals to pence (x 100) and
outbound pence back to decimals (/ 100) so the rest of the app only sees
decimals.
"""

import re
import sqlite3
from decimal import Decimal, ROUND_HALF_UP

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SELECT_COLS = "id, account_id, date, balance, equity, note"


def _to_pence(value: object) -> int:
    """Convert a decimal monetary value to integer pence.

    Uses Decimal for exact arithmetic to avoid float rounding issues.

    Raises:
        ValueError: If value cannot be converted.
    """
    d = Decimal(str(value))
    return int((d * 100).to_integral_value(rounding=ROUND_HALF_UP))


def _from_pence(pence: int) -> float:
    """Convert integer pence to a decimal float for API responses."""
    return round(pence / 100, 2)


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict, converting pence to decimal."""
    d = dict(row)
    d["balance"] = _from_pence(d["balance"])
    if d["equity"] is not None:
        d["equity"] = _from_pence(d["equity"])
    return d


def _validate_date(date: object) -> str:
    """Validate a YYYY-MM-DD date string.

    Raises:
        ValueError: If the format is wrong.
    """
    if date is None:
        raise ValueError("date is required")
    date = str(date).strip()
    if not _DATE_RE.match(date):
        raise ValueError("date must be in YYYY-MM-DD format")
    return date


def _validate_balance(value: object) -> int:
    """Validate and convert balance to pence.

    Balance is required and must be zero or positive.

    Raises:
        ValueError: If value is missing, non-numeric, or negative.
    """
    if value is None:
        raise ValueError("balance is required")
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise ValueError("balance must be a number")
    if amount < 0:
        raise ValueError("balance must be zero or positive")
    return _to_pence(amount)


def _validate_equity(value: object) -> int | None:
    """Validate and convert equity to pence, or return None if not provided.

    Raises:
        ValueError: If provided value is non-numeric or negative.
    """
    if value is None:
        return None
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise ValueError("equity must be a number")
    if amount < 0:
        raise ValueError("equity must be zero or positive")
    return _to_pence(amount)


def _account_exists(db: sqlite3.Connection, account_id: int) -> bool:
    """Return True if the given trading account ID exists."""
    row = db.execute(
        "SELECT id FROM trading_accounts WHERE id = ?",
        (account_id,),
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def list_snapshots(
    db: sqlite3.Connection,
    *,
    account_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """Return account snapshots ordered by date ascending.

    Args:
        account_id: Optional filter by trading account.
        start_date: Optional lower bound (inclusive) in YYYY-MM-DD format.
        end_date: Optional upper bound (inclusive) in YYYY-MM-DD format.

    Returns:
        List of snapshot dicts with balance/equity as decimals.
    """
    conditions: list[str] = []
    params: list[object] = []

    if account_id is not None:
        conditions.append("account_id = ?")
        params.append(int(account_id))
    if start_date is not None:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date is not None:
        conditions.append("date <= ?")
        params.append(end_date)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT {_SELECT_COLS} FROM account_snapshots {where} ORDER BY date ASC"
    rows = db.execute(sql, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_snapshot(db: sqlite3.Connection, snapshot_id: int) -> dict | None:
    """Return a single snapshot by primary key, or None if not found."""
    row = db.execute(
        f"SELECT {_SELECT_COLS} FROM account_snapshots WHERE id = ?",
        (snapshot_id,),
    ).fetchone()
    return _row_to_dict(row) if row else None


def snapshot_exists(
    db: sqlite3.Connection,
    account_id: int,
    date: str,
) -> bool:
    """Return True if a snapshot already exists for account_id + date."""
    row = db.execute(
        "SELECT id FROM account_snapshots WHERE account_id = ? AND date = ?",
        (account_id, date),
    ).fetchone()
    return row is not None


def upsert_snapshot(db: sqlite3.Connection, data: dict) -> tuple[dict, bool]:
    """Create or update the snapshot for a given account + date.

    Required fields: account_id, date, balance.
    Optional: equity, note.

    Uses INSERT ... ON CONFLICT ... DO UPDATE so a single statement handles
    both the create and update cases.

    Args:
        data: Dict containing snapshot fields.

    Returns:
        Tuple of (snapshot dict, created: bool). ``created`` is True when a
        new row was inserted, False when an existing row was updated.

    Raises:
        ValueError: On validation failure or missing account.
    """
    if data.get("account_id") is None:
        raise ValueError("account_id is required")
    try:
        account_id = int(data["account_id"])
    except (TypeError, ValueError):
        raise ValueError("account_id must be an integer")

    if not _account_exists(db, account_id):
        raise ValueError(f"trading account {account_id} does not exist")

    date = _validate_date(data.get("date"))
    balance = _validate_balance(data.get("balance"))
    equity = _validate_equity(data.get("equity"))
    note = str(data["note"]).strip() if data.get("note") else None

    created = not snapshot_exists(db, account_id, date)

    db.execute(
        """
        INSERT INTO account_snapshots (account_id, date, balance, equity, note)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(account_id, date) DO UPDATE SET
            balance = excluded.balance,
            equity  = excluded.equity,
            note    = excluded.note
        """,
        (account_id, date, balance, equity, note),
    )
    db.commit()

    row = db.execute(
        f"SELECT {_SELECT_COLS} FROM account_snapshots WHERE account_id = ? AND date = ?",
        (account_id, date),
    ).fetchone()
    return _row_to_dict(row), created


def delete_snapshot(db: sqlite3.Connection, snapshot_id: int) -> bool:
    """Delete a snapshot by primary key.

    Returns:
        True if the snapshot was deleted, False if it was not found.
    """
    cursor = db.execute(
        "DELETE FROM account_snapshots WHERE id = ?",
        (snapshot_id,),
    )
    db.commit()
    return cursor.rowcount > 0
