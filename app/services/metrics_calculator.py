"""Aggregate trading metrics for Jade.

Pure functions operating on lists of trade dicts (already filtered to closed
trades by the DB query).  All monetary values are integer pence throughout
these functions; only the public ``get_trading_performance`` orchestrator
converts to decimal via ``_from_pence`` before returning.

These are pure functions with no side effects and no database access.
``get_trading_performance`` is the only function that touches the DB.
"""

import math
import sqlite3
from datetime import date
from typing import Optional


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _from_pence(pence: int) -> float:
    """Convert integer pence to a decimal float for API responses."""
    return round(pence / 100, 2)


def _nice_width(raw: float) -> int:
    """Round a raw bin width in pence to a human-readable step."""
    nice_steps = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500,
                  1000, 2000, 2500, 5000, 10000, 20000, 50000,
                  100000, 200000, 500000]
    for step in nice_steps:
        if step >= raw:
            return step
    return int(raw)


def _format_bin_label(lo_pence: int, hi_pence: int) -> str:
    """Format a bin range as a GBP string, e.g. '£-100 to £-50'."""
    def _fmt(p: int) -> str:
        pounds = p / 100
        sign = "-" if pounds < 0 else ""
        return f"£{sign}{abs(pounds):.0f}"
    return f"{_fmt(lo_pence)} to {_fmt(hi_pence)}"


_NICE_R_STEPS = [0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0]


def _nice_r_step(raw: float) -> float:
    """Round a raw bin width to a human-readable R-multiple step."""
    for step in _NICE_R_STEPS:
        if step >= raw:
            return step
    return raw


def _format_r_label(lo: float, hi: float) -> str:
    """Format a bin range as an R-multiple string, e.g. '-2.00R to -1.00R'."""
    def _fmt(v: float) -> str:
        sign = "-" if v < 0 else ""
        return f"{sign}{abs(v):.2f}R"
    return f"{_fmt(lo)} to {_fmt(hi)}"


# ---------------------------------------------------------------------------
# Pure metric functions
# ---------------------------------------------------------------------------


def calculate_win_rate(trades: list[dict]) -> Optional[float]:
    """Percentage of winning trades in the set.

    Formula: winning_trades / total_closed_trades × 100

    A win is ``pnl_net > 0``.  Breakeven trades (``pnl_net == 0``) count
    toward the total but are neither wins nor losses.

    Args:
        trades: List of closed-trade dicts with a ``pnl_net`` key.

    Returns:
        Win rate as a float (0.0–100.0), or None if the list is empty.
    """
    if not trades:
        return None
    winning = sum(1 for t in trades if t["pnl_net"] is not None and t["pnl_net"] > 0)
    return round(winning / len(trades) * 100, 2)


def calculate_profit_factor(trades: list[dict]) -> Optional[float]:
    """Ratio of total winning P&L to absolute total losing P&L.

    Formula: sum(winning_pnl) / abs(sum(losing_pnl))

    Breakeven trades (``pnl_net == 0``) are excluded from both sides.

    Args:
        trades: List of closed-trade dicts with a ``pnl_net`` key.

    Returns:
        Profit factor as a float, or None if there are no winning trades,
        no losing trades, or the trade list is empty.
    """
    if not trades:
        return None
    total_wins = sum(t["pnl_net"] for t in trades if t["pnl_net"] is not None and t["pnl_net"] > 0)
    total_losses = sum(t["pnl_net"] for t in trades if t["pnl_net"] is not None and t["pnl_net"] < 0)
    if total_wins == 0 or total_losses == 0:
        return None
    return round(total_wins / abs(total_losses), 4)


def calculate_expectancy(trades: list[dict]) -> Optional[int]:
    """Expected P&L per trade in integer pence.

    Formula: (win_rate_decimal × avg_win_pence) − (loss_rate_decimal × abs(avg_loss_pence))

    Breakeven trades contribute to the total count (diluting expectancy)
    but not to win or loss sums.

    Args:
        trades: List of closed-trade dicts with a ``pnl_net`` key.

    Returns:
        Expectancy as integer pence (truncated), or None if the list is empty.
    """
    if not trades:
        return None
    total = len(trades)
    wins = [t["pnl_net"] for t in trades if t["pnl_net"] is not None and t["pnl_net"] > 0]
    losses = [t["pnl_net"] for t in trades if t["pnl_net"] is not None and t["pnl_net"] < 0]
    win_rate = len(wins) / total
    loss_rate = len(losses) / total
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0
    return int((win_rate * avg_win) - (loss_rate * avg_loss))


