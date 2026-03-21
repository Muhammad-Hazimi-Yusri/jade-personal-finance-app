"""Category rules service layer for Jade.

All SQL queries and business logic for category rules live here.
Route handlers call these functions and never access the database directly.

Category rules implement a three-tier auto-categorisation strategy:

- **Tier 1 (Monzo defaults):** CSV ``Category`` column — handled by csv_parser.
- **Tier 2 (Manual keyword rules):** User-created rules that override Tier 1.
- **Tier 3 (Learned corrections):** Auto-created when a user manually changes
  a transaction's category.  Higher priority so they win over manual rules.

Resolution order: Tier 3 (learned, priority 100) → Tier 2 (manual, priority 0)
→ Tier 1 (Monzo default).
"""

import sqlite3

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SELECT_COLS = """
    id, field, operator, value, category, priority, is_active, source,
    created_at
"""

_VALID_FIELDS: frozenset[str] = frozenset({"name", "description", "notes"})

_VALID_OPERATORS: frozenset[str] = frozenset({
    "contains", "equals", "starts_with",
})

_VALID_SOURCES: frozenset[str] = frozenset({"manual", "learned"})

_UPDATABLE_FIELDS: frozenset[str] = frozenset({
    "field", "operator", "value", "category", "priority", "is_active",
})

_LEARNED_PRIORITY: int = 100

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row)


def _validate_field(field: object) -> str:
    """Validate and return a stripped field string.

    Raises:
        ValueError: If field is missing or not one of the allowed values.
    """
    if field is None:
        raise ValueError("field is required")
    val = str(field).strip()
    if val not in _VALID_FIELDS:
        raise ValueError(
            f"field must be one of: {', '.join(sorted(_VALID_FIELDS))}"
        )
    return val


def _validate_operator(operator: object) -> str:
    """Validate and return a stripped operator string.

    Raises:
        ValueError: If operator is not one of the allowed values.
    """
    if operator is None:
        return "contains"
    val = str(operator).strip()
    if val not in _VALID_OPERATORS:
        raise ValueError(
            f"operator must be one of: {', '.join(sorted(_VALID_OPERATORS))}"
        )
    return val


def _validate_value(value: object) -> str:
    """Validate and return a stripped match-pattern string.

    Raises:
        ValueError: If value is missing, empty, or too long.
    """
    if value is None:
        raise ValueError("value is required")
    val = str(value).strip()
    if not val:
        raise ValueError("value must be a non-empty string")
    if len(val) > 200:
        raise ValueError("value must be 200 characters or fewer")
    return val


def _validate_category(db: sqlite3.Connection, category: object) -> str:
    """Validate that a category name exists in the database.

    Raises:
        ValueError: If category is missing or does not exist.
    """
    if category is None:
        raise ValueError("category is required")
    val = str(category).strip()
    if not val:
        raise ValueError("category must be a non-empty string")
    row = db.execute(
        "SELECT 1 FROM categories WHERE name = ?", (val,)
    ).fetchone()
    if row is None:
        raise ValueError(f"category '{val}' does not exist")
    return val


def _validate_priority(priority: object) -> int:
    """Validate and return an integer priority.

    Raises:
        ValueError: If priority cannot be converted or is negative.
    """
    if priority is None:
        return 0
    try:
        val = int(priority)
    except (TypeError, ValueError):
        raise ValueError("priority must be an integer")
    if val < 0:
        raise ValueError("priority must be >= 0")
    return val


def _validate_source(source: object) -> str:
    """Validate and return a stripped source string.

    Raises:
        ValueError: If source is not one of the allowed values.
    """
    if source is None:
        return "manual"
    val = str(source).strip()
    if val not in _VALID_SOURCES:
        raise ValueError(
            f"source must be one of: {', '.join(sorted(_VALID_SOURCES))}"
        )
    return val


def _matches_rule(rule: dict, transaction: dict) -> bool:
    """Check whether a single rule matches a transaction.

    Matching is **case-insensitive** for all operators.

    Args:
        rule: Dict with ``field``, ``operator``, and ``value`` keys.
        transaction: Parsed transaction dict (keys: name, description, notes…).

    Returns:
        True if the rule matches the transaction.
    """
    tx_val = transaction.get(rule["field"])
    if not tx_val:
        return False

    tx_lower = str(tx_val).lower().strip()
    rule_lower = rule["value"].lower().strip()

    op = rule["operator"]
    if op == "contains":
        return rule_lower in tx_lower
    if op == "equals":
        return tx_lower == rule_lower
    if op == "starts_with":
        return tx_lower.startswith(rule_lower)
    return False


# ---------------------------------------------------------------------------
# Public CRUD
# ---------------------------------------------------------------------------


