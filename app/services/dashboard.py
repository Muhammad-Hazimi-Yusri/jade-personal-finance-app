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


def _parse_iso_date(s: str) -> date:
    """Parse an ISO 8601 date string (YYYY-MM-DD) into a date object.

    Raises:
        ValueError: If the string is not a valid ISO date.
    """
    return date.fromisoformat(s)


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


def _date_range_boundaries(
    start_date: str, end_date: str
) -> list[tuple[str, str, str]]:
    """Return (label, start_iso, exclusive_end_iso) for each calendar month
    spanned by the given date range.

    Args:
        start_date: ISO 8601 date string for the range start (inclusive).
        end_date: ISO 8601 date string for the range end (inclusive).

    Returns:
        List of tuples ordered oldest-first, one per calendar month.
    """
    sd = _parse_iso_date(start_date)
    ed = _parse_iso_date(end_date)

    result: list[tuple[str, str, str]] = []
    year, month = sd.year, sd.month

    while True:
        month_start = date(year, month, 1)
        if month == 12:
            exclusive_end = date(year + 1, 1, 1)
        else:
            exclusive_end = date(year, month + 1, 1)

        # Stop if this month starts after the end date
        if month_start > ed:
            break

        label = month_start.strftime("%b %Y")
        result.append((label, month_start.isoformat(), exclusive_end.isoformat()))

        # Advance to next month
        month += 1
        if month > 12:
            month = 1
            year += 1

    return result


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def get_summary(
    db: sqlite3.Connection,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    today: date | None = None,
) -> dict:
    """Compute top-level KPIs: balance, period income/expenses/net/savings.

    Args:
        db: Active database connection.
        start_date: ISO 8601 start of period (inclusive). Defaults to current month.
        end_date: ISO 8601 end of period (inclusive). Defaults to today.
        today: Reference date (defaults to today; accepts override for tests).

    Returns:
        Dict with balance, income, expenses, net,
        and savings_rate (percentage, 0.0 when no income).
    """
    today = today or date.today()

    if start_date and end_date:
        period_start = start_date
        # Use exclusive end: day after end_date
        ed = _parse_iso_date(end_date)
        period_end = (ed + timedelta(days=1)).isoformat()
    else:
        boundaries = _month_boundaries(today, 1)
        _, period_start, period_end = boundaries[0]

    row = db.execute(
        """
        SELECT
            COALESCE(SUM(amount), 0) AS balance,
            COALESCE(SUM(CASE WHEN date >= ? AND date < ?
                              AND amount > 0
                         THEN amount ELSE 0 END), 0) AS period_income,
            COALESCE(SUM(CASE WHEN date >= ? AND date < ?
                              AND amount < 0
                         THEN amount ELSE 0 END), 0) AS period_expenses
        FROM transactions
        """,
        (period_start, period_end, period_start, period_end),
    ).fetchone()

    balance = row["balance"]
    period_income = row["period_income"]
    period_expenses = row["period_expenses"]
    period_net = period_income + period_expenses  # expenses already negative

    savings_rate = (
        round(period_net / period_income * 100, 1) if period_income > 0 else 0.0
    )

    return {
        "balance": _from_pence(balance),
        "income": _from_pence(period_income),
        "expenses": _from_pence(abs(period_expenses)),
        "net": _from_pence(period_net),
        "savings_rate": savings_rate,
    }


def get_income_vs_expenses(
    db: sqlite3.Connection,
    *,
    months: int = 6,
    start_date: str | None = None,
    end_date: str | None = None,
    today: date | None = None,
) -> list[dict]:
    """Per-month income and expense totals for a bar chart.

    Args:
        db: Active database connection.
        months: How many months of history (default 6). Ignored when
            start_date/end_date are provided.
        start_date: ISO 8601 start of period (inclusive).
        end_date: ISO 8601 end of period (inclusive).
        today: Reference date override for tests.

    Returns:
        List of dicts ``{month, income, expenses}`` ordered oldest-first.
        Empty months are filled with zeroes.
    """
    today = today or date.today()
    if start_date and end_date:
        boundaries = _date_range_boundaries(start_date, end_date)
    else:
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
    start_date: str | None = None,
    end_date: str | None = None,
    today: date | None = None,
) -> list[dict]:
    """Spending grouped by category for a donut chart.

    Only includes debit (negative-amount) transactions. Joins with the
    categories table to include display_name and colour.

    Args:
        db: Active database connection.
        start_date: ISO 8601 start of period (inclusive). Defaults to current month.
        end_date: ISO 8601 end of period (inclusive). Defaults to today.
        today: Reference date override for tests.

    Returns:
        List of dicts ``{category, display_name, colour, total, percentage}``
        ordered by total descending.  Empty list if no debits in the period.
    """
    today = today or date.today()

    if start_date and end_date:
        month_start = start_date
        ed = _parse_iso_date(end_date)
        month_end = (ed + timedelta(days=1)).isoformat()
    else:
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
    start_date: str | None = None,
    end_date: str | None = None,
    today: date | None = None,
) -> list[dict]:
    """Monthly cash flow breakdown for an area/bar chart.

    Args:
        db: Active database connection.
        months: How many months of history (default 6). Ignored when
            start_date/end_date are provided.
        start_date: ISO 8601 start of period (inclusive).
        end_date: ISO 8601 end of period (inclusive).
        today: Reference date override for tests.

    Returns:
        List of dicts ``{month, income, expenses, net, cumulative}``
        ordered oldest-first.  Empty months are filled with zeroes.
        ``cumulative`` is the running sum of ``net`` across the period.
    """
    today = today or date.today()
    if start_date and end_date:
        boundaries = _date_range_boundaries(start_date, end_date)
    else:
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
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 10,
) -> dict:
    """Assemble all finance dashboard data into a single response dict.

    Args:
        db: Active database connection.
        months: Number of months for chart history (1–24). Ignored when
            start_date/end_date are provided.
        start_date: ISO 8601 start of date range (inclusive).
        end_date: ISO 8601 end of date range (inclusive).
        limit: Number of recent transactions to include (1–50).

    Returns:
        Dict with keys: summary, income_vs_expenses, spending_by_category,
        cash_flow, budget_status, recent_transactions.

    Raises:
        ValueError: If months or limit are outside valid ranges, or if
            dates are invalid.
    """
    if start_date and end_date:
        # Validate dates
        sd = _parse_iso_date(start_date)
        ed = _parse_iso_date(end_date)
        if sd > ed:
            raise ValueError("start_date must be on or before end_date")
    else:
        if not 1 <= months <= 24:
            raise ValueError("months must be between 1 and 24")

    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")

    date_kwargs: dict = {}
    if start_date and end_date:
        date_kwargs = {"start_date": start_date, "end_date": end_date}

    from app.services.budgets import get_budget_status

    return {
        "summary": get_summary(db, **date_kwargs),
        "income_vs_expenses": get_income_vs_expenses(
            db, months=months, **date_kwargs
        ),
        "spending_by_category": get_spending_by_category(db, **date_kwargs),
        "cash_flow": get_cash_flow(db, months=months, **date_kwargs),
        "budget_status": get_budget_status(db),
        "recent_transactions": get_recent_transactions(db, limit=limit),
    }
