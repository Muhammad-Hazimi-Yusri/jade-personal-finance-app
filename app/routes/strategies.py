"""Strategy API routes for Jade.

Blueprint registered at /api/strategies.
All business logic is delegated to app.services.strategies.
"""

from flask import Blueprint, jsonify, request

from app.db import get_db
from app.services import strategies as strategy_service

bp = Blueprint("strategies", __name__, url_prefix="/api/strategies")


@bp.get("/")
def list_strategies():
    """List all strategies.

    Query params:
        active_only (str): '1' to return only active strategies.

    Returns:
        JSON envelope with 'strategies' array.
    """
    active_only = request.args.get("active_only", "0") == "1"
    strategies = strategy_service.list_strategies(get_db(), active_only=active_only)
    return jsonify({"strategies": strategies}), 200


@bp.get("/<int:strategy_id>")
def get_strategy(strategy_id: int):
    """Get a single strategy by ID.

    Returns:
        JSON strategy object, or 404 if not found.
    """
    result = strategy_service.get_strategy(get_db(), strategy_id)
    if result is None:
        return jsonify({"error": "Strategy not found"}), 404
    return jsonify({"strategy": result}), 200


@bp.post("/")
def create_strategy():
    """Create a new strategy.

    Request body (JSON):
        name (str, required): Strategy display name.
        description (str, optional): Short description.
        rules (str, optional): Entry rules / checklist text.
        version (str, optional): Version label, defaults to '1.0'.

    Returns:
        201 with the created strategy, or 422 on validation error.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    try:
        result = strategy_service.create_strategy(get_db(), data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    return jsonify({"strategy": result}), 201


@bp.put("/<int:strategy_id>")
def update_strategy(strategy_id: int):
    """Update an existing strategy.

    Returns:
        200 with the updated strategy, 404 if not found, 422 on error.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    try:
        result = strategy_service.update_strategy(get_db(), strategy_id, data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    if result is None:
        return jsonify({"error": "Strategy not found"}), 404
    return jsonify({"strategy": result}), 200


@bp.delete("/<int:strategy_id>")
def delete_strategy(strategy_id: int):
    """Delete a strategy.

    Returns:
        204 No Content on success, 404 if not found.
    """
    deleted = strategy_service.delete_strategy(get_db(), strategy_id)
    if not deleted:
        return jsonify({"error": "Strategy not found"}), 404
    return "", 204


@bp.post("/<int:strategy_id>/toggle")
def toggle_strategy(strategy_id: int):
    """Toggle a strategy's active/inactive state.

    Returns:
        200 with the updated strategy, 404 if not found.
    """
    result = strategy_service.toggle_strategy(get_db(), strategy_id)
    if result is None:
        return jsonify({"error": "Strategy not found"}), 404
    return jsonify({"strategy": result}), 200
