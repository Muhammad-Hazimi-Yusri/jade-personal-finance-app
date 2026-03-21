"""Category service layer for Jade.

All SQL queries and business logic for categories live here.
Route handlers call these functions and never access the database directly.

The database column is ``label`` but the API returns ``display_name``
for backward-compatibility with the frontend.  The alias is applied
inside ``_row_to_dict``.
"""

import re
import sqlite3

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SELECT_COLS = """
    id, name, label, colour, icon, is_default, sort_order
"""

_COLOUR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

_UPDATABLE_FIELDS: frozenset[str] = frozenset({
    "label", "colour", "icon", "sort_order",
})

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict.

    Renames ``label`` → ``display_name`` in the output so the API
    contract stays consistent with frontend expectations.
    """
    d = dict(row)
    d["display_name"] = d.pop("label")
    return d


def _validate_label(label: object) -> str:
    """Validate and return a stripped label string.

    Raises:
        ValueError: If label is missing, empty, or too long.
    """
    if label is None:
        raise ValueError("label is required")
    label = str(label).strip()
    if not label:
        raise ValueError("label is required")
    if len(label) > 50:
        raise ValueError("label must be 50 characters or fewer")
    return label


def _validate_colour(colour: object) -> str:
    """Validate a hex colour string.

    Raises:
        ValueError: If colour is not a valid ``#RRGGBB`` string.
    """
    if colour is None:
        raise ValueError("colour is required")
    colour = str(colour).strip()
    if not _COLOUR_RE.match(colour):
        raise ValueError("colour must be a valid hex colour (e.g. #FF5733)")
    return colour


def _slugify_label(label: str) -> str:
    """Convert a display label to a snake_case name.

    Example: ``"Eating Out"`` → ``"eating_out"``.
    """
    slug = label.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def list_categories(db: sqlite3.Connection) -> list[dict]:
    """Return all categories ordered by sort_order then label.

    Returns:
        List of category dicts with ``display_name`` (aliased from ``label``).
    """
    rows = db.execute(
        f"SELECT {_SELECT_COLS} FROM categories ORDER BY sort_order, label"
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_category(db: sqlite3.Connection, category_id: int) -> dict | None:
    """Return a single category by ID, or None if not found."""
    row = db.execute(
        f"SELECT {_SELECT_COLS} FROM categories WHERE id = ?",
        (category_id,),
    ).fetchone()
    return _row_to_dict(row) if row else None


def create_category(db: sqlite3.Connection, data: dict) -> dict:
    """Create a custom category.

    The ``name`` field is auto-generated from ``label``.  The caller
    supplies ``label``, ``colour``, and optionally ``icon``.

    Returns:
        The newly created category dict.

    Raises:
        ValueError: On validation failure or duplicate name.
    """
    label = _validate_label(data.get("label"))
    colour = _validate_colour(data.get("colour", "#6B7280"))
    icon = data.get("icon")
    if icon is not None:
        icon = str(icon).strip() or None
        if icon and len(icon) > 10:
            raise ValueError("icon must be 10 characters or fewer")

    name = _slugify_label(label)
    if not name:
        raise ValueError("label must contain at least one letter or digit")

    # Auto-assign sort_order after all existing categories
    sort_order = data.get("sort_order")
    if sort_order is None:
        max_order = db.execute(
            "SELECT COALESCE(MAX(sort_order), -1) FROM categories"
        ).fetchone()[0]
        sort_order = max_order + 1
    else:
        try:
            sort_order = int(sort_order)
        except (TypeError, ValueError):
            raise ValueError("sort_order must be an integer")

    try:
        cursor = db.execute(
            """
            INSERT INTO categories (name, label, colour, icon, is_default, sort_order)
            VALUES (?, ?, ?, ?, 0, ?)
            """,
            (name, label, colour, icon, sort_order),
        )
        db.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"A category with the name '{name}' already exists")

    return get_category(db, cursor.lastrowid)


def update_category(
    db: sqlite3.Connection,
    category_id: int,
    data: dict,
) -> dict | None:
    """Update an existing category.

    Only ``label``, ``colour``, ``icon``, and ``sort_order`` may be
    changed.  The ``name`` field is immutable.

    Returns:
        The updated category dict, or None if the ID does not exist.

    Raises:
        ValueError: On validation failure.
    """
    existing = get_category(db, category_id)
    if existing is None:
        return None

    updates: dict[str, object] = {}

    if "label" in data:
        updates["label"] = _validate_label(data["label"])
    if "colour" in data:
        updates["colour"] = _validate_colour(data["colour"])
    if "icon" in data:
        icon = data["icon"]
        if icon is not None:
            icon = str(icon).strip() or None
            if icon and len(icon) > 10:
                raise ValueError("icon must be 10 characters or fewer")
        updates["icon"] = icon
    if "sort_order" in data:
        try:
            updates["sort_order"] = int(data["sort_order"])
        except (TypeError, ValueError):
            raise ValueError("sort_order must be an integer")

    if not updates:
        return existing

    set_fragments = [f"{field} = ?" for field in updates]
    set_clause = ", ".join(set_fragments)

    db.execute(
        f"UPDATE categories SET {set_clause} WHERE id = ?",
        [*updates.values(), category_id],
    )
    db.commit()
    return get_category(db, category_id)


def delete_category(db: sqlite3.Connection, category_id: int) -> bool:
    """Delete a custom category.

    Default categories (``is_default = 1``) cannot be deleted.
    Categories that are in use by transactions cannot be deleted.

    Returns:
        True if the category was deleted.

    Raises:
        ValueError: If the category is a default or is in use.
    """
    existing = get_category(db, category_id)
    if existing is None:
        return False

    if existing["is_default"]:
        raise ValueError("Cannot delete a default category")

    # Check if any transactions reference this category
    tx_count = db.execute(
        "SELECT COUNT(*) FROM transactions WHERE category = ?",
        (existing["name"],),
    ).fetchone()[0]
    if tx_count > 0:
        raise ValueError(
            f"Cannot delete: {tx_count} transaction{'s' if tx_count != 1 else ''} "
            f"use this category. Reassign them first."
        )

    # Check if any category rules reference this category
    rule_count = db.execute(
        "SELECT COUNT(*) FROM category_rules WHERE category = ?",
        (existing["name"],),
    ).fetchone()[0]
    if rule_count > 0:
        raise ValueError(
            f"Cannot delete: {rule_count} category rule{'s' if rule_count != 1 else ''} "
            f"reference this category. Remove them first."
        )

    db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    db.commit()
    return True
