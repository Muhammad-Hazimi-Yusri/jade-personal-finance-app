"""Transaction service layer for Jade.

All SQL queries and business logic for transactions live here.
Route handlers call these functions and never access the database directly.
"""

import math
import sqlite3
from datetime import datetime

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SORTABLE_FIELDS: frozenset[str] = frozenset({
    "date", "amount", "name", "category", "created_at", "updated_at"
})

_UPDATABLE_FIELDS: frozenset[str] = frozenset({
    "monzo_id", "date", "type", "name", "emoji", "category", "amount",
    "currency", "local_amount", "local_currency", "notes", "address",
    "description", "custom_category",
})

_SELECT_COLS = """
    id, monzo_id, date, type, name, emoji, category, amount, currency,
    local_amount, local_currency, notes, address, description,
    is_income, custom_category, created_at, updated_at
"""

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row)


def _validate_iso_date(value: str) -> None:
    """Raise ValueError if value is not a parseable ISO 8601 date string.

    Args:
        value: The string to validate.

    Raises:
        ValueError: If value cannot be parsed as an ISO 8601 date/datetime.
    """
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise ValueError(f"date must be a valid ISO 8601 string, got: {value!r}")


def _validate_amount(value: object) -> float:
    """Parse and validate amount. Raises ValueError if not a non-zero number.

    Args:
        value: The raw value from the request body.

    Returns:
        The amount as a float.

    Raises:
        ValueError: If value is not numeric or is zero.
    """
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise ValueError("amount must be a number")
    if amount == 0.0:
        raise ValueError("amount must be non-zero")
    return amount


def _validate_category(db: sqlite3.Connection, category: str) -> None:
    """Raise ValueError if the category name does not exist in the categories table.

    Args:
        db: Open database connection.
        category: snake_case category name to validate.

    Raises:
        ValueError: If the category is not found.
    """
    row = db.execute(
        "SELECT 1 FROM categories WHERE name = ?", (category,)
    ).fetchone()
    if row is None:
        raise ValueError(f"category '{category}' does not exist")


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def list_transactions(
    db: sqlite3.Connection,
    *,
    page: int = 1,
    per_page: int = 50,
    category: str | None = None,
    type_: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    search: str | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    sort: str = "date",
    order: str = "desc",
) -> dict:
    """Return a paginated, filtered list of transactions.

    Args:
        db: Open database connection.
        page: Page number (1-indexed).
        per_page: Rows per page, clamped to 200.
        category: Filter by category snake_case name.
        type_: Filter by transaction type string.
        start_date: Lower bound on date (inclusive, ISO 8601).
        end_date: Upper bound on date (inclusive, ISO 8601).
        search: Free-text search across name, notes, description.
        min_amount: Minimum amount filter (inclusive).
        max_amount: Maximum amount filter (inclusive).
        sort: Column to sort by; must be in _SORTABLE_FIELDS.
        order: 'asc' or 'desc'.

    Returns:
        Dict with 'transactions' list and 'pagination' metadata.
    """
    per_page = min(per_page, 200)
    if sort not in _SORTABLE_FIELDS:
        sort = "date"
    if order not in ("asc", "desc"):
        order = "desc"

    conditions: list[str] = []
    params: list[object] = []

    if category:
        conditions.append("category = ?")
        params.append(category)
    if type_:
        conditions.append("type = ?")
        params.append(type_)
    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)
    if search:
        conditions.append("(name LIKE ? OR notes LIKE ? OR description LIKE ?)")
        pattern = f"%{search}%"
        params.extend([pattern, pattern, pattern])
    if min_amount is not None:
        conditions.append("amount >= ?")
        params.append(min_amount)
    if max_amount is not None:
        conditions.append("amount <= ?")
        params.append(max_amount)

    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    total: int = db.execute(
        f"SELECT COUNT(*) FROM transactions {where_sql}", params
    ).fetchone()[0]

    # sort and order are whitelisted above — safe to interpolate into ORDER BY
    rows = db.execute(
        f"""
        SELECT {_SELECT_COLS}
        FROM transactions
        {where_sql}
        ORDER BY {sort} {order}
        LIMIT ? OFFSET ?
        """,
        [*params, per_page, (page - 1) * per_page],
    ).fetchall()

    total_pages = math.ceil(total / per_page) if total else 0

    return {
        "transactions": [_row_to_dict(r) for r in rows],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page * per_page < total,
            "has_prev": page > 1,
        },
    }


