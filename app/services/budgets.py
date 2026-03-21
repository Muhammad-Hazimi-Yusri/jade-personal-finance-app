"""Budget service layer for Jade.

All SQL queries and business logic for budgets live here.
Route handlers call these functions and never access the database directly.

Money convention: the database stores the budget amount as integer pence.
This module converts inbound decimals to pence (x 100) and outbound pence
back to decimals (/ 100) so the rest of the app only sees decimals.
"""

import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SELECT_COLS = """
    id, category, amount, period, start_date, is_active, created_at
"""

_VALID_PERIODS: frozenset[str] = frozenset({"monthly", "weekly"})

_UPDATABLE_FIELDS: frozenset[str] = frozenset({
    "category", "amount", "period", "start_date", "is_active",
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
    d["amount"] = _from_pence(d["amount"])
    return d


def _validate_category(db: sqlite3.Connection, category: object) -> str:
    """Validate that a category name exists in the categories table.

    Raises:
        ValueError: If category is missing or does not exist.
    """
    if not category:
        raise ValueError("category is required")
    category = str(category).strip()
    if not category:
        raise ValueError("category is required")
    row = db.execute(
        "SELECT 1 FROM categories WHERE name = ?", (category,)
    ).fetchone()
    if row is None:
        raise ValueError(f"category '{category}' does not exist")
    return category


def _validate_amount(value: object) -> int:
    """Validate and convert a budget amount to pence.

    Budget limits must be positive (greater than zero).

    Raises:
        ValueError: If value is missing, non-numeric, or not positive.
    """
    if value is None:
        raise ValueError("amount is required")
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise ValueError("amount must be a number")
    if amount <= 0:
        raise ValueError("amount must be greater than zero")
    return _to_pence(amount)


def _validate_period(value: object) -> str:
    """Validate period, defaulting to 'monthly'.

    Raises:
        ValueError: If period is not 'monthly' or 'weekly'.
    """
    if value is None:
        return "monthly"
    value = str(value).strip().lower()
    if value not in _VALID_PERIODS:
        raise ValueError(f"period must be one of: {', '.join(sorted(_VALID_PERIODS))}")
    return value


def _validate_start_date(value: object) -> str | None:
    """Validate an optional ISO 8601 date string.

    Raises:
        ValueError: If value is provided but not a valid date.
    """
    if value is None or str(value).strip() == "":
        return None
    value = str(value).strip()
    try:
        datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("start_date must be a valid ISO 8601 date (e.g. 2025-01-01)")
    return value


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def list_budgets(
    db: sqlite3.Connection,
    *,
    active_only: bool = False,
) -> list[dict]:
    """Return all budgets, optionally filtered to active only.

    Returns:
        List of budget dicts with amount in decimal pounds.
    """
    sql = f"SELECT {_SELECT_COLS} FROM budgets"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY category, period"
    rows = db.execute(sql).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_budget(db: sqlite3.Connection, budget_id: int) -> dict | None:
    """Return a single budget by ID, or None if not found."""
    row = db.execute(
        f"SELECT {_SELECT_COLS} FROM budgets WHERE id = ?",
        (budget_id,),
    ).fetchone()
    return _row_to_dict(row) if row else None


def create_budget(db: sqlite3.Connection, data: dict) -> dict:
    """Create a new budget.

    Required fields: category, amount.
    Optional: period (default 'monthly'), start_date.

    Returns:
        The newly created budget dict.

    Raises:
        ValueError: On validation failure or duplicate category+period.
    """
    category = _validate_category(db, data.get("category"))
    amount = _validate_amount(data.get("amount"))
    period = _validate_period(data.get("period"))
    start_date = _validate_start_date(data.get("start_date"))

    try:
        cursor = db.execute(
            """
            INSERT INTO budgets (category, amount, period, start_date)
            VALUES (?, ?, ?, ?)
            """,
            (category, amount, period, start_date),
        )
        db.commit()
    except sqlite3.IntegrityError:
        raise ValueError(
            f"A budget for '{category}' with period '{period}' already exists"
        )

    return get_budget(db, cursor.lastrowid)


def update_budget(
    db: sqlite3.Connection,
    budget_id: int,
    data: dict,
) -> dict | None:
    """Update an existing budget (partial update).

    Returns:
        The updated budget dict, or None if the ID does not exist.

    Raises:
        ValueError: On validation failure or duplicate category+period.
    """
    existing = get_budget(db, budget_id)
    if existing is None:
        return None

    updates: dict[str, object] = {}

    if "category" in data:
        updates["category"] = _validate_category(db, data["category"])
    if "amount" in data:
        updates["amount"] = _validate_amount(data["amount"])
    if "period" in data:
        updates["period"] = _validate_period(data["period"])
    if "start_date" in data:
        updates["start_date"] = _validate_start_date(data["start_date"])
    if "is_active" in data:
        updates["is_active"] = 1 if data["is_active"] else 0

    if not updates:
        return existing

    set_fragments = [f"{field} = ?" for field in updates]
    set_clause = ", ".join(set_fragments)

    try:
        db.execute(
            f"UPDATE budgets SET {set_clause} WHERE id = ?",
            [*updates.values(), budget_id],
        )
        db.commit()
    except sqlite3.IntegrityError:
        raise ValueError(
            "A budget for this category and period combination already exists"
        )

    return get_budget(db, budget_id)


def delete_budget(db: sqlite3.Connection, budget_id: int) -> bool:
    """Delete a budget.

    Returns:
        True if the budget was deleted, False if not found.
    """
    existing = get_budget(db, budget_id)
    if existing is None:
        return False

    db.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))
    db.commit()
    return True