def calculate_avg_r_multiple(trades: list[dict]) -> Optional[float]:
    """Mean R-multiple across trades that have an R value.

    Formula: sum(r_multiples) / count_of_trades_with_r_multiple

    Trades where ``r_multiple`` is None are excluded from both numerator
    and denominator.

    Args:
        trades: List of closed-trade dicts with an ``r_multiple`` key.

    Returns:
        Average R-multiple as a float, or None if no trade has an R value.
    """
    if not trades:
        return None
    r_values = [t["r_multiple"] for t in trades if t["r_multiple"] is not None]
    if not r_values:
        return None
    return round(sum(r_values) / len(r_values), 4)


def calculate_max_drawdown(trades: list[dict]) -> Optional[float]:
    """Maximum peak-to-trough drawdown as a percentage of peak equity.

    Equity is modelled as the running cumulative sum of ``pnl_net`` values,
    starting from a 0 baseline, ordered by ``exit_date`` ascending.

    Formula: (peak_equity − trough_equity) / peak_equity × 100

    Edge cases:
    - Empty list → None.
    - All-win sequence (equity never falls below a prior peak) → 0.0.
    - All-loss sequence from zero baseline (``peak`` never exceeds 0) → 0.0,
      because the formula has ``peak`` in the denominator.

    Args:
        trades: List of closed-trade dicts with ``pnl_net`` and ``exit_date`` keys.

    Returns:
        Largest drawdown as a positive percentage float (e.g. ``15.3`` means
        a −15.3% drawdown), or None if the list is empty.
    """
    if not trades:
        return None

    # Sort defensively so the function is self-contained and testable
    sorted_trades = sorted(trades, key=lambda t: (t["exit_date"] or ""))

    cumulative = 0
    peak = 0
    max_dd = 0.0

    for trade in sorted_trades:
        pnl = trade["pnl_net"]
        if pnl is None:
            continue
        cumulative += pnl
        if cumulative > peak:
            peak = cumulative
        if peak > 0:
            dd = (peak - cumulative) / peak * 100
            if dd > max_dd:
                max_dd = dd

    return round(max_dd, 2)


def calculate_streaks(trades: list[dict]) -> tuple[int, int]:
    """Longest consecutive winning and losing streaks.

    Trades are ordered by ``exit_date`` ascending before analysis.
    Breakeven trades (``pnl_net == 0``) reset both win and loss counters.

    Args:
        trades: List of closed-trade dicts with ``pnl_net`` and ``exit_date`` keys.

    Returns:
        ``(max_consecutive_wins, max_consecutive_losses)``  — both 0 if empty.
    """
    if not trades:
        return (0, 0)

    sorted_trades = sorted(trades, key=lambda t: (t["exit_date"] or ""))

    max_wins = 0
    max_losses = 0
    cur_wins = 0
    cur_losses = 0

    for trade in sorted_trades:
        pnl = trade["pnl_net"]
        if pnl is None or pnl == 0:
            # Breakeven or unknown — reset both streaks
            cur_wins = 0
            cur_losses = 0
        elif pnl > 0:
            cur_wins += 1
            cur_losses = 0
            if cur_wins > max_wins:
                max_wins = cur_wins
        else:
            cur_losses += 1
            cur_wins = 0
            if cur_losses > max_losses:
                max_losses = cur_losses

    return (max_wins, max_losses)


def calculate_avg_win(trades: list[dict]) -> Optional[int]:
    """Mean P&L of winning trades, in integer pence (truncated).

    Breakeven trades are excluded.

    Args:
        trades: List of closed-trade dicts with a ``pnl_net`` key.

    Returns:
        Average winning P&L as integer pence, or None if there are no wins.
    """
    wins = [t["pnl_net"] for t in trades if t["pnl_net"] is not None and t["pnl_net"] > 0]
    if not wins:
        return None
    return int(sum(wins) / len(wins))


