"""Reports service layer for Jade.

Aggregation queries for spending reports and period comparisons.
Route handlers call these functions and never access the database directly.

Money convention: the database stores all monetary values as integer pence.
This module converts outbound pence back to decimals (/ 100) so the rest
of the app only sees decimals.
"""

import sqlite3
from datetime import date


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

    Results are ordered oldest-first.
    """
    result: list[tuple[str, str, str]] = []
    for i in range(months_back - 1, -1, -1):
        year = ref_date.year
        month = ref_date.month - i
        while month <= 0:
            month += 12
            year -= 1

        start = date(year, month, 1)

        if month == 12:
            exclusive_end = date(year + 1, 1, 1)
        else:
            exclusive_end = date(year, month + 1, 1)

        label = start.strftime("%b %Y")
        result.append((label, start.isoformat(), exclusive_end.isoformat()))

    return result


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def get_spending_comparison(
    db: sqlite3.Connection,
    *,
    period: str = "month",
    today: date | None = None,
) -> dict:
    """Compare spending by category between the current and previous period.

    Args:
        db: Active database connection.
        period: Comparison period type. Currently only ``"month"`` is
            supported (this month vs last month).
        today: Reference date (defaults to today; accepts override for tests).

    Returns:
        Dict with ``current_period``, ``previous_period``, ``categories``
        (list of per-category comparisons), and ``totals``.

    Raises:
        ValueError: If *period* is not a supported value.
    """
    if period != "month":
        raise ValueError(f"Unsupported period: {period!r}. Only 'month' is supported.")

    today = today or date.today()

    # Current month and previous month boundaries
    boundaries = _month_boundaries(today, 2)
    prev_label, prev_start, prev_end = boundaries[0]
    curr_label, curr_start, curr_end = boundaries[1]

    # Single query with conditional aggregation for both periods
    rows = db.execute(
        """
        SELECT
            t.category,
            c.label   AS display_name,
            c.colour,
            COALESCE(SUM(CASE WHEN t.date >= ? AND t.date < ?
                              THEN ABS(t.amount) ELSE 0 END), 0) AS current_total,
            COALESCE(SUM(CASE WHEN t.date >= ? AND t.date < ?
                              THEN ABS(t.amount) ELSE 0 END), 0) AS previous_total
        FROM transactions t
        LEFT JOIN categories c ON c.name = t.category
        WHERE t.amount < 0
          AND t.date >= ?
          AND t.date < ?
        GROUP BY t.category
        ORDER BY current_total DESC
        """,
        (
            curr_start, curr_end,
            prev_start, prev_end,
            prev_start, curr_end,
        ),
    ).fetchall()

    # Build per-category comparison list
    categories_list: list[dict] = []
    grand_current = 0
    grand_previous = 0

    for r in rows:
        current_pence = r["current_total"]
        previous_pence = r["previous_total"]

        # Skip categories with zero in both periods
        if current_pence == 0 and previous_pence == 0:
            continue

        change_pence = current_pence - previous_pence
        change_pct = (
            round(change_pence / previous_pence * 100, 1)
            if previous_pence > 0
            else None
        )

        grand_current += current_pence
        grand_previous += previous_pence

        categories_list.append({
            "category": r["category"],
            "display_name": r["display_name"],
            "colour": r["colour"],
            "current": _from_pence(current_pence),
            "previous": _from_pence(previous_pence),
            "change": _from_pence(change_pence),
            "change_pct": change_pct,
        })

    # Grand totals
    total_change = grand_current - grand_previous
    total_change_pct = (
        round(total_change / grand_previous * 100, 1)
        if grand_previous > 0
        else None
    )

    return {
        "current_period": {
            "label": curr_label,
            "start": curr_start,
            "end": curr_end,
        },
        "previous_period": {
            "label": prev_label,
            "start": prev_start,
            "end": prev_end,
        },
        "categories": categories_list,
        "totals": {
            "current": _from_pence(grand_current),
            "previous": _from_pence(grand_previous),
            "change": _from_pence(total_change),
            "change_pct": total_change_pct,
        },
    }
