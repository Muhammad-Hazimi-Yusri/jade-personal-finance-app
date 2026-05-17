"""Reports service layer for Jade.

Aggregation queries for spending reports and period comparisons.
Route handlers call these functions and never access the database directly.

Money convention: the database stores all monetary values as integer pence.
This module converts outbound pence back to decimals (/ 100) so the rest
of the app only sees decimals.
"""

import sqlite3
from datetime import date, timedelta

from app.services.csv_parser import TRANSFER_CATEGORIES

# Inline SQL fragment to exclude internal transfers (savings/transfers
# categories) from spending aggregations. Built once at module load —
# values are fixed snake_case keys, no user input.
_NOT_TRANSFER_SQL = (
    "category NOT IN ("
    + ", ".join(f"'{c}'" for c in TRANSFER_CATEGORIES)
    + ")"
)


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


def _format_range_label(sd: date, ed: date) -> str:
    """Create a human-readable label for a date range.

    Same month: "Mar 2026".  Cross-month: "Jan–Mar 2026".  Cross-year:
    "Nov 2025–Mar 2026".
    """
    if sd.year == ed.year and sd.month == ed.month:
        return sd.strftime("%b %Y")
    if sd.year == ed.year:
        return f"{sd.strftime('%b')}–{ed.strftime('%b %Y')}"
    return f"{sd.strftime('%b %Y')}–{ed.strftime('%b %Y')}"


def get_spending_comparison(
    db: sqlite3.Connection,
    *,
    period: str = "month",
    start_date: str | None = None,
    end_date: str | None = None,
    today: date | None = None,
) -> dict:
    """Compare spending by category between the current and previous period.

    Args:
        db: Active database connection.
        period: Comparison period type (``"month"``). Ignored when
            start_date/end_date are provided.
        start_date: ISO 8601 start of "current" period (inclusive).
        end_date: ISO 8601 end of "current" period (inclusive).
            The "previous" period is auto-computed as the same duration
            shifted backward.
        today: Reference date (defaults to today; accepts override for tests).

    Returns:
        Dict with ``current_period``, ``previous_period``, ``categories``
        (list of per-category comparisons), and ``totals``.

    Raises:
        ValueError: If dates are invalid or *period* is unsupported.
    """
    today = today or date.today()

    if start_date and end_date:
        sd = date.fromisoformat(start_date)
        ed = date.fromisoformat(end_date)
        if sd > ed:
            raise ValueError("start_date must be on or before end_date")

        # Current period: start_date to end_date (inclusive → exclusive end)
        curr_start = start_date
        curr_end = (ed + timedelta(days=1)).isoformat()
        curr_label = _format_range_label(sd, ed)

        # Previous period: shift back by the same duration
        duration = (ed - sd).days + 1  # inclusive count
        prev_ed = sd - timedelta(days=1)
        prev_sd = prev_ed - timedelta(days=duration - 1)
        prev_start = prev_sd.isoformat()
        prev_end = (prev_ed + timedelta(days=1)).isoformat()
        prev_label = _format_range_label(prev_sd, prev_ed)
    else:
        if period != "month":
            raise ValueError(
                f"Unsupported period: {period!r}. Only 'month' is supported."
            )
        # Current month and previous month boundaries
        boundaries = _month_boundaries(today, 2)
        prev_label, prev_start, prev_end = boundaries[0]
        curr_label, curr_start, curr_end = boundaries[1]

    # Single query with conditional aggregation for both periods
    rows = db.execute(
        f"""
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
          AND t.{_NOT_TRANSFER_SQL}
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
