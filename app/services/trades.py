"""Trade service layer for Jade.

All SQL queries and business logic for trades live here.
Route handlers call these functions and never access the database directly.

Money convention: price/fee/P&L fields are stored as integer pence in the
database. This module converts inbound decimals to pence (× 100) and outbound
pence back to decimals (/ 100) so the rest of the app only sees decimals.
"""

import math
import sqlite3
from decimal import Decimal, ROUND_HALF_UP

from app.services.tags import get_tags_for_trade

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Fields stored as integer pence — converted on read/write.
_PENCE_FIELDS: frozenset[str] = frozenset({
    "entry_price", "exit_price", "entry_fee", "exit_fee",
    "stop_loss", "take_profit", "risk_amount",
    "pnl", "pnl_net", "mae", "mfe", "strike_price",
})

_VALID_ASSET_CLASSES: frozenset[str] = frozenset({
    "stocks", "forex", "crypto", "options",
})
_VALID_DIRECTIONS: frozenset[str] = frozenset({"long", "short"})
_VALID_TRADE_TYPES: frozenset[str] = frozenset({
    "trade", "dividend", "fee", "interest", "deposit", "withdrawal",
})
_VALID_OPTION_TYPES: frozenset[str] = frozenset({"call", "put"})
_VALID_TIMEFRAMES: frozenset[str] = frozenset({
    "1m", "5m", "15m", "1h", "4h", "D", "W",
})
_VALID_MARKET_CONDITIONS: frozenset[str] = frozenset({
    "trending", "ranging", "volatile", "choppy",
})

_REQUIRED_FIELDS: tuple[str, ...] = (
    "account_id", "symbol", "asset_class", "direction",
    "entry_date", "entry_price", "position_size",
)

_UPDATABLE_FIELDS: frozenset[str] = frozenset({
    "symbol", "asset_class", "direction",
    "entry_date", "entry_price", "position_size", "entry_fee",
    "exit_date", "exit_price", "exit_fee",
    "stop_loss", "take_profit", "risk_amount",
    "pnl", "pnl_net", "pnl_percentage", "r_multiple",
    "mae", "mfe", "mae_percentage", "mfe_percentage", "duration_minutes",
    "strategy_id", "timeframe", "setup_type", "market_condition",
    "entry_reason", "exit_reason", "confidence",
    "emotion_before", "emotion_during", "emotion_after",
    "rules_followed_pct", "psychology_notes", "post_trade_review",
    "option_type", "strike_price", "expiry_date", "implied_volatility",
    "trade_type", "notes", "screenshot_path", "is_open",
})

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _to_pence(value: object) -> int:
    """Convert a decimal monetary value to integer pence.

    Uses Decimal for exact arithmetic to avoid float rounding issues.

    Raises:
        ValueError: If value cannot be converted to a number.
    """
    try:
        d = Decimal(str(value))
    except Exception:
        raise ValueError(f"Invalid monetary value: {value!r}")
    return int((d * 100).to_integral_value(rounding=ROUND_HALF_UP))