def calculate_avg_loss(trades: list[dict]) -> Optional[int]:
    """Mean P&L of losing trades, in integer pence (truncated, negative).

    Breakeven trades are excluded.

    Args:
        trades: List of closed-trade dicts with a ``pnl_net`` key.

    Returns:
        Average losing P&L as integer pence (a negative number), or None if
        there are no losing trades.
    """
    losses = [t["pnl_net"] for t in trades if t["pnl_net"] is not None and t["pnl_net"] < 0]
    if not losses:
        return None
    return int(sum(losses) / len(losses))


def calculate_largest_win(trades: list[dict]) -> Optional[int]:
    """Largest single-trade P&L in integer pence.

    Args:
        trades: List of closed-trade dicts with a ``pnl_net`` key.

    Returns:
        Maximum ``pnl_net`` as integer pence, or None if the list is empty
        or all ``pnl_net`` values are None.
    """
    values = [t["pnl_net"] for t in trades if t["pnl_net"] is not None]
    return max(values) if values else None


def calculate_largest_loss(trades: list[dict]) -> Optional[int]:
    """Smallest (most negative) single-trade P&L in integer pence.

    Args:
        trades: List of closed-trade dicts with a ``pnl_net`` key.

    Returns:
        Minimum ``pnl_net`` as integer pence (negative if there was a loss),
        or None if the list is empty or all ``pnl_net`` values are None.
    """
    values = [t["pnl_net"] for t in trades if t["pnl_net"] is not None]
    return min(values) if values else None


def calculate_avg_duration_winners(trades: list[dict]) -> Optional[float]:
    """Mean duration in minutes of winning trades.

    Only includes trades where ``duration_minutes`` is not None.

    Args:
        trades: List of closed-trade dicts with ``pnl_net`` and
            ``duration_minutes`` keys.

    Returns:
        Mean duration as a float, or None if no eligible winning trade exists.
    """
    durations = [
        t["duration_minutes"]
        for t in trades
        if t["pnl_net"] is not None and t["pnl_net"] > 0 and t["duration_minutes"] is not None
    ]
    if not durations:
        return None
    return round(sum(durations) / len(durations), 1)


def calculate_avg_duration_losers(trades: list[dict]) -> Optional[float]:
    """Mean duration in minutes of losing trades.

    Only includes trades where ``duration_minutes`` is not None.

    Args:
        trades: List of closed-trade dicts with ``pnl_net`` and
            ``duration_minutes`` keys.

    Returns:
        Mean duration as a float, or None if no eligible losing trade exists.
    """
    durations = [
        t["duration_minutes"]
        for t in trades
        if t["pnl_net"] is not None and t["pnl_net"] < 0 and t["duration_minutes"] is not None
    ]
    if not durations:
        return None
    return round(sum(durations) / len(durations), 1)


def calculate_discipline_score(trades: list[dict]) -> Optional[float]:
    """Mean ``rules_followed_pct`` across trades where the field is set.

    Args:
        trades: List of closed-trade dicts with a ``rules_followed_pct`` key.

    Returns:
        Average discipline score (0–100) rounded to 1 decimal place, or None
        if no trade has ``rules_followed_pct`` set.
    """
    scores = [t["rules_followed_pct"] for t in trades if t["rules_followed_pct"] is not None]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 1)


def calculate_pnl_distribution(values: list[int]) -> dict:
    """Compute histogram bin data from a list of pnl_net pence values.

    Bins are auto-sized using Sturges' rule (capped at 20), then snapped to a
    human-readable step via ``_nice_width``.  All monetary values in the
    returned dicts are decimal pounds (already divided by 100).

    Args:
        values: Flat list of pnl_net values in integer pence for closed trades.

    Returns:
        Dict with ``bins`` (list of bin dicts) and ``total`` (int trade count).
        Each bin dict contains: ``label``, ``min``, ``max``, ``count``,
        ``midpoint`` — all monetary values in decimal pounds.
    """
    n = len(values)
    if n == 0:
        return {"bins": [], "total": 0}

    lo = min(values)
    hi = max(values)

    # Edge case: all trades at the same P&L — produce one bin
    if lo == hi:
        return {
            "bins": [{
                "label": _format_bin_label(lo, lo),
                "min": round(lo / 100, 2),
                "max": round(lo / 100, 2),
                "count": n,
                "midpoint": round(lo / 100, 2),
            }],
            "total": n,
        }

    # Sturges' rule, capped at 20 bins
    k = min(math.ceil(math.log2(n)) + 1, 20)
    raw_width = (hi - lo) / k
    bin_width = _nice_width(raw_width)

    # Grid-align the lower bound so bin edges land on round numbers
    bin_lo = math.floor(lo / bin_width) * bin_width

    bins: list[dict] = []
    edge = bin_lo
    while True:
        bin_hi = edge + bin_width
        # Last bin is inclusive on upper bound to capture hi exactly
        if bin_hi >= hi:
            count = sum(1 for v in values if edge <= v <= hi)
        else:
            count = sum(1 for v in values if edge <= v < bin_hi)
        midpoint = (edge + bin_hi) / 2 / 100
        bins.append({
            "label": _format_bin_label(edge, bin_hi),
            "min": round(edge / 100, 2),
            "max": round(bin_hi / 100, 2),
            "count": count,
            "midpoint": round(midpoint, 2),
        })
        edge = bin_hi
        if edge >= hi:
            break

    # Drop bins that fall entirely outside the data range
    bins = [b for b in bins if b["min"] <= round(hi / 100, 2) and b["max"] >= round(lo / 100, 2)]

    return {"bins": bins, "total": n}


