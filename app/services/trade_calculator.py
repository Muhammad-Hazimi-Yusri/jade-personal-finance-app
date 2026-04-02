"""Per-trade calculation functions for Jade.

All monetary inputs and outputs are integer pence (int).  No float is
used for money — arithmetic stays in pence and only the final division
for percentage/ratio results returns a float.

These are pure functions with no side effects and no database access.
They are called by ``app.services.trades.close_trade`` and may be
reused by future analytics modules.
"""

from datetime import datetime
from typing import Optional


def calculate_gross_pnl(
    entry_price_pence: int,
    exit_price_pence: int,
    position_size: float,
    direction: str,
) -> int:
    """Calculate gross P&L for a closed trade.

    Formula (README §Trading Journal):
        (exit_price - entry_price) × position_size × direction_multiplier

    Direction multiplier is 1 for "long", -1 for "short".

    Args:
        entry_price_pence: Entry price in integer pence.
        exit_price_pence:  Exit price in integer pence.
        position_size:     Number of units/contracts held.
        direction:         "long" or "short" (case-insensitive).

    Returns:
        Gross P&L as integer pence.  Positive means profit.

    Raises:
        ValueError: If direction is not "long" or "short".
    """
    d = direction.strip().lower()
    if d == "long":
        return int(round((exit_price_pence - entry_price_pence) * position_size))
    elif d == "short":
        return int(round((entry_price_pence - exit_price_pence) * position_size))
    else:
        raise ValueError(f"direction must be 'long' or 'short', got: {direction!r}")


def calculate_net_pnl(
    gross_pnl_pence: int,
    entry_fee_pence: int,
    exit_fee_pence: int,
) -> int:
    """Calculate net P&L by deducting total fees from gross P&L.

    Formula:
        pnl_net = pnl_gross - entry_fee - exit_fee

    Args:
        gross_pnl_pence:  Gross P&L in integer pence.
        entry_fee_pence:  Entry commission/fee in integer pence (0 if none).
        exit_fee_pence:   Exit commission/fee in integer pence (0 if none).

    Returns:
        Net P&L as integer pence.
    """
    return gross_pnl_pence - entry_fee_pence - exit_fee_pence


def calculate_pnl_percentage(
    net_pnl_pence: int,
    entry_price_pence: int,
    position_size: float,
) -> Optional[float]:
    """Calculate P&L as a percentage of the notional entry cost.

    Formula (README §Trading Journal):
        pnl_net / (entry_price × position_size) × 100

    Uses pnl_net (not gross) — this corrects the bug in the previous
    inline implementation which mistakenly used gross_pnl.

    Args:
        net_pnl_pence:     Net P&L in integer pence.
        entry_price_pence: Entry price in integer pence.
        position_size:     Number of units/contracts held.

    Returns:
        Percentage as a float, or None if the notional value is zero
        (prevents division-by-zero).
    """  # noqa: E501
    notional = entry_price_pence * position_size
    if notional == 0:
        return None
    return (net_pnl_pence / notional) * 100


def calculate_r_multiple(
    net_pnl_pence: int,
    risk_amount_pence: Optional[int],
) -> Optional[float]:
    """Calculate the R-multiple for a trade.

    Formula:
        r_multiple = pnl_net / risk_amount

    Args:
        net_pnl_pence:     Net P&L in integer pence.
        risk_amount_pence: Pre-defined risk amount in integer pence,
                           or None if not set.

    Returns:
        R-multiple as a float, or None if risk_amount is None or zero.
    """
    if not risk_amount_pence:
        return None
    return net_pnl_pence / risk_amount_pence


def calculate_duration_minutes(
    entry_date: str,
    exit_date: str,
) -> Optional[int]:
    """Calculate trade duration in whole minutes.

    Formula:
        duration_minutes = (exit_datetime - entry_datetime).total_seconds() / 60

    Both strings must be valid ISO 8601 datetime strings (as stored in
    the trades table).

    Args:
        entry_date: ISO 8601 string for trade entry (e.g. "2025-01-15T09:30:00").
        exit_date:  ISO 8601 string for trade exit.

    Returns:
        Duration in whole minutes (truncated), or None if either date
        string cannot be parsed.
    """
    try:
        entry_dt = datetime.fromisoformat(str(entry_date).strip())
        exit_dt = datetime.fromisoformat(str(exit_date).strip())
        return int((exit_dt - entry_dt).total_seconds() / 60)
    except (ValueError, TypeError):
        return None