def toggle_budget(db: sqlite3.Connection, budget_id: int) -> dict | None:
    """Toggle a budget's is_active flag.

    Returns:
        The updated budget dict, or None if not found.
    """
    existing = get_budget(db, budget_id)
    if existing is None:
        return None

    new_active = 0 if existing["is_active"] else 1
    db.execute(
        "UPDATE budgets SET is_active = ? WHERE id = ?",
        (new_active, budget_id),
    )
    db.commit()
    return get_budget(db, budget_id)


def get_budget_status(
    db: sqlite3.Connection,
    *,
    period: str = "monthly",
) -> list[dict]:
    """Compute current-period budget status with actual spending.

    Joins active budgets with transactions to calculate how much has been
    spent against each budget in the current month or week.

    Spending is the absolute sum of negative transaction amounts (debits)
    for each budget's category within the current period.

    Returns:
        List of dicts with: id, category, budget_amount, spent,
        remaining, percentage, period, start_date, is_active, created_at.
    """
    period = _validate_period(period)
    today = date.today()

    # Determine current period boundaries
    if period == "monthly":
        start_of_period = today.replace(day=1).isoformat()
        # End of month: go to next month's first day, subtract one day
        if today.month == 12:
            end_of_period = today.replace(year=today.year + 1, month=1, day=1)
        else:
            end_of_period = today.replace(month=today.month + 1, day=1)
        end_of_period = (end_of_period - timedelta(days=1)).isoformat()
    else:  # weekly
        # Monday = 0 in weekday()
        start_of_period = (today - timedelta(days=today.weekday())).isoformat()
        end_of_period = (
            today + timedelta(days=6 - today.weekday())
        ).isoformat()

    rows = db.execute(
        f"""
        SELECT
            b.id,
            b.category,
            b.amount AS budget_amount,
            b.period,
            b.start_date,
            b.is_active,
            b.created_at,
            COALESCE(
                SUM(CASE WHEN t.amount < 0 THEN ABS(t.amount) ELSE 0 END),
                0
            ) AS spent
        FROM budgets b
        LEFT JOIN transactions t
            ON t.category = b.category
            AND t.date >= ?
            AND t.date <= ?
        WHERE b.is_active = 1
          AND b.period = ?
        GROUP BY b.id
        ORDER BY b.category
        """,
        (start_of_period, end_of_period, period),
    ).fetchall()

    result = []
    for row in rows:
        d = dict(row)
        budget_amount = _from_pence(d["budget_amount"])
        spent = _from_pence(d["spent"])
        remaining = round(budget_amount - spent, 2)
        percentage = round((spent / budget_amount) * 100, 1) if budget_amount > 0 else 0.0

        result.append({
            "id": d["id"],
            "category": d["category"],
            "budget_amount": budget_amount,
            "spent": spent,
            "remaining": remaining,
            "percentage": percentage,
            "period": d["period"],
            "start_date": d["start_date"],
            "is_active": d["is_active"],
            "created_at": d["created_at"],
        })

    return result
