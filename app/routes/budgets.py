"""Budget API routes for Jade.

Blueprint registered at /api/budgets.
All business logic is delegated to app.services.budgets.
"""

from flask import Blueprint, jsonify, request

from app.db import get_db
from app.services import budgets as budget_service

bp = Blueprint("budgets", __name__, url_prefix="/api/budgets")


@bp.get("/")
def list_budgets():
    """List all budgets.

    Query params:
        active_only (str): '1' to return only active budgets.

    Returns:
        JSON envelope with 'budgets' array.
    """
    active_only = request.args.get("active_only", "0") == "1"
    budgets = budget_service.list_budgets(get_db(), active_only=active_only)
    return jsonify({"budgets": budgets}), 200


@bp.get("/status")
def budget_status():
    """Get current-period budget status with spending totals.

    Query params:
        period (str): 'monthly' (default) or 'weekly'.

    Returns:
        JSON envelope with 'status' array containing budget_amount,
        spent, remaining, and percentage for each active budget.
    """
    period = request.args.get("period", "monthly")
    try:
        status = budget_service.get_budget_status(get_db(), period=period)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    return jsonify({"status": status}), 200


@bp.get("/<int:budget_id>")
def get_budget(budget_id: int):
    """Get a single budget by ID.

    Returns:
        JSON budget object, or 404 if not found.
    """
    result = budget_service.get_budget(get_db(), budget_id)
    if result is None:
        return jsonify({"error": "Budget not found"}), 404
    return jsonify(result), 200


@bp.post("/")
def create_budget():
    """Create a new budget.

    Request body (JSON):
        category (str, required): Category name (FK to categories.name).
        amount (number, required): Budget limit in pounds (e.g. 250.00).
        period (str, optional): 'monthly' (default) or 'weekly'.
        start_date (str, optional): ISO 8601 date.

    Returns:
        201 with the created budget, or 422 on validation error.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    try:
        result = budget_service.create_budget(get_db(), data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    return jsonify(result), 201


@bp.put("/<int:budget_id>")
def update_budget(budget_id: int):
    """Update an existing budget.

    Returns:
        200 with the updated budget, 404 if not found, 422 on error.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    try:
        result = budget_service.update_budget(get_db(), budget_id, data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    if result is None:
        return jsonify({"error": "Budget not found"}), 404
    return jsonify(result), 200


@bp.delete("/<int:budget_id>")
def delete_budget(budget_id: int):
    """Delete a budget.

    Returns:
        204 No Content on success, 404 if not found.
    """
    deleted = budget_service.delete_budget(get_db(), budget_id)
    if not deleted:
        return jsonify({"error": "Budget not found"}), 404
    return "", 204


@bp.post("/<int:budget_id>/toggle")
def toggle_budget(budget_id: int):
    """Toggle a budget's active/inactive state.

    Returns:
        200 with the updated budget, 404 if not found.
    """
    result = budget_service.toggle_budget(get_db(), budget_id)
    if result is None:
        return jsonify({"error": "Budget not found"}), 404
    return jsonify(result), 200
