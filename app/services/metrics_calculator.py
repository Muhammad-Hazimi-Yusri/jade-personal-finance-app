"""Aggregate trading metrics for Jade.

Pure functions operating on lists of trade dicts (already filtered to closed
trades by the DB query).  All monetary values are integer pence throughout
these functions; only the public ``get_trading_performance`` orchestrator
converts to decimal via ``_from_pence`` before returning.

These are pure functions with no side effects and no database access.
``get_trading_performance`` is the only function that touches the DB.
"""

import sqlite3
from datetime import date
from typing import Optional


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _from_pence(pence: int) -> float:
    """Convert integer pence to a decimal float for API responses."""
    return round(pence / 100, 2)


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
