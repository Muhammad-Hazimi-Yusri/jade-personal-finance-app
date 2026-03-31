"""Strategy service layer for Jade.

All SQL queries and business logic for trading strategies live here.
Route handlers call these functions and never access the database directly.
"""

import sqlite3

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SELECT_COLS = """
    id, name, description, rules, version, is_active, created_at
"""

_UPDATABLE_FIELDS: frozenset[str] = frozenset({
    "name", "description", "rules", "version", "is_active",
})

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row)


def _validate_name(value: object) -> str:
    """Validate strategy name — required, non-empty, max 100 chars.

    Raises:
        ValueError: If name is missing, blank, or too long.
    """
    if value is None:
        raise ValueError("name is required")
    name = str(value).strip()
    if not name:
        raise ValueError("name is required")
    if len(name) > 100:
        raise ValueError("name must be 100 characters or fewer")
    return name


def _validate_version(value: object) -> str:
    """Validate version string — optional, max 20 chars, defaults to '1.0'.

    Raises:
        ValueError: If provided value is too long.
    """
    if value is None or str(value).strip() == "":
        return "1.0"
    version = str(value).strip()
    if len(version) > 20:
        raise ValueError("version must be 20 characters or fewer")
    return version


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def list_strategies(
    db: sqlite3.Connection,
    *,
    active_only: bool = False,
) -> list[dict]:
    """Return all strategies, optionally filtered to active only.

    Returns:
        List of strategy dicts.
    """
    sql = f"SELECT {_SELECT_COLS} FROM strategies"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY name"
    rows = db.execute(sql).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_strategy(db: sqlite3.Connection, strategy_id: int) -> dict | None:
    """Return a single strategy by ID, or None if not found."""
    row = db.execute(
        f"SELECT {_SELECT_COLS} FROM strategies WHERE id = ?",
        (strategy_id,),
    ).fetchone()
    return _row_to_dict(row) if row else None


def create_strategy(db: sqlite3.Connection, data: dict) -> dict:
    """Create a new strategy.

    Required fields: name.
    Optional: description, rules, version (default '1.0').

    Returns:
        The newly created strategy dict.

    Raises:
        ValueError: On validation failure.
    """
    name = _validate_name(data.get("name"))
    version = _validate_version(data.get("version"))
    description = str(data["description"]).strip() if data.get("description") else None
    rules = str(data["rules"]).strip() if data.get("rules") else None

    cursor = db.execute(
        """
        INSERT INTO strategies (name, description, rules, version)
        VALUES (?, ?, ?, ?)
        """,
        (name, description, rules, version),
    )
    db.commit()
    return get_strategy(db, cursor.lastrowid)


def update_strategy(
    db: sqlite3.Connection,
    strategy_id: int,
    data: dict,
) -> dict | None:
    """Update an existing strategy (partial update).

    Returns:
        The updated strategy dict, or None if the ID does not exist.

    Raises:
        ValueError: On validation failure.
    """
    existing = get_strategy(db, strategy_id)
    if existing is None:
        return None

    updates: dict[str, object] = {}

    if "name" in data:
        updates["name"] = _validate_name(data["name"])
    if "version" in data:
        updates["version"] = _validate_version(data["version"])
    if "description" in data:
        updates["description"] = str(data["description"]).strip() if data["description"] else None
    if "rules" in data:
        updates["rules"] = str(data["rules"]).strip() if data["rules"] else None
    if "is_active" in data:
        updates["is_active"] = 1 if data["is_active"] else 0

    if not updates:
        return existing

    set_fragments = [f"{field} = ?" for field in updates]
    set_clause = ", ".join(set_fragments)

    db.execute(
        f"UPDATE strategies SET {set_clause} WHERE id = ?",
        [*updates.values(), strategy_id],
    )
    db.commit()
    return get_strategy(db, strategy_id)


def delete_strategy(db: sqlite3.Connection, strategy_id: int) -> bool:
    """Delete a strategy.

    Returns:
        True if the strategy was deleted, False if not found.
    """
    existing = get_strategy(db, strategy_id)
    if existing is None:
        return False

    db.execute("DELETE FROM strategies WHERE id = ?", (strategy_id,))
    db.commit()
    return True


def toggle_strategy(db: sqlite3.Connection, strategy_id: int) -> dict | None:
    """Toggle a strategy's is_active flag.

    Returns:
        The updated strategy dict, or None if not found.
    """
    existing = get_strategy(db, strategy_id)
    if existing is None:
        return None

    new_active = 0 if existing["is_active"] else 1
    db.execute(
        "UPDATE strategies SET is_active = ? WHERE id = ?",
        (new_active, strategy_id),
    )
    db.commit()
    return get_strategy(db, strategy_id)
