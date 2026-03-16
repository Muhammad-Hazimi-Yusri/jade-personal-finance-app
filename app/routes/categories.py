"""Category API routes for Jade.

Blueprint registered at /api/categories.
All business logic is delegated to app.services.categories.
"""

from flask import Blueprint, jsonify, request

from app.db import get_db
from app.services import categories as cat_service

bp = Blueprint("categories", __name__, url_prefix="/api/categories")


@bp.get("/")
def list_categories():
    """List all categories ordered by sort_order then label.

    Returns:
        JSON envelope with 'categories' array, each containing
        id, name, display_name, colour, icon, is_default, and sort_order.
    """
    categories = cat_service.list_categories(get_db())
    return jsonify({"categories": categories}), 200


@bp.get("/<int:category_id>")
def get_category(category_id: int):
    """Get a single category by ID.

    Args:
        category_id: Primary key of the category.

    Returns:
        JSON category object, or 404 if not found.
    """
    result = cat_service.get_category(get_db(), category_id)
    if result is None:
        return jsonify({"error": "Category not found"}), 404
    return jsonify(result), 200


@bp.post("/")
def create_category():
    """Create a new custom category.

    Request body (JSON):
        label (str, required): Display name (e.g. "Subscriptions").
        colour (str, optional): Hex colour, default '#6B7280'.
        icon (str, optional): Emoji or icon character.
        sort_order (int, optional): Display order, auto-assigned if omitted.

    The ``name`` field is auto-generated from the label as snake_case.

    Returns:
        201 with the created category, or 422 on validation error.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    try:
        result = cat_service.create_category(get_db(), data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    return jsonify(result), 201


@bp.put("/<int:category_id>")
def update_category(category_id: int):
    """Update an existing category.

    Only label, colour, icon, and sort_order may be changed.
    The name field is immutable.

    Args:
        category_id: Primary key of the category to update.

    Returns:
        200 with the updated category, 404 if not found, 422 on error.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    try:
        result = cat_service.update_category(get_db(), category_id, data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    if result is None:
        return jsonify({"error": "Category not found"}), 404
    return jsonify(result), 200


@bp.delete("/<int:category_id>")
def delete_category(category_id: int):
    """Delete a custom category.

    Default categories cannot be deleted.
    Categories in use by transactions cannot be deleted.

    Args:
        category_id: Primary key of the category to delete.

    Returns:
        204 No Content on success, 404 if not found, 409 if protected.
    """
    try:
        deleted = cat_service.delete_category(get_db(), category_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    if not deleted:
        return jsonify({"error": "Category not found"}), 404
    return "", 204
