"""Transaction API routes for Jade.

Blueprint registered at /api/transactions.
All business logic is delegated to app.services.transactions.
"""

from flask import Blueprint, jsonify, request

from app.db import get_db
from app.services import transactions as tx_service

bp = Blueprint("transactions", __name__, url_prefix="/api/transactions")

_VALID_SORT_FIELDS = frozenset({
    "date", "amount", "name", "category", "created_at", "updated_at"
})


@bp.get("/")
def list_transactions():
    """List transactions with pagination and optional filtering.

    Query parameters:
        page (int): Page number, default 1.
        per_page (int): Items per page, default 50, max 200.
        category (str): Filter by category snake_case name.
        type (str): Filter by transaction type.
        start_date (str): ISO 8601 lower bound on date (inclusive).
        end_date (str): ISO 8601 upper bound on date (inclusive).
        search (str): Search name, notes, and description.
        min_amount (float): Minimum amount in decimal GBP (inclusive).
        max_amount (float): Maximum amount in decimal GBP (inclusive).
        sort (str): Sort field, default 'date'.
        order (str): 'asc' or 'desc', default 'desc'.

    Returns:
        JSON envelope with 'transactions' array and 'pagination' metadata.
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    sort = request.args.get("sort", "date")
    order = request.args.get("order", "desc").lower()

    if page < 1:
        return jsonify({"error": "page must be >= 1"}), 400
    if sort not in _VALID_SORT_FIELDS:
        return jsonify({
            "error": f"Invalid sort field. Must be one of: {', '.join(sorted(_VALID_SORT_FIELDS))}"
        }), 400
    if order not in ("asc", "desc"):
        return jsonify({"error": "order must be 'asc' or 'desc'"}), 400

    # Parse optional ids filter (comma-separated integers)
    ids = None
    ids_raw = request.args.get("ids")
    if ids_raw:
        try:
            ids = [int(x) for x in ids_raw.split(",") if x.strip()]
        except ValueError:
            return jsonify({"error": "ids must be comma-separated integers"}), 400

    result = tx_service.list_transactions(
        get_db(),
        page=page,
        per_page=per_page,
        category=request.args.get("category"),
        type_=request.args.get("type"),
        start_date=request.args.get("start_date"),
        end_date=request.args.get("end_date"),
        search=request.args.get("search"),
        min_amount=request.args.get("min_amount", type=float),
        max_amount=request.args.get("max_amount", type=float),
        ids=ids,
        sort=sort,
        order=order,
    )
    return jsonify(result), 200


@bp.get("/<int:transaction_id>")
def get_transaction(transaction_id: int):
    """Get a single transaction by ID.

    Args:
        transaction_id: Primary key of the transaction.

    Returns:
        JSON transaction object, or 404 if not found.
    """
    result = tx_service.get_transaction(get_db(), transaction_id)
    if result is None:
        return jsonify({"error": "Transaction not found"}), 404
    return jsonify(result), 200


@bp.post("/")
def create_transaction():
    """Create a new transaction.

    Request body (JSON):
        date (str, required): ISO 8601 date string.
        name (str, required): Display name / merchant.
        amount (float, required): Signed decimal GBP; negative = debit.
            Stored as integer pence internally.
        category (str, required): snake_case category name.
        monzo_id (str, optional): Monzo transaction ID for deduplication.
        type (str, optional): Transaction type string.
        emoji (str, optional): Monzo emoji.
        currency (str, optional): Currency code, default 'GBP'.
        local_amount (float, optional): Foreign currency amount (decimal).
        local_currency (str, optional): Foreign currency code.
        notes (str, optional): Free-text notes.
        address (str, optional): Physical address.
        description (str, optional): Raw merchant string.
        custom_category (str, optional): User override category.

    Returns:
        201 with the created transaction, or 422 on validation error.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    try:
        result = tx_service.create_transaction(get_db(), data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    return jsonify(result), 201


@bp.put("/<int:transaction_id>")
def update_transaction(transaction_id: int):
    """Partially update an existing transaction.

    Only fields supplied in the request body are updated.

    Args:
        transaction_id: Primary key of the transaction to update.

    Returns:
        200 with the updated transaction, 404 if not found, 422 on error.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    try:
        result = tx_service.update_transaction(get_db(), transaction_id, data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    if result is None:
        return jsonify({"error": "Transaction not found"}), 404
    return jsonify(result), 200


@bp.delete("/<int:transaction_id>")
def delete_transaction(transaction_id: int):
    """Delete a transaction by ID.

    Args:
        transaction_id: Primary key of the transaction to delete.

    Returns:
        204 No Content on success, 404 if not found.
    """
    deleted = tx_service.delete_transaction(get_db(), transaction_id)
    if not deleted:
        return jsonify({"error": "Transaction not found"}), 404
    return "", 204
