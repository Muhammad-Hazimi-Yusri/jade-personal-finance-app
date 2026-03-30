"""Trading account API routes for Jade.

Blueprint registered at /api/accounts.
All business logic is delegated to app.services.accounts.
"""

from flask import Blueprint, jsonify, request

from app.db import get_db
from app.services import accounts as account_service

bp = Blueprint("accounts", __name__, url_prefix="/api/accounts")


@bp.get("/")
def list_accounts():
    """List all trading accounts.

    Query params:
        active_only (str): '1' to return only active accounts.

    Returns:
        JSON envelope with 'accounts' array.
    """
    active_only = request.args.get("active_only", "0") == "1"
    accounts = account_service.list_accounts(get_db(), active_only=active_only)
    return jsonify({"accounts": accounts}), 200


@bp.get("/<int:account_id>")
def get_account(account_id: int):
    """Get a single trading account by ID.

    Returns:
        JSON account object, or 404 if not found.
    """
    result = account_service.get_account(get_db(), account_id)
    if result is None:
        return jsonify({"error": "Account not found"}), 404
    return jsonify(result), 200


@bp.post("/")
def create_account():
    """Create a new trading account.

    Request body (JSON):
        name (str, required): Account display name.
        broker (str, optional): Broker name.
        asset_class (str, required): stocks, forex, crypto, options, or multi.
        currency (str, optional): Currency code, defaults to 'GBP'.
        initial_balance (number, optional): Starting balance in pounds, defaults to 0.

    Returns:
        201 with the created account, or 422 on validation error.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    try:
        result = account_service.create_account(get_db(), data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    return jsonify(result), 201


@bp.put("/<int:account_id>")
def update_account(account_id: int):
    """Update an existing trading account.

    Returns:
        200 with the updated account, 404 if not found, 422 on error.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    try:
        result = account_service.update_account(get_db(), account_id, data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    if result is None:
        return jsonify({"error": "Account not found"}), 404
    return jsonify(result), 200


@bp.delete("/<int:account_id>")
def delete_account(account_id: int):
    """Delete a trading account.

    Returns:
        204 No Content on success, 404 if not found.
    """
    deleted = account_service.delete_account(get_db(), account_id)
    if not deleted:
        return jsonify({"error": "Account not found"}), 404
    return "", 204


@bp.post("/<int:account_id>/toggle")
def toggle_account(account_id: int):
    """Toggle a trading account's active/inactive state.

    Returns:
        200 with the updated account, 404 if not found.
    """
    result = account_service.toggle_account(get_db(), account_id)
    if result is None:
        return jsonify({"error": "Account not found"}), 404
    return jsonify(result), 200
