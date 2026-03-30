"""Trading account service layer for Jade.

All SQL queries and business logic for trading accounts live here.
Route handlers call these functions and never access the database directly.

Money convention: initial_balance is stored as integer pence in the database.
This module converts inbound decimals to pence (x 100) and outbound pence
back to decimals (/ 100) so the rest of the app only sees decimals.
"""

import sqlite3
from decimal import Decimal, ROUND_HALF_UP

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SELECT_COLS = """
    id, name, broker, asset_class, currency, initial_balance, is_active, created_at
"""

_VALID_ASSET_CLASSES: frozenset[str] = frozenset({
    "stocks", "forex", "crypto", "options", "multi",
})

_UPDATABLE_FIELDS: frozenset[str] = frozenset({
    "name", "broker", "asset_class", "currency", "initial_balance", "is_active",
})

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


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
    d["initial_balance"] = _from_pence(d["initial_balance"])
    return d


def _validate_name(value: object) -> str:
    """Validate account name — required, non-empty.

    Raises:
        ValueError: If name is missing or blank.
    """
    if value is None:
        raise ValueError("name is required")
    name = str(value).strip()
    if not name:
        raise ValueError("name is required")
    return name


def _validate_asset_class(value: object) -> str:
    """Validate asset class against the allowed set.

    Raises:
        ValueError: If value is missing or not in the allowed set.
    """
    if value is None:
        raise ValueError("asset_class is required")
    value = str(value).strip().lower()
    if value not in _VALID_ASSET_CLASSES:
        raise ValueError(
            f"asset_class must be one of: {', '.join(sorted(_VALID_ASSET_CLASSES))}"
        )
    return value


def _validate_currency(value: object) -> str:
    """Validate currency code, defaulting to 'GBP'.

    Raises:
        ValueError: If provided value is blank or too long.
    """
    if value is None or str(value).strip() == "":
        return "GBP"
    currency = str(value).strip().upper()
    if len(currency) > 10:
        raise ValueError("currency must be 10 characters or fewer")
    return currency


def _validate_initial_balance(value: object) -> int:
    """Validate and convert initial balance to pence.

    Balance must be zero or positive. Defaults to 0 if not provided.

    Raises:
        ValueError: If value is non-numeric or negative.
    """
    if value is None:
        return 0
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise ValueError("initial_balance must be a number")
    if amount < 0:
        raise ValueError("initial_balance must be zero or positive")
    return _to_pence(amount)


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def list_accounts(
    db: sqlite3.Connection,
    *,
    active_only: bool = False,
) -> list[dict]:
    """Return all trading accounts, optionally filtered to active only.

    Returns:
        List of account dicts with initial_balance in decimal pounds.
    """
    sql = f"SELECT {_SELECT_COLS} FROM trading_accounts"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY name"
    rows = db.execute(sql).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_account(db: sqlite3.Connection, account_id: int) -> dict | None:
    """Return a single trading account by ID, or None if not found."""
    row = db.execute(
        f"SELECT {_SELECT_COLS} FROM trading_accounts WHERE id = ?",
        (account_id,),
    ).fetchone()
    return _row_to_dict(row) if row else None


def create_account(db: sqlite3.Connection, data: dict) -> dict:
    """Create a new trading account.

    Required fields: name, asset_class.
    Optional: broker, currency (default 'GBP'), initial_balance (default 0).

    Returns:
        The newly created account dict.

    Raises:
        ValueError: On validation failure.
    """
    name = _validate_name(data.get("name"))
    broker = str(data["broker"]).strip() if data.get("broker") else None
    asset_class = _validate_asset_class(data.get("asset_class"))
    currency = _validate_currency(data.get("currency"))
    initial_balance = _validate_initial_balance(data.get("initial_balance"))

    cursor = db.execute(
        """
        INSERT INTO trading_accounts (name, broker, asset_class, currency, initial_balance)
        VALUES (?, ?, ?, ?, ?)
        """,
        (name, broker, asset_class, currency, initial_balance),
    )
    db.commit()
    return get_account(db, cursor.lastrowid)


def update_account(
    db: sqlite3.Connection,
    account_id: int,
    data: dict,
) -> dict | None:
    """Update an existing trading account (partial update).

    Returns:
        The updated account dict, or None if the ID does not exist.

    Raises:
        ValueError: On validation failure.
    """
    existing = get_account(db, account_id)
    if existing is None:
        return None

    updates: dict[str, object] = {}

    if "name" in data:
        updates["name"] = _validate_name(data["name"])
    if "broker" in data:
        updates["broker"] = str(data["broker"]).strip() if data["broker"] else None
    if "asset_class" in data:
        updates["asset_class"] = _validate_asset_class(data["asset_class"])
    if "currency" in data:
        updates["currency"] = _validate_currency(data["currency"])
    if "initial_balance" in data:
        updates["initial_balance"] = _validate_initial_balance(data["initial_balance"])
    if "is_active" in data:
        updates["is_active"] = 1 if data["is_active"] else 0

    if not updates:
        return existing

    set_fragments = [f"{field} = ?" for field in updates]
    set_clause = ", ".join(set_fragments)

    db.execute(
        f"UPDATE trading_accounts SET {set_clause} WHERE id = ?",
        [*updates.values(), account_id],
    )
    db.commit()
    return get_account(db, account_id)


def delete_account(db: sqlite3.Connection, account_id: int) -> bool:
    """Delete a trading account.

    Returns:
        True if the account was deleted, False if not found.
    """
    existing = get_account(db, account_id)
    if existing is None:
        return False

    db.execute("DELETE FROM trading_accounts WHERE id = ?", (account_id,))
    db.commit()
    return True


def toggle_account(db: sqlite3.Connection, account_id: int) -> dict | None:
    """Toggle a trading account's is_active flag.

    Returns:
        The updated account dict, or None if not found.
    """
    existing = get_account(db, account_id)
    if existing is None:
        return None

    new_active = 0 if existing["is_active"] else 1
    db.execute(
        "UPDATE trading_accounts SET is_active = ? WHERE id = ?",
        (new_active, account_id),
    )
    db.commit()
    return get_account(db, account_id)
