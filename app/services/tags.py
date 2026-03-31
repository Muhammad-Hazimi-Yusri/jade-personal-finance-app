"""Tag service layer for Jade.

All SQL queries and business logic for tags and trade-tag associations
live here. Route handlers call these functions and never access the
database directly.
"""

import sqlite3

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_GROUPS: frozenset[str] = frozenset({
    "general", "setup", "mistake", "pattern", "market",
})

_SELECT_COLS = "id, name, group_name"

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row)


def _validate_name(value: object) -> str:
    """Validate tag name — required, non-empty, max 50 chars.

    Raises:
        ValueError: If name is missing, blank, or too long.
    """
    if value is None:
        raise ValueError("name is required")
    name = str(value).strip()
    if not name:
        raise ValueError("name is required")
    if len(name) > 50:
        raise ValueError("name must be 50 characters or fewer")
    return name


def _validate_group(value: object) -> str:
    """Validate group_name — optional, must be a known group.

    Defaults to 'general' if not provided.

    Raises:
        ValueError: If the provided value is not in the valid set.
    """
    if value is None or str(value).strip() == "":
        return "general"
    group = str(value).strip().lower()
    if group not in _VALID_GROUPS:
        valid = ", ".join(sorted(_VALID_GROUPS))
        raise ValueError(f"group_name must be one of: {valid}")
    return group


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def list_tags(
    db: sqlite3.Connection,
    *,
    group_name: str | None = None,
) -> list[dict]:
    """Return all tags, optionally filtered by group, ordered by group then name.

    Args:
        group_name: If provided, return only tags in this group.

    Returns:
        List of tag dicts.
    """
    if group_name is not None:
        rows = db.execute(
            f"SELECT {_SELECT_COLS} FROM tags WHERE group_name = ? ORDER BY group_name, name",
            (group_name,),
        ).fetchall()
    else:
        rows = db.execute(
            f"SELECT {_SELECT_COLS} FROM tags ORDER BY group_name, name"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_tag(db: sqlite3.Connection, tag_id: int) -> dict | None:
    """Return a single tag by ID, or None if not found."""
    row = db.execute(
        f"SELECT {_SELECT_COLS} FROM tags WHERE id = ?",
        (tag_id,),
    ).fetchone()
    return _row_to_dict(row) if row else None


def create_tag(db: sqlite3.Connection, data: dict) -> dict:
    """Create a new tag.

    Required fields: name.
    Optional: group_name (default 'general').

    Returns:
        The newly created tag dict.

    Raises:
        ValueError: On validation failure or duplicate name.
    """
    name = _validate_name(data.get("name"))
    group_name = _validate_group(data.get("group_name"))

    try:
        cursor = db.execute(
            "INSERT INTO tags (name, group_name) VALUES (?, ?)",
            (name, group_name),
        )
    except sqlite3.IntegrityError:
        raise ValueError("tag name already exists")

    db.commit()
    return get_tag(db, cursor.lastrowid)


def delete_tag(db: sqlite3.Connection, tag_id: int) -> bool:
    """Delete a tag. Cascades to trade_tags via FK.

    Returns:
        True if the tag was deleted, False if not found.
    """
    existing = get_tag(db, tag_id)
    if existing is None:
        return False

    db.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    db.commit()
    return True


def get_tags_for_trade(db: sqlite3.Connection, trade_id: int) -> list[dict]:
    """Return all tags attached to a trade, ordered by group then name.

    Returns:
        List of tag dicts.
    """
    rows = db.execute(
        f"""
        SELECT {_SELECT_COLS}
        FROM tags
        JOIN trade_tags ON tags.id = trade_tags.tag_id
        WHERE trade_tags.trade_id = ?
        ORDER BY tags.group_name, tags.name
        """,
        (trade_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def add_tags_to_trade(
    db: sqlite3.Connection,
    trade_id: int,
    tag_ids: list[int],
) -> list[dict]:
    """Attach one or more tags to a trade. Already-attached tags are silently ignored.

    Args:
        trade_id: The trade to tag.
        tag_ids: List of tag IDs to attach.

    Returns:
        The full updated tag list for the trade.

    Raises:
        ValueError: If any tag_id does not exist.
    """
    for tag_id in tag_ids:
        if get_tag(db, tag_id) is None:
            raise ValueError(f"tag {tag_id} not found")

    for tag_id in tag_ids:
        db.execute(
            "INSERT OR IGNORE INTO trade_tags (trade_id, tag_id) VALUES (?, ?)",
            (trade_id, tag_id),
        )

    db.commit()
    return get_tags_for_trade(db, trade_id)


def remove_tag_from_trade(
    db: sqlite3.Connection,
    trade_id: int,
    tag_id: int,
) -> bool:
    """Remove a single tag from a trade.

    Returns:
        True if the association existed and was removed, False otherwise.
    """
    cursor = db.execute(
        "DELETE FROM trade_tags WHERE trade_id = ? AND tag_id = ?",
        (trade_id, tag_id),
    )
    db.commit()
    return cursor.rowcount > 0
