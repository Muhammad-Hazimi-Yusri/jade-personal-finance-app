"""Trade API routes for Jade.

Blueprint registered at /api/trades.
All business logic is delegated to app.services.trades.
"""

from flask import Blueprint, jsonify, request

from app.db import get_db
from app.services import trades as trade_service

bp = Blueprint("trades", __name__, url_prefix="/api/trades")


@bp.get("/")
def list_trades():
    """List trades with optional filtering and pagination.

    Query params:
        account_id (int): Filter by trading account.
        asset_class (str): stocks, forex, crypto, options.
        symbol (str): Filter by instrument symbol.
        strategy_id (int): Filter by strategy.
        is_open (int): 1 = open trades only, 0 = closed trades only.
        direction (str): long or short.
        start_date (str): ISO 8601 date — entry_date >= this value.
        end_date (str): ISO 8601 date — entry_date <= this value.
        page (int): Page number (default 1).
        per_page (int): Items per page (default 50, max 200).

    Returns:
        JSON envelope with trades array and pagination metadata.
    """
    filters = {
        "account_id": request.args.get("account_id"),
        "asset_class": request.args.get("asset_class"),
        "symbol": request.args.get("symbol"),
        "strategy_id": request.args.get("strategy_id"),
        "is_open": request.args.get("is_open"),
        "direction": request.args.get("direction"),
        "start_date": request.args.get("start_date"),
        "end_date": request.args.get("end_date"),
        "page": request.args.get("page"),
        "per_page": request.args.get("per_page"),
    }
    # Remove None-valued keys so the service can distinguish "not provided"
    filters = {k: v for k, v in filters.items() if v is not None}
    result = trade_service.list_trades(get_db(), filters)
    return jsonify(result), 200


@bp.get("/<int:trade_id>")
def get_trade(trade_id: int):
    """Get a single trade by ID including its tags.

    Returns:
        JSON trade object, or 404 if not found.
    """
    result = trade_service.get_trade(get_db(), trade_id)
    if result is None:
        return jsonify({"error": "Trade not found"}), 404
    return jsonify({"trade": result}), 200


@bp.post("/")
def create_trade():
    """Create a new trade.

    Request body (JSON):
        account_id (int, required)
        symbol (str, required): Instrument symbol, e.g. AAPL, EUR/USD.
        asset_class (str, required): stocks, forex, crypto, options.
        direction (str, required): long or short.
        entry_date (str, required): ISO 8601 date.
        entry_price (number, required): Entry price in pounds (stored as pence).
        position_size (number, required): Quantity / lots / contracts.
        entry_fee (number, optional): Entry commission in pounds.
        strategy_id (int, optional)
        ... (all other optional trade fields)

    Returns:
        201 with the created trade, or 422 on validation error.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    try:
        result = trade_service.create_trade(get_db(), data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    return jsonify({"trade": result}), 201


@bp.put("/<int:trade_id>")
def update_trade(trade_id: int):
    """Update an existing trade (partial update).

    Returns:
        200 with the updated trade, 404 if not found, 422 on validation error.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    try:
        result = trade_service.update_trade(get_db(), trade_id, data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    if result is None:
        return jsonify({"error": "Trade not found"}), 404
    return jsonify({"trade": result}), 200


@bp.delete("/<int:trade_id>")
def delete_trade(trade_id: int):
    """Delete a trade.

    Returns:
        204 No Content on success, 404 if not found.
    """
    deleted = trade_service.delete_trade(get_db(), trade_id)
    if not deleted:
        return jsonify({"error": "Trade not found"}), 404
    return "", 204


@bp.post("/<int:trade_id>/close")
def close_trade(trade_id: int):
    """Close an open trade by recording exit details.

    P&L calculation is deferred to phase 4.9; this endpoint only records
    the exit price, date, and fee, and marks the trade as closed.

    Request body (JSON):
        exit_date (str, required): ISO 8601 date of exit.
        exit_price (number, required): Exit price in pounds.
        exit_fee (number, optional): Exit commission in pounds.

    Returns:
        200 with the updated trade, 400 if already closed or fields missing,
        404 if not found.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    try:
        result = trade_service.close_trade(get_db(), trade_id, data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if result is None:
        return jsonify({"error": "Trade not found"}), 404
    return jsonify({"trade": result}), 200