def _from_pence(pence: int) -> float:
    """Convert integer pence to a decimal float for API responses."""
    return round(pence / 100, 2)


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict, converting pence fields to decimal."""
    d = dict(row)
    for field in _PENCE_FIELDS:
        if d.get(field) is not None:
            d[field] = _from_pence(d[field])
    return d


def _validate_create(data: dict) -> None:
    """Validate all required fields and enum values for a new trade.

    Raises:
        ValueError: On any validation failure.
    """
    for field in _REQUIRED_FIELDS:
        if data.get(field) is None:
            raise ValueError(f"{field} is required")

    _validate_enum("asset_class", data["asset_class"], _VALID_ASSET_CLASSES)
    _validate_enum("direction", data["direction"], _VALID_DIRECTIONS)

    if data.get("trade_type") is not None:
        _validate_enum("trade_type", data["trade_type"], _VALID_TRADE_TYPES)
    if data.get("option_type") is not None:
        _validate_enum("option_type", data["option_type"], _VALID_OPTION_TYPES)
    if data.get("timeframe") is not None:
        _validate_enum("timeframe", data["timeframe"], _VALID_TIMEFRAMES)
    if data.get("market_condition") is not None:
        _validate_enum("market_condition", data["market_condition"], _VALID_MARKET_CONDITIONS)

    _validate_optional_range("confidence", data.get("confidence"), 1, 10)
    _validate_optional_range("emotion_before", data.get("emotion_before"), 1, 5)
    _validate_optional_range("emotion_during", data.get("emotion_during"), 1, 5)
    _validate_optional_range("emotion_after", data.get("emotion_after"), 1, 5)
    _validate_optional_range("rules_followed_pct", data.get("rules_followed_pct"), 0, 100)


def _validate_update(data: dict) -> None:
    """Validate enum and range fields present in an update payload.

    Raises:
        ValueError: On any validation failure.
    """
    if "asset_class" in data:
        _validate_enum("asset_class", data["asset_class"], _VALID_ASSET_CLASSES)
    if "direction" in data:
        _validate_enum("direction", data["direction"], _VALID_DIRECTIONS)
    if "trade_type" in data:
        _validate_enum("trade_type", data["trade_type"], _VALID_TRADE_TYPES)
    if "option_type" in data:
        _validate_enum("option_type", data["option_type"], _VALID_OPTION_TYPES)
    if "timeframe" in data:
        _validate_enum("timeframe", data["timeframe"], _VALID_TIMEFRAMES)
    if "market_condition" in data:
        _validate_enum("market_condition", data["market_condition"], _VALID_MARKET_CONDITIONS)

    if "confidence" in data:
        _validate_optional_range("confidence", data["confidence"], 1, 10)
    if "emotion_before" in data:
        _validate_optional_range("emotion_before", data["emotion_before"], 1, 5)
    if "emotion_during" in data:
        _validate_optional_range("emotion_during", data["emotion_during"], 1, 5)
    if "emotion_after" in data:
        _validate_optional_range("emotion_after", data["emotion_after"], 1, 5)
    if "rules_followed_pct" in data:
        _validate_optional_range("rules_followed_pct", data["rules_followed_pct"], 0, 100)


def _validate_enum(field: str, value: object, valid_set: frozenset[str]) -> str:
    """Validate a field against a set of allowed string values.

    Raises:
        ValueError: If value is not in the valid set.
    """
    v = str(value).strip().lower()
    if v not in valid_set:
        raise ValueError(
            f"{field} must be one of: {', '.join(sorted(valid_set))}"
        )
    return v


def _validate_optional_range(
    field: str,
    value: object,
    min_val: float,
    max_val: float,
) -> None:
    """Validate a numeric field is within [min_val, max_val], if provided.

    Raises:
        ValueError: If value is non-numeric or out of range.
    """
    if value is None:
        return
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a number")
    if not (min_val <= num <= max_val):
        raise ValueError(f"{field} must be between {min_val} and {max_val}")


def _build_insert(data: dict) -> tuple[str, list]:
    """Build INSERT column list and values for a new trade.

    Pence fields are converted ×100. Returns (columns_sql, values_list).
    """
    cols: list[str] = []
    vals: list[object] = []

    # Required fields
    cols += ["account_id", "symbol", "asset_class", "direction",
             "entry_date", "entry_price", "position_size"]
    vals += [
        int(data["account_id"]),
        str(data["symbol"]).strip().upper(),
        str(data["asset_class"]).strip().lower(),
        str(data["direction"]).strip().lower(),
        str(data["entry_date"]).strip(),
        _to_pence(data["entry_price"]),
        float(data["position_size"]),
    ]

    # Optional fields
    _optional_int(data, "entry_fee", cols, vals, pence=True)
    _optional_str(data, "exit_date", cols, vals)
    _optional_int(data, "exit_price", cols, vals, pence=True)
    _optional_int(data, "exit_fee", cols, vals, pence=True)
    _optional_int(data, "stop_loss", cols, vals, pence=True)
    _optional_int(data, "take_profit", cols, vals, pence=True)
    _optional_int(data, "risk_amount", cols, vals, pence=True)
    _optional_int(data, "pnl", cols, vals, pence=True)
    _optional_int(data, "pnl_net", cols, vals, pence=True)
    _optional_float(data, "pnl_percentage", cols, vals)
    _optional_float(data, "r_multiple", cols, vals)
    _optional_int(data, "mae", cols, vals, pence=True)
    _optional_int(data, "mfe", cols, vals, pence=True)
    _optional_float(data, "mae_percentage", cols, vals)
    _optional_float(data, "mfe_percentage", cols, vals)
    _optional_int(data, "duration_minutes", cols, vals)
    _optional_int(data, "strategy_id", cols, vals)
    _optional_str(data, "timeframe", cols, vals)
    _optional_str(data, "setup_type", cols, vals)
    _optional_str(data, "market_condition", cols, vals)
    _optional_str(data, "entry_reason", cols, vals)
    _optional_str(data, "exit_reason", cols, vals)
    _optional_int(data, "confidence", cols, vals)
    _optional_int(data, "emotion_before", cols, vals)
    _optional_int(data, "emotion_during", cols, vals)
    _optional_int(data, "emotion_after", cols, vals)
    _optional_float(data, "rules_followed_pct", cols, vals)
    _optional_str(data, "psychology_notes", cols, vals)
    _optional_str(data, "post_trade_review", cols, vals)
    _optional_str(data, "option_type", cols, vals)
    _optional_int(data, "strike_price", cols, vals, pence=True)
    _optional_str(data, "expiry_date", cols, vals)
    _optional_float(data, "implied_volatility", cols, vals)
    _optional_str(data, "trade_type", cols, vals)
    _optional_str(data, "notes", cols, vals)
    _optional_str(data, "screenshot_path", cols, vals)

    if data.get("is_open") is not None:
        cols.append("is_open")
        vals.append(1 if data["is_open"] else 0)

    col_sql = ", ".join(cols)
    placeholders = ", ".join(["?"] * len(cols))
    return f"({col_sql}) VALUES ({placeholders})", vals


def _optional_str(data: dict, key: str, cols: list, vals: list) -> None:
    if data.get(key) is not None:
        cols.append(key)
        vals.append(str(data[key]).strip() or None)


def _optional_int(
    data: dict,
    key: str,
    cols: list,
    vals: list,
    pence: bool = False,
) -> None:
    if data.get(key) is not None:
        cols.append(key)
        vals.append(_to_pence(data[key]) if pence else int(data[key]))


def _optional_float(data: dict, key: str, cols: list, vals: list) -> None:
    if data.get(key) is not None:
        cols.append(key)
        vals.append(float(data[key]))


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def list_trades(db: sqlite3.Connection, filters: dict) -> dict:
    """Return a paginated, filtered list of trades.

    Supported filter keys: account_id, asset_class, symbol, strategy_id,
    is_open, direction, start_date, end_date, page, per_page.

    Returns:
        Dict with keys: trades, total, page, per_page, pages.
    """
    page = max(1, int(filters.get("page") or 1))
    per_page = min(200, max(1, int(filters.get("per_page") or 50)))

    conditions: list[str] = []
    params: list[object] = []

    if filters.get("account_id") is not None:
        conditions.append("t.account_id = ?")
        params.append(int(filters["account_id"]))
    if filters.get("asset_class") is not None:
        conditions.append("t.asset_class = ?")
        params.append(str(filters["asset_class"]).lower())
    if filters.get("symbol") is not None:
        conditions.append("t.symbol = ?")
        params.append(str(filters["symbol"]).upper())
    if filters.get("strategy_id") is not None:
        conditions.append("t.strategy_id = ?")
        params.append(int(filters["strategy_id"]))
    if filters.get("is_open") is not None:
        conditions.append("t.is_open = ?")
        params.append(1 if str(filters["is_open"]) in ("1", "true", "True") else 0)
    if filters.get("direction") is not None:
        conditions.append("t.direction = ?")
        params.append(str(filters["direction"]).lower())
    if filters.get("start_date") is not None:
        conditions.append("t.entry_date >= ?")
        params.append(str(filters["start_date"]))
    if filters.get("end_date") is not None:
        conditions.append("t.entry_date <= ?")
        params.append(str(filters["end_date"]))

    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    total: int = db.execute(
        f"SELECT COUNT(*) FROM trades t {where_sql}", params
    ).fetchone()[0]

    offset = (page - 1) * per_page
    rows = db.execute(
        f"SELECT t.* FROM trades t {where_sql} ORDER BY t.entry_date DESC, t.id DESC LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()

    trades = [_row_to_dict(r) for r in rows]
    # Attach tags to each trade
    for trade in trades:
        trade["tags"] = get_tags_for_trade(db, trade["id"])

    pages = math.ceil(total / per_page) if total > 0 else 1

    return {
        "trades": trades,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


def get_trade(db: sqlite3.Connection, trade_id: int) -> dict | None:
    """Return a single trade by ID with its tags, or None if not found."""
    row = db.execute(
        "SELECT * FROM trades WHERE id = ?",
        (trade_id,),
    ).fetchone()
    if row is None:
        return None
    trade = _row_to_dict(row)
    trade["tags"] = get_tags_for_trade(db, trade_id)
    return trade


def create_trade(db: sqlite3.Connection, data: dict) -> dict:
    """Create a new trade.

    Required fields: account_id, symbol, asset_class, direction,
    entry_date, entry_price, position_size.

    Returns:
        The newly created trade dict with tags.

    Raises:
        ValueError: On validation failure.
    """
    _validate_create(data)

    col_vals_sql, vals = _build_insert(data)
    cursor = db.execute(
        f"INSERT INTO trades {col_vals_sql}",
        vals,
    )
    db.commit()
    return get_trade(db, cursor.lastrowid)


def update_trade(
    db: sqlite3.Connection,
    trade_id: int,
    data: dict,
) -> dict | None:
    """Update an existing trade (partial update).

    Returns:
        The updated trade dict, or None if the ID does not exist.

    Raises:
        ValueError: On validation failure.
    """
    existing = get_trade(db, trade_id)
    if existing is None:
        return None

    _validate_update(data)

    updates: dict[str, object] = {}

    for field in _UPDATABLE_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if field in _PENCE_FIELDS:
            updates[field] = _to_pence(value) if value is not None else None
        elif field == "is_open":
            updates[field] = 1 if value else 0
        elif field == "asset_class":
            updates[field] = str(value).strip().lower()
        elif field == "direction":
            updates[field] = str(value).strip().lower()
        elif field == "trade_type":
            updates[field] = str(value).strip().lower()
        elif field == "option_type":
            updates[field] = str(value).strip().lower() if value is not None else None
        elif field == "timeframe":
            updates[field] = str(value).strip() if value is not None else None
        elif field == "market_condition":
            updates[field] = str(value).strip().lower() if value is not None else None
        elif field == "symbol":
            updates[field] = str(value).strip().upper()
        elif field in {"position_size", "pnl_percentage", "r_multiple",
                       "mae_percentage", "mfe_percentage", "implied_volatility",
                       "rules_followed_pct"}:
            updates[field] = float(value) if value is not None else None
        elif field in {"account_id", "strategy_id", "confidence", "emotion_before",
                       "emotion_during", "emotion_after", "duration_minutes"}:
            updates[field] = int(value) if value is not None else None
        else:
            updates[field] = value

    if not updates:
        return existing

    set_fragments = [f"{field} = ?" for field in updates]
    set_fragments.append("updated_at = datetime('now')")
    set_clause = ", ".join(set_fragments)

    db.execute(
        f"UPDATE trades SET {set_clause} WHERE id = ?",
        [*updates.values(), trade_id],
    )
    db.commit()
    return get_trade(db, trade_id)


def delete_trade(db: sqlite3.Connection, trade_id: int) -> bool:
    """Delete a trade and its tag associations.

    Returns:
        True if the trade was deleted, False if not found.
    """
    existing = get_trade(db, trade_id)
    if existing is None:
        return False

    db.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    db.commit()
    return True


def close_trade(
    db: sqlite3.Connection,
    trade_id: int,
    data: dict,
) -> dict | None:
    """Close an open trade by recording exit details.

    Sets exit_date, exit_price, exit_fee, and is_open = 0.
    P&L calculation is deferred to phase 4.9 (trade_calculator.py).

    Args:
        trade_id: The trade to close.
        data: Dict with exit_date (required), exit_price (required),
              exit_fee (optional).

    Returns:
        The updated trade dict, or None if not found.

    Raises:
        ValueError: If the trade is already closed, or if required exit
                    fields are missing.
    """
    existing = get_trade(db, trade_id)
    if existing is None:
        return None
    if not existing["is_open"]:
        raise ValueError("Trade is already closed")

    if data.get("exit_date") is None:
        raise ValueError("exit_date is required to close a trade")
    if data.get("exit_price") is None:
        raise ValueError("exit_price is required to close a trade")

    exit_fee = _to_pence(data["exit_fee"]) if data.get("exit_fee") is not None else 0

    db.execute(
        """
        UPDATE trades
        SET exit_date = ?,
            exit_price = ?,
            exit_fee = ?,
            is_open = 0,
            updated_at = datetime('now')
        WHERE id = ?
        """,
        (
            str(data["exit_date"]).strip(),
            _to_pence(data["exit_price"]),
            exit_fee,
            trade_id,
        ),
    )
    db.commit()
    return get_trade(db, trade_id)