def calculate_r_distribution(values: list[float]) -> dict:
    """Compute histogram bin data from a list of r_multiple float values.

    Bins are auto-sized using Sturges' rule (capped at 20), then snapped to a
    human-readable R step via ``_nice_r_step``.

    Args:
        values: Flat list of r_multiple floats for closed trades.

    Returns:
        Dict with ``bins`` (list of bin dicts) and ``total`` (int trade count).
        Each bin dict contains: ``label``, ``min``, ``max``, ``count``,
        ``midpoint`` — all as R-multiple floats.
    """
    n = len(values)
    if n == 0:
        return {"bins": [], "total": 0}

    lo = min(values)
    hi = max(values)

    # Edge case: all trades have identical R — produce one bin
    if lo == hi:
        return {
            "bins": [{
                "label": _format_r_label(lo, lo),
                "min": round(lo, 4),
                "max": round(lo, 4),
                "count": n,
                "midpoint": round(lo, 4),
            }],
            "total": n,
        }

    # Sturges' rule, capped at 20 bins
    k = min(math.ceil(math.log2(n)) + 1, 20)
    raw_width = (hi - lo) / k
    bin_width = _nice_r_step(raw_width)

    # Grid-align the lower bound so bin edges land on round numbers
    bin_lo = math.floor(lo / bin_width) * bin_width

    bins: list[dict] = []
    edge = bin_lo
    while True:
        bin_hi = edge + bin_width
        if bin_hi >= hi:
            count = sum(1 for v in values if edge <= v <= hi)
        else:
            count = sum(1 for v in values if edge <= v < bin_hi)
        midpoint = round((edge + bin_hi) / 2, 4)
        bins.append({
            "label": _format_r_label(edge, bin_hi),
            "min": round(edge, 4),
            "max": round(bin_hi, 4),
            "count": count,
            "midpoint": midpoint,
        })
        edge = bin_hi
        if edge >= hi:
            break

    bins = [b for b in bins if b["min"] <= round(hi, 4) and b["max"] >= round(lo, 4)]

    return {"bins": bins, "total": n}


# ---------------------------------------------------------------------------
# DB-facing orchestrator
# ---------------------------------------------------------------------------


