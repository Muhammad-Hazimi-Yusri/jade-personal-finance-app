"""Dashboard service layer for Jade.

All SQL queries and business logic for dashboard aggregations live here.
Route handlers call these functions and never access the database directly.

Money convention: the database stores all monetary values as integer pence.
This module converts outbound pence back to decimals (/ 100) so the rest
of the app only sees decimals.
"""

import sqlite3
from datetime import date, timedelta


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _from_pence(pence: int) -> float:
    """Convert integer pence to a decimal float for API responses."""
    return round(pence / 100, 2)


def _month_boundaries(
    ref_date: date, months_back: int
) -> list[tuple[str, str, str]]:
    """Return (label, start_iso, exclusive_end_iso) for the last N months.

    The exclusive end is the first day of the *next* month, so callers can
    use ``date >= start AND date < exclusive_end`` which correctly includes
    all timestamps on the last day of the month.

    Results are ordered oldest-first (suitable for left-to-right charts).
    """
    result: list[tuple[str, str, str]] = []
    for i in range(months_back - 1, -1, -1):
        year = ref_date.year
        month = ref_date.month - i
        while month <= 0:
            month += 12
            year -= 1

        start = date(year, month, 1)

        # Exclusive end: first day of the following month
        if month == 12:
            exclusive_end = date(year + 1, 1, 1)
        else:
            exclusive_end = date(year, month + 1, 1)

        label = start.strftime("%b %Y")  # e.g. "Mar 2026"
        result.append((label, start.isoformat(), exclusive_end.isoformat()))

    return result


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def get_summary(
    db: sqlite3.Connection,
    *,
    today: date | None = None,
) -> dict:
    """Compute top-level KPIs: balance, monthly income/expenses/net/savings.

    Args:
        db: Active database connection.
        today: Reference date (defaults to today; accepts override for tests).

    Returns:
        Dict with balance, month_income, month_expenses, month_net,
        and savings_rate (percentage, 0.0 when no income).
    """
    today = today or date.today()
    boundaries = _month_boundaries(today, 1)
    _, month_start, month_end = boundaries[0]

    row = db.execute(
        """
        SELECT
            COALESCE(SUM(amount), 0) AS balance,
            COALESCE(SUM(CASE WHEN date >= ? AND date < ?
                              AND amount > 0
                         THEN amount ELSE 0 END), 0) AS month_income,
            COALESCE(SUM(CASE WHEN date >= ? AND date < ?
                              AND amount < 0
                         THEN amount ELSE 0 END), 0) AS month_expenses
        FROM transactions
        """,
        (month_start, month_end, month_start, month_end),
    ).fetchone()

    balance = row["balance"]
    month_income = row["month_income"]
    month_expenses = row["month_expenses"]
    month_net = month_income + month_expenses  # expenses already negative

    savings_rate = (
        round(month_net / month_income * 100, 1) if month_income > 0 else 0.0
    )

    return {
        "balance": _from_pence(balance),
        "month_income": _from_pence(month_income),
        "month_expenses": _from_pence(abs(month_expenses)),
        "month_net": _from_pence(month_net),
        "savings_rate": savings_rate,
    }


def get_income_vs_expenses(
    db: sqlite3.Connection,
    *,
    months: int = 6,
    today: date | None = None,
) -> list[dict]:
    """Per-month income and expense totals for a bar chart.

    Args:
        db: Active database connection.
        months: How many months of history (default 6).
        today: Reference date override for tests.

    Returns:
        List of dicts ``{month, income, expenses}`` ordered oldest-first.
        Empty months are filled with zeroes.
    """
    today = today or date.today()
    boundaries = _month_boundaries(today, months)
    range_start = boundaries[0][1]
    range_end = boundaries[-1][2]

    rows = db.execute(
        """
        SELECT
            strftime('%Y-%m', date) AS month_key,
            COALESCE(SUM(CASE WHEN amount > 0 THEN amount
                         ELSE 0 END), 0) AS income,
            COALESCE(SUM(CASE WHEN amount < 0 THEN ABS(amount)
                         ELSE 0 END), 0) AS expenses
        FROM transactions
        WHERE date >= ? AND date < ?
        GROUP BY month_key
        ORDER BY month_key
        """,
        (range_start, range_end),
    ).fetchall()

    by_key: dict[str, dict] = {
        r["month_key"]: {"income": r["income"], "expenses": r["expenses"]}
        for r in rows
    }

    result: list[dict] = []
    for label, start_iso, _ in boundaries:
        key = start_iso[:7]  # "YYYY-MM"
        data = by_key.get(key, {"income": 0, "expenses": 0})
        result.append({
            "month": label,
            "income": _from_pence(data["income"]),
            "expenses": _from_pence(data["expenses"]),
        })

    return result