def get_transaction(db: sqlite3.Connection, transaction_id: int) -> dict | None:
    """Return a single transaction by ID, or None if not found.

    Args:
        db: Open database connection.
        transaction_id: Primary key of the transaction.

    Returns:
        Transaction dict, or None if the ID does not exist.
    """
    row = db.execute(
        f"SELECT {_SELECT_COLS} FROM transactions WHERE id = ?",
        (transaction_id,),
    ).fetchone()
    return _row_to_dict(row) if row else None


def create_transaction(db: sqlite3.Connection, data: dict) -> dict:
    """Insert a new transaction and return the created row.

    Required fields in data: date, name, amount, category.
    is_income is derived from the sign of amount and must not be supplied.

    Args:
        db: Open database connection.
        data: Dict of transaction fields from the request body.

    Returns:
        The newly created transaction as a dict.

    Raises:
        ValueError: If any required field is missing or fails validation.
    """
    # Required field presence check
    required = ("date", "name", "amount", "category")
    missing = [f for f in required if data.get(f) is None]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    # Validate and coerce
    _validate_iso_date(data["date"])
    amount = _validate_amount(data["amount"])
    name = str(data["name"]).strip()
    if not name:
        raise ValueError("name must be a non-empty string")
    _validate_category(db, data["category"])

    is_income = 1 if amount > 0 else 0

    cursor = db.execute(
        """
        INSERT INTO transactions (
            monzo_id, date, type, name, emoji, category, amount, currency,
            local_amount, local_currency, notes, address, description,
            is_income, custom_category
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.get("monzo_id"),
            data["date"],
            data.get("type"),
            name,
            data.get("emoji"),
            data["category"],
            amount,
            data.get("currency", "GBP"),
            data.get("local_amount"),
            data.get("local_currency"),
            data.get("notes"),
            data.get("address"),
            data.get("description"),
            is_income,
            data.get("custom_category"),
        ),
    )
    db.commit()
    return get_transaction(db, cursor.lastrowid)


def update_transaction(
    db: sqlite3.Connection,
    transaction_id: int,
    data: dict,
) -> dict | None:
    """Partially update an existing transaction.

    Only fields present in data and in _UPDATABLE_FIELDS are changed.
    updated_at is always set to the current UTC time via SQL.
    is_income is re-derived if amount changes.

    Args:
        db: Open database connection.
        transaction_id: Primary key of the transaction to update.
        data: Dict of fields to update.

    Returns:
        The updated transaction dict, or None if the ID does not exist.

    Raises:
        ValueError: If any supplied field fails validation.
    """
    if get_transaction(db, transaction_id) is None:
        return None

    # Collect only allowed fields from the request body
    updates: dict[str, object] = {
        field: data[field]
        for field in _UPDATABLE_FIELDS
        if field in data
    }

    if not updates:
        # Nothing to change — return the row unchanged
        return get_transaction(db, transaction_id)

    # Field-level validation
    if "date" in updates:
        _validate_iso_date(str(updates["date"]))
    if "amount" in updates:
        updates["amount"] = _validate_amount(updates["amount"])
        updates["is_income"] = 1 if updates["amount"] > 0 else 0
    if "name" in updates:
        name = str(updates["name"]).strip()
        if not name:
            raise ValueError("name must be a non-empty string")
        updates["name"] = name
    if "category" in updates:
        _validate_category(db, str(updates["category"]))

    # Build SET clause; updated_at is set via SQL literal (no user param)
    fields = list(updates.keys())
    set_fragments = [f"{field} = ?" for field in fields]
    set_fragments.append("updated_at = datetime('now')")
    set_clause = ", ".join(set_fragments)

    db.execute(
        f"UPDATE transactions SET {set_clause} WHERE id = ?",
        [*[updates[f] for f in fields], transaction_id],
    )
    db.commit()

    return get_transaction(db, transaction_id)


def delete_transaction(db: sqlite3.Connection, transaction_id: int) -> bool:
    """Delete a transaction by ID.

    Args:
        db: Open database connection.
        transaction_id: Primary key of the transaction to delete.

    Returns:
        True if a row was deleted, False if the ID did not exist.
    """
    cursor = db.execute(
        "DELETE FROM transactions WHERE id = ?", (transaction_id,)
    )
    db.commit()
    return cursor.rowcount > 0