def get_trading_performance(
    db: sqlite3.Connection,
    *,
    account_id: Optional[int] = None,
    strategy_id: Optional[int] = None,
    asset_class: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """Compute aggregate trading performance metrics for a filtered trade set.

    Queries the ``trades`` table for all closed trades matching the supplied
    filters, then delegates to the pure metric functions above.

    Date filters apply to ``exit_date`` (i.e. when the trade closed), not
    ``entry_date``.

    Args:
        db: Active database connection.
        account_id: Restrict to trades from this account.
        strategy_id: Restrict to trades using this strategy.
        asset_class: Restrict to trades of this asset class (e.g. "stocks").
        start_date: ISO 8601 date string (YYYY-MM-DD); include trades where
            ``exit_date >= start_date``.
        end_date: ISO 8601 date string (YYYY-MM-DD); include trades where
            ``exit_date <= end_date``.

    Returns:
        Dict with ``filters``, ``summary``, and ``metrics`` sections.
        Monetary metric values are decimal pounds (pence ÷ 100).
        Any metric that cannot be computed is ``None``.

    Raises:
        ValueError: If date strings are invalid or start_date > end_date.
    """
    # Validate dates
    if start_date:
        date.fromisoformat(start_date)
    if end_date:
        date.fromisoformat(end_date)
    if start_date and end_date:
        if date.fromisoformat(start_date) > date.fromisoformat(end_date):
            raise ValueError("start_date must be on or before end_date")

    # Build dynamic WHERE clause
    conditions = ["is_open = 0"]
    params: list = []

    if account_id is not None:
        conditions.append("account_id = ?")
        params.append(account_id)
    if strategy_id is not None:
        conditions.append("strategy_id = ?")
        params.append(strategy_id)
    if asset_class is not None:
        conditions.append("asset_class = ?")
        params.append(asset_class)
    if start_date is not None:
        conditions.append("exit_date >= ?")
        params.append(start_date)
    if end_date is not None:
        conditions.append("exit_date <= ?")
        params.append(end_date)

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT pnl_net, r_multiple, duration_minutes, rules_followed_pct, exit_date
        FROM trades
        WHERE {where_clause}
        ORDER BY exit_date ASC, id ASC
    """  # noqa: S608 — where_clause built from literals only, no user data

    rows = db.execute(sql, params).fetchall()
    trades = [dict(row) for row in rows]

    # Summary counts
    total_closed = len(trades)
    winning_count = sum(1 for t in trades if t["pnl_net"] is not None and t["pnl_net"] > 0)
    losing_count = sum(1 for t in trades if t["pnl_net"] is not None and t["pnl_net"] < 0)
    breakeven_count = sum(1 for t in trades if t["pnl_net"] is not None and t["pnl_net"] == 0)

    # Pure metric calculations
    max_wins, max_losses = calculate_streaks(trades)

    avg_win_pence = calculate_avg_win(trades)
    avg_loss_pence = calculate_avg_loss(trades)
    largest_win_pence = calculate_largest_win(trades)
    largest_loss_pence = calculate_largest_loss(trades)
    expectancy_pence = calculate_expectancy(trades)

    return {
        "filters": {
            "account_id": account_id,
            "strategy_id": strategy_id,
            "asset_class": asset_class,
            "start_date": start_date,
            "end_date": end_date,
        },
        "summary": {
            "total_closed_trades": total_closed,
            "winning_trades": winning_count,
            "losing_trades": losing_count,
            "breakeven_trades": breakeven_count,
        },
        "metrics": {
            "win_rate": calculate_win_rate(trades),
            "profit_factor": calculate_profit_factor(trades),
            "expectancy": _from_pence(expectancy_pence) if expectancy_pence is not None else None,
            "avg_r_multiple": calculate_avg_r_multiple(trades),
            "max_drawdown_pct": calculate_max_drawdown(trades),
            "max_consecutive_wins": max_wins,
            "max_consecutive_losses": max_losses,
            "avg_win": _from_pence(avg_win_pence) if avg_win_pence is not None else None,
            "avg_loss": _from_pence(avg_loss_pence) if avg_loss_pence is not None else None,
            "largest_win": _from_pence(largest_win_pence) if largest_win_pence is not None else None,
            "largest_loss": _from_pence(largest_loss_pence) if largest_loss_pence is not None else None,
            "avg_duration_winners_minutes": calculate_avg_duration_winners(trades),
            "avg_duration_losers_minutes": calculate_avg_duration_losers(trades),
            "discipline_score": calculate_discipline_score(trades),
        },
    }


def get_equity_curve(
    db: sqlite3.Connection,
    *,
    account_id: Optional[int] = None,
    strategy_id: Optional[int] = None,
    asset_class: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """Cumulative P&L equity curve data points from closed trades.

    Groups closed trades by exit_date, sums daily P&L, then computes the
    running cumulative sum.  Returns a list of ``{time, value}`` dicts ready
    for TradingView Lightweight Charts.

    Args:
        db: Active SQLite connection.
        account_id: Filter to a specific trading account.
        strategy_id: Filter to a specific strategy.
        asset_class: Filter to a specific asset class.
        start_date: ISO 8601 lower bound on exit_date (inclusive).
        end_date: ISO 8601 upper bound on exit_date (inclusive).

    Returns:
        Dict with a single ``points`` key containing a list of
        ``{"time": "YYYY-MM-DD", "value": float}`` dicts ordered by date.

    Raises:
        ValueError: If date strings are invalid or start_date > end_date.
    """
    if start_date is not None:
        try:
            date.fromisoformat(start_date)
        except ValueError:
            raise ValueError("start_date must be a valid ISO 8601 date (YYYY-MM-DD)")
    if end_date is not None:
        try:
            date.fromisoformat(end_date)
        except ValueError:
            raise ValueError("end_date must be a valid ISO 8601 date (YYYY-MM-DD)")
    if start_date is not None and end_date is not None:
        if date.fromisoformat(start_date) > date.fromisoformat(end_date):
            raise ValueError("start_date must be on or before end_date")

    conditions = ["is_open = 0", "exit_date IS NOT NULL", "pnl_net IS NOT NULL"]
    params: list = []

    if account_id is not None:
        conditions.append("account_id = ?")
        params.append(account_id)
    if strategy_id is not None:
        conditions.append("strategy_id = ?")
        params.append(strategy_id)
    if asset_class is not None:
        conditions.append("asset_class = ?")
        params.append(asset_class)
    if start_date is not None:
        conditions.append("exit_date >= ?")
        params.append(start_date)
    if end_date is not None:
        conditions.append("exit_date <= ?")
        params.append(end_date)

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT exit_date, SUM(pnl_net) AS daily_pnl
        FROM trades
        WHERE {where_clause}
        GROUP BY exit_date
        ORDER BY exit_date ASC
    """  # noqa: S608 — where_clause built from literals only, no user data

    rows = db.execute(sql, params).fetchall()

    points: list[dict] = []
    cumulative_pence = 0
    for row in rows:
        cumulative_pence += row["daily_pnl"]
        points.append({
            "time": row["exit_date"],
            "value": _from_pence(cumulative_pence),
        })

    return {"points": points}


def get_pnl_distribution(
    db: sqlite3.Connection,
    *,
    account_id: Optional[int] = None,
    strategy_id: Optional[int] = None,
    asset_class: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """P&L distribution histogram bins from closed trades.

    Fetches all pnl_net values for closed trades matching the filters, then
    delegates to ``calculate_pnl_distribution`` for bin computation.

    Args:
        db: Active SQLite connection.
        account_id: Filter to a specific trading account.
        strategy_id: Filter to a specific strategy.
        asset_class: Filter to a specific asset class.
        start_date: ISO 8601 lower bound on exit_date (inclusive).
        end_date: ISO 8601 upper bound on exit_date (inclusive).

    Returns:
        Dict with ``bins`` list and ``total`` int.  Each bin contains
        ``label``, ``min``, ``max``, ``count``, and ``midpoint`` (all monetary
        values in decimal pounds).

    Raises:
        ValueError: If date strings are invalid or start_date > end_date.
    """
    if start_date is not None:
        try:
            date.fromisoformat(start_date)
        except ValueError:
            raise ValueError("start_date must be a valid ISO 8601 date (YYYY-MM-DD)")
    if end_date is not None:
        try:
            date.fromisoformat(end_date)
        except ValueError:
            raise ValueError("end_date must be a valid ISO 8601 date (YYYY-MM-DD)")
    if start_date is not None and end_date is not None:
        if date.fromisoformat(start_date) > date.fromisoformat(end_date):
            raise ValueError("start_date must be on or before end_date")

    conditions = ["is_open = 0", "exit_date IS NOT NULL", "pnl_net IS NOT NULL"]
    params: list = []

    if account_id is not None:
        conditions.append("account_id = ?")
        params.append(account_id)
    if strategy_id is not None:
        conditions.append("strategy_id = ?")
        params.append(strategy_id)
    if asset_class is not None:
        conditions.append("asset_class = ?")
        params.append(asset_class)
    if start_date is not None:
        conditions.append("exit_date >= ?")
        params.append(start_date)
    if end_date is not None:
        conditions.append("exit_date <= ?")
        params.append(end_date)

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT pnl_net
        FROM trades
        WHERE {where_clause}
        ORDER BY pnl_net ASC
    """  # noqa: S608 — where_clause built from literals only, no user data

    rows = db.execute(sql, params).fetchall()
    return calculate_pnl_distribution([row["pnl_net"] for row in rows])


def get_r_distribution(
    db: sqlite3.Connection,
    *,
    account_id: Optional[int] = None,
    strategy_id: Optional[int] = None,
    asset_class: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """R-multiple distribution histogram bins from closed trades.

    Fetches all r_multiple values for closed trades matching the filters, then
    delegates to ``calculate_r_distribution`` for bin computation.

    Args:
        db: Active SQLite connection.
        account_id: Filter to a specific trading account.
        strategy_id: Filter to a specific strategy.
        asset_class: Filter to a specific asset class.
        start_date: ISO 8601 lower bound on exit_date (inclusive).
        end_date: ISO 8601 upper bound on exit_date (inclusive).

    Returns:
        Dict with ``bins`` list and ``total`` int.  Each bin contains
        ``label``, ``min``, ``max``, ``count``, and ``midpoint`` (R-multiple
        floats).  Trades with no ``r_multiple`` set are excluded.

    Raises:
        ValueError: If date strings are invalid or start_date > end_date.
    """
    if start_date is not None:
        try:
            date.fromisoformat(start_date)
        except ValueError:
            raise ValueError("start_date must be a valid ISO 8601 date (YYYY-MM-DD)")
    if end_date is not None:
        try:
            date.fromisoformat(end_date)
        except ValueError:
            raise ValueError("end_date must be a valid ISO 8601 date (YYYY-MM-DD)")
    if start_date is not None and end_date is not None:
        if date.fromisoformat(start_date) > date.fromisoformat(end_date):
            raise ValueError("start_date must be on or before end_date")

    conditions = ["is_open = 0", "exit_date IS NOT NULL", "r_multiple IS NOT NULL"]
    params: list = []

    if account_id is not None:
        conditions.append("account_id = ?")
        params.append(account_id)
    if strategy_id is not None:
        conditions.append("strategy_id = ?")
        params.append(strategy_id)
    if asset_class is not None:
        conditions.append("asset_class = ?")
        params.append(asset_class)
    if start_date is not None:
        conditions.append("exit_date >= ?")
        params.append(start_date)
    if end_date is not None:
        conditions.append("exit_date <= ?")
        params.append(end_date)

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT r_multiple
        FROM trades
        WHERE {where_clause}
        ORDER BY r_multiple ASC
    """  # noqa: S608 — where_clause built from literals only, no user data

    rows = db.execute(sql, params).fetchall()
    return calculate_r_distribution([row["r_multiple"] for row in rows])


def get_win_rate_by_strategy(
    db: sqlite3.Connection,
    *,
    account_id: Optional[int] = None,
    strategy_id: Optional[int] = None,
    asset_class: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """Win rate breakdown grouped by strategy for closed trades.

    Joins trades with the strategies table to resolve names.  Trades with no
    strategy are grouped under the label ``"No strategy"``.

    Args:
        db: Active SQLite connection.
        account_id: Filter to a specific trading account.
        strategy_id: Filter to a specific strategy.
        asset_class: Filter to a specific asset class.
        start_date: ISO 8601 lower bound on exit_date (inclusive).
        end_date: ISO 8601 upper bound on exit_date (inclusive).

    Returns:
        Dict with a ``strategies`` key containing a list of dicts, each with
        ``strategy_id``, ``strategy_name``, ``total``, ``wins``, ``losses``,
        ``breakeven``, and ``win_rate`` (float, 0–100).  Sorted by total
        trades descending.

    Raises:
        ValueError: If date strings are invalid or start_date > end_date.
    """
    if start_date is not None:
        try:
            date.fromisoformat(start_date)
        except ValueError:
            raise ValueError("start_date must be a valid ISO 8601 date (YYYY-MM-DD)")
    if end_date is not None:
        try:
            date.fromisoformat(end_date)
        except ValueError:
            raise ValueError("end_date must be a valid ISO 8601 date (YYYY-MM-DD)")
    if start_date is not None and end_date is not None:
        if date.fromisoformat(start_date) > date.fromisoformat(end_date):
            raise ValueError("start_date must be on or before end_date")

    conditions = ["t.is_open = 0", "t.exit_date IS NOT NULL", "t.pnl_net IS NOT NULL"]
    params: list = []

    if account_id is not None:
        conditions.append("t.account_id = ?")
        params.append(account_id)
    if strategy_id is not None:
        conditions.append("t.strategy_id = ?")
        params.append(strategy_id)
    if asset_class is not None:
        conditions.append("t.asset_class = ?")
        params.append(asset_class)
    if start_date is not None:
        conditions.append("t.exit_date >= ?")
        params.append(start_date)
    if end_date is not None:
        conditions.append("t.exit_date <= ?")
        params.append(end_date)

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT
            t.strategy_id,
            COALESCE(s.name, 'No strategy') AS strategy_name,
            COUNT(*) AS total,
            SUM(CASE WHEN t.pnl_net > 0 THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN t.pnl_net < 0 THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN t.pnl_net = 0 THEN 1 ELSE 0 END) AS breakeven
        FROM trades t
        LEFT JOIN strategies s ON t.strategy_id = s.id
        WHERE {where_clause}
        GROUP BY t.strategy_id
        ORDER BY total DESC
    """  # noqa: S608 — where_clause built from literals only, no user data

    rows = db.execute(sql, params).fetchall()

    strategies = []
    for row in rows:
        total = row["total"]
        wins = row["wins"]
        win_rate = round(wins / total * 100, 1) if total > 0 else 0.0
        strategies.append({
            "strategy_id": row["strategy_id"],
            "strategy_name": row["strategy_name"],
            "total": total,
            "wins": wins,
            "losses": row["losses"],
            "breakeven": row["breakeven"],
            "win_rate": win_rate,
        })

    return {"strategies": strategies}


def get_discipline_scatter(
    db: sqlite3.Connection,
    *,
    account_id: Optional[int] = None,
    strategy_id: Optional[int] = None,
    asset_class: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """Per-trade discipline vs P&L scatter data for closed trades.

    Returns one data point per closed trade that has both ``pnl_net`` and
    ``rules_followed_pct`` set.  Monetary values are converted to decimal
    pounds before returning.

    Args:
        db: Active SQLite connection.
        account_id: Filter to a specific trading account.
        strategy_id: Filter to a specific strategy.
        asset_class: Filter to a specific asset class.
        start_date: ISO 8601 lower bound on exit_date (inclusive).
        end_date: ISO 8601 upper bound on exit_date (inclusive).

    Returns:
        Dict with a ``points`` key containing a list of dicts, each with
        ``x`` (rules_followed_pct float 0–100), ``y`` (pnl_net decimal £),
        ``symbol`` (str), ``exit_date`` (ISO 8601 str), and
        ``r_multiple`` (float or None).
        Also includes ``total`` (int) count of points returned.

    Raises:
        ValueError: If date strings are invalid or start_date > end_date.
    """
    if start_date is not None:
        try:
            date.fromisoformat(start_date)
        except ValueError:
            raise ValueError("start_date must be a valid ISO 8601 date (YYYY-MM-DD)")
    if end_date is not None:
        try:
            date.fromisoformat(end_date)
        except ValueError:
            raise ValueError("end_date must be a valid ISO 8601 date (YYYY-MM-DD)")
    if start_date is not None and end_date is not None:
        if date.fromisoformat(start_date) > date.fromisoformat(end_date):
            raise ValueError("start_date must be on or before end_date")

    conditions = [
        "is_open = 0",
        "exit_date IS NOT NULL",
        "pnl_net IS NOT NULL",
        "rules_followed_pct IS NOT NULL",
    ]
    params: list = []

    if account_id is not None:
        conditions.append("account_id = ?")
        params.append(account_id)
    if strategy_id is not None:
        conditions.append("strategy_id = ?")
        params.append(strategy_id)
    if asset_class is not None:
        conditions.append("asset_class = ?")
        params.append(asset_class)
    if start_date is not None:
        conditions.append("exit_date >= ?")
        params.append(start_date)
    if end_date is not None:
        conditions.append("exit_date <= ?")
        params.append(end_date)

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT
            rules_followed_pct,
            pnl_net,
            symbol,
            exit_date,
            r_multiple
        FROM trades
        WHERE {where_clause}
        ORDER BY exit_date ASC, id ASC
    """  # noqa: S608 — where_clause built from literals only, no user data

    rows = db.execute(sql, params).fetchall()

    points = [
        {
            "x": row["rules_followed_pct"],
            "y": _from_pence(row["pnl_net"]),
            "symbol": row["symbol"],
            "exit_date": row["exit_date"],
            "r_multiple": row["r_multiple"],
        }
        for row in rows
    ]

    return {"points": points, "total": len(points)}