def get_spending_by_category(
    db: sqlite3.Connection,
    *,
    today: date | None = None,
) -> list[dict]:
    """Current-month spending grouped by category for a donut chart.

    Only includes debit (negative-amount) transactions. Joins with the
    categories table to include display_name and colour.

    Returns:
        List of dicts ``{category, display_name, colour, total, percentage}``
        ordered by total descending.  Empty list if no debits this month.
    """
    today = today or date.today()
    boundaries = _month_boundaries(today, 1)
    _, month_start, month_end = boundaries[0]

    rows = db.execute(
        """
        SELECT
            t.category,
            c.label  AS display_name,
            c.colour,
            COALESCE(SUM(ABS(t.amount)), 0) AS total
        FROM transactions t
        LEFT JOIN categories c ON c.name = t.category
        WHERE t.amount < 0
          AND t.date >= ?
          AND t.date < ?
        GROUP BY t.category
        ORDER BY total DESC
        """,
        (month_start, month_end),
    ).fetchall()

    grand_total = sum(r["total"] for r in rows)

    return [
        {
            "category": r["category"],
            "display_name": r["display_name"],
            "colour": r["colour"],
            "total": _from_pence(r["total"]),
            "percentage": round(r["total"] / grand_total * 100, 1)
            if grand_total > 0
            else 0.0,
        }
        for r in rows
    ]


def get_cash_flow(
    db: sqlite3.Connection,
    *,
    months: int = 6,
    today: date | None = None,
) -> list[dict]:
    """Monthly cash flow breakdown for an area/bar chart.

    Returns:
        List of dicts ``{month, income, expenses, net, cumulative}``
        ordered oldest-first.  Empty months are filled with zeroes.
        ``cumulative`` is the running sum of ``net`` across the period.
    """
    today = today or date.today()
    boundaries = _month_boundaries(today, months)
    range_start = boundaries[0][1]
    range_end = boundaries[-1][2]

    rows = db.execute(
        """
        SELECT
            strftime('%Y-%m', date) AS month_key,
            COALESCE(SUM(CASE WHEN amount > 0 THEN amount
                         ELSE 0 END), 0) AS income,
            COALESCE(SUM(CASE WHEN amount < 0 THEN ABS(amount)
                         ELSE 0 END), 0) AS expenses
        FROM transactions
        WHERE date >= ? AND date < ?
        GROUP BY month_key
        ORDER BY month_key
        """,
        (range_start, range_end),
    ).fetchall()

    by_key: dict[str, dict] = {
        r["month_key"]: {"income": r["income"], "expenses": r["expenses"]}
        for r in rows
    }

    result: list[dict] = []
    cumulative_pence = 0
    for label, start_iso, _ in boundaries:
        key = start_iso[:7]
        data = by_key.get(key, {"income": 0, "expenses": 0})
        net_pence = data["income"] - data["expenses"]
        cumulative_pence += net_pence
        result.append({
            "month": label,
            "income": _from_pence(data["income"]),
            "expenses": _from_pence(data["expenses"]),
            "net": _from_pence(net_pence),
            "cumulative": _from_pence(cumulative_pence),
        })

    return result


def get_recent_transactions(
    db: sqlite3.Connection,
    *,
    limit: int = 10,
) -> list[dict]:
    """Last N transactions for the dashboard table.

    Joins with categories to include the human-readable category name.

    Returns:
        List of transaction dicts ordered newest-first.
    """
    rows = db.execute(
        """
        SELECT
            t.id,
            t.date,
            t.name,
            t.category,
            c.label AS category_display_name,
            t.amount,
            t.is_income
        FROM transactions t
        LEFT JOIN categories c ON c.name = t.category
        ORDER BY t.date DESC, t.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    return [
        {
            "id": r["id"],
            "date": r["date"],
            "name": r["name"],
            "category": r["category"],
            "category_display_name": r["category_display_name"],
            "amount": _from_pence(r["amount"]),
            "is_income": r["is_income"],
        }
        for r in rows
    ]


def get_finance_dashboard(
    db: sqlite3.Connection,
    *,
    months: int = 6,
    limit: int = 10,
) -> dict:
    """Assemble all finance dashboard data into a single response dict.

    Args:
        db: Active database connection.
        months: Number of months for chart history (1–24).
        limit: Number of recent transactions to include (1–50).

    Returns:
        Dict with keys: summary, income_vs_expenses, spending_by_category,
        cash_flow, budget_status, recent_transactions.

    Raises:
        ValueError: If months or limit are outside valid ranges.
    """
    if not 1 <= months <= 24:
        raise ValueError("months must be between 1 and 24")
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")

    from app.services.budgets import get_budget_status

    return {
        "summary": get_summary(db),
        "income_vs_expenses": get_income_vs_expenses(db, months=months),
        "spending_by_category": get_spending_by_category(db),
        "cash_flow": get_cash_flow(db, months=months),
        "budget_status": get_budget_status(db),
        "recent_transactions": get_recent_transactions(db, limit=limit),
    }
