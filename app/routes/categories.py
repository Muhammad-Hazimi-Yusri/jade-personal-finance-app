"""Category API routes for Jade.

Blueprint registered at /api/categories.
Read-only endpoint used to populate filter dropdowns.
Full category management (create, edit, colour) is Phase 1.8.
"""

from flask import Blueprint, jsonify

from app.db import get_db

bp = Blueprint("categories", __name__, url_prefix="/api/categories")


@bp.get("/")
def list_categories():
    """List all categories ordered alphabetically by display name.

    Returns:
        JSON envelope with 'categories' array, each containing
        id, name, display_name, colour, icon, and is_default.
    """
    rows = get_db().execute(
        "SELECT id, name, display_name, colour, icon, is_default "
        "FROM categories ORDER BY display_name"
    ).fetchall()
    return jsonify({"categories": [dict(r) for r in rows]}), 200