def list_rules(
    db: sqlite3.Connection,
    *,
    active_only: bool = False,
) -> list[dict]:
    """Return all category rules, ordered by priority DESC.

    Args:
        db: Open database connection.
        active_only: If True, return only rules with ``is_active = 1``.

    Returns:
        List of rule dicts.
    """
    sql = f"SELECT {_SELECT_COLS} FROM category_rules"
    params: list = []
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY priority DESC, created_at DESC"

    rows = db.execute(sql, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_rule(db: sqlite3.Connection, rule_id: int) -> dict | None:
    """Fetch a single category rule by ID.

    Returns:
        Rule dict, or None if not found.
    """
    row = db.execute(
        f"SELECT {_SELECT_COLS} FROM category_rules WHERE id = ?",
        (rule_id,),
    ).fetchone()
    return _row_to_dict(row) if row else None


def create_rule(db: sqlite3.Connection, data: dict) -> dict:
    """Create a new category rule.

    Args:
        db: Open database connection.
        data: Dict with keys: ``field`` (required), ``operator`` (default
            'contains'), ``value`` (required), ``category`` (required),
            ``priority`` (default 0), ``source`` (default 'manual').

    Returns:
        The newly created rule dict.

    Raises:
        ValueError: If validation fails.
    """
    field = _validate_field(data.get("field"))
    operator = _validate_operator(data.get("operator"))
    value = _validate_value(data.get("value"))
    category = _validate_category(db, data.get("category"))
    priority = _validate_priority(data.get("priority"))
    source = _validate_source(data.get("source"))

    cursor = db.execute(
        """INSERT INTO category_rules
               (field, operator, value, category, priority, source)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (field, operator, value, category, priority, source),
    )
    db.commit()
    return get_rule(db, cursor.lastrowid)  # type: ignore[return-value]


def update_rule(
    db: sqlite3.Connection,
    rule_id: int,
    data: dict,
) -> dict | None:
    """Update an existing category rule.

    Only fields present in *data* are updated.

    Returns:
        Updated rule dict, or None if the ID does not exist.

    Raises:
        ValueError: If any supplied field fails validation.
    """
    existing = get_rule(db, rule_id)
    if existing is None:
        return None

    updates: dict[str, object] = {}

    if "field" in data:
        updates["field"] = _validate_field(data["field"])
    if "operator" in data:
        updates["operator"] = _validate_operator(data["operator"])
    if "value" in data:
        updates["value"] = _validate_value(data["value"])
    if "category" in data:
        updates["category"] = _validate_category(db, data["category"])
    if "priority" in data:
        updates["priority"] = _validate_priority(data["priority"])
    if "is_active" in data:
        updates["is_active"] = 1 if data["is_active"] else 0

    if not updates:
        return existing

    set_fragments = [f"{field} = ?" for field in updates]
    set_clause = ", ".join(set_fragments)

    db.execute(
        f"UPDATE category_rules SET {set_clause} WHERE id = ?",
        [*updates.values(), rule_id],
    )
    db.commit()
    return get_rule(db, rule_id)


def delete_rule(db: sqlite3.Connection, rule_id: int) -> bool:
    """Delete a category rule by ID.

    Returns:
        True if the rule was deleted, False if not found.
    """
    existing = get_rule(db, rule_id)
    if existing is None:
        return False

    db.execute("DELETE FROM category_rules WHERE id = ?", (rule_id,))
    db.commit()
    return True


def toggle_rule(db: sqlite3.Connection, rule_id: int) -> dict | None:
    """Toggle a rule's ``is_active`` state.

    Returns:
        Updated rule dict, or None if the ID does not exist.
    """
    existing = get_rule(db, rule_id)
    if existing is None:
        return None

    new_val = 0 if existing["is_active"] else 1
    db.execute(
        "UPDATE category_rules SET is_active = ? WHERE id = ?",
        (new_val, rule_id),
    )
    db.commit()
    return get_rule(db, rule_id)


# ---------------------------------------------------------------------------
# Rules engine
# ---------------------------------------------------------------------------


def apply_rules(
    db: sqlite3.Connection,
    transactions: list[dict],
) -> tuple[list[dict], int]:
    """Apply active category rules to a list of parsed transactions.

    Iterates through rules in priority order (highest first).  The first
    matching rule wins — its category overrides the transaction's existing
    category.

    Args:
        db: Open database connection.
        transactions: List of parsed transaction dicts (from csv_parser).

    Returns:
        Tuple of (transactions, rules_applied_count).  The transactions
        list is mutated in-place for efficiency.
    """
    rules = list_rules(db, active_only=True)
    if not rules:
        return transactions, 0

    rules_applied_count = 0

    for tx in transactions:
        for rule in rules:
            if _matches_rule(rule, tx):
                tx["category"] = rule["category"]
                rules_applied_count += 1
                break

    return transactions, rules_applied_count


# ---------------------------------------------------------------------------
# Tier 3: Learned rules
# ---------------------------------------------------------------------------


def create_learned_rule(
    db: sqlite3.Connection,
    transaction_name: str,
    new_category: str,
) -> dict:
    """Create or update a learned rule for a transaction name.

    When a user manually changes a transaction's category, this function
    ensures future imports of the same merchant are auto-categorised.

    If a learned rule already exists for the same name (case-insensitive),
    its category is updated.  Otherwise a new rule is created with
    ``field='name'``, ``operator='equals'``, and ``priority=100``.

    Args:
        db: Open database connection.
        transaction_name: The transaction's ``name`` field.
        new_category: The new category to assign.

    Returns:
        The created or updated rule dict.
    """
    # Check for existing learned rule with same name
    existing = db.execute(
        """SELECT id FROM category_rules
           WHERE field = 'name'
             AND operator = 'equals'
             AND LOWER(value) = LOWER(?)
             AND source = 'learned'""",
        (transaction_name,),
    ).fetchone()

    if existing:
        return update_rule(db, existing[0], {"category": new_category})  # type: ignore[return-value]

    return create_rule(db, {
        "field": "name",
        "operator": "equals",
        "value": transaction_name,
        "category": new_category,
        "priority": _LEARNED_PRIORITY,
        "source": "learned",
    })
