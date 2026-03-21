"""Category rules API routes for Jade.

Blueprint registered at /api/category-rules.
All business logic is delegated to app.services.category_rules.
"""

from flask import Blueprint, jsonify, request

from app.db import get_db
from app.services import category_rules as rules_service

bp = Blueprint("category_rules", __name__, url_prefix="/api/category-rules")


@bp.get("/")
def list_rules():
    """List all category rules, ordered by priority DESC.

    Query parameters:
        active_only (str): Pass '1' to return only active rules.

    Returns:
        JSON envelope with 'rules' array.
    """
    active_only = request.args.get("active_only", "0") == "1"
    rules = rules_service.list_rules(get_db(), active_only=active_only)
    return jsonify({"rules": rules}), 200


@bp.get("/<int:rule_id>")
def get_rule(rule_id: int):
    """Get a single category rule by ID.

    Args:
        rule_id: Primary key of the rule.

    Returns:
        JSON rule object, or 404 if not found.
    """
    result = rules_service.get_rule(get_db(), rule_id)
    if result is None:
        return jsonify({"error": "Rule not found"}), 404
    return jsonify(result), 200


@bp.post("/")
def create_rule():
    """Create a new category rule.

    Request body (JSON):
        field (str, required): 'name', 'description', or 'notes'.
        operator (str, optional): 'contains' (default), 'equals', 'starts_with'.
        value (str, required): Match pattern (e.g. 'Tesco').
        category (str, required): Target category snake_case name.
        priority (int, optional): Higher = checked first (default: 0).
        source (str, optional): 'manual' (default) or 'learned'.

    Returns:
        201 with the created rule, or 422 on validation error.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    try:
        result = rules_service.create_rule(get_db(), data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    return jsonify(result), 201


@bp.put("/<int:rule_id>")
def update_rule(rule_id: int):
    """Update an existing category rule.

    Only field, operator, value, category, priority, and is_active
    may be changed.

    Args:
        rule_id: Primary key of the rule to update.

    Returns:
        200 with the updated rule, 404 if not found, 422 on error.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    try:
        result = rules_service.update_rule(get_db(), rule_id, data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    if result is None:
        return jsonify({"error": "Rule not found"}), 404
    return jsonify(result), 200


@bp.delete("/<int:rule_id>")
def delete_rule(rule_id: int):
    """Delete a category rule.

    Args:
        rule_id: Primary key of the rule to delete.

    Returns:
        204 No Content on success, 404 if not found.
    """
    deleted = rules_service.delete_rule(get_db(), rule_id)
    if not deleted:
        return jsonify({"error": "Rule not found"}), 404
    return "", 204


@bp.post("/<int:rule_id>/toggle")
def toggle_rule(rule_id: int):
    """Toggle a rule's active/inactive state.

    Args:
        rule_id: Primary key of the rule to toggle.

    Returns:
        200 with the updated rule, 404 if not found.
    """
    result = rules_service.toggle_rule(get_db(), rule_id)
    if result is None:
        return jsonify({"error": "Rule not found"}), 404
    return jsonify(result), 200
