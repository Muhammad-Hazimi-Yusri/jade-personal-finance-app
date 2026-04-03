"""Account snapshot API routes for Jade.

Blueprint registered at /api/snapshots.
All business logic is delegated to app.services.snapshots.
"""

from flask import Blueprint, jsonify, request

from app.db import get_db
from app.services import snapshots as snapshots_service

bp = Blueprint("snapshots", __name__, url_prefix="/api/snapshots")


@bp.get("/")
def list_snapshots():
    """List account snapshots, optionally filtered.

    Query params:
        account_id (int): Filter by trading account.
        start_date (str): Lower bound date (YYYY-MM-DD, inclusive).
        end_date (str): Upper bound date (YYYY-MM-DD, inclusive).

    Returns:
        JSON object with a ``snapshots`` array, ordered by date ascending.
    """
    account_id = request.args.get("account_id", type=int)
    start_date = request.args.get("start_date") or None
    end_date = request.args.get("end_date") or None

    snapshots = snapshots_service.list_snapshots(
        get_db(),
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
    )
    return jsonify({"snapshots": snapshots}), 200


@bp.get("/<int:snapshot_id>")
def get_snapshot(snapshot_id: int):
    """Get a single snapshot by ID.

    Returns:
        JSON snapshot object, or 404 if not found.
    """
    snapshot = snapshots_service.get_snapshot(get_db(), snapshot_id)
    if snapshot is None:
        return jsonify({"error": "Snapshot not found"}), 404
    return jsonify({"snapshot": snapshot}), 200


@bp.post("/")
def upsert_snapshot():
    """Create or update a snapshot for a given account and date.

    Request body (JSON):
        account_id (int, required): Trading account ID.
        date (str, required): YYYY-MM-DD date string.
        balance (float, required): Account balance in decimal pounds.
        equity (float, optional): Balance + unrealised P&L in decimal pounds.
        note (str, optional): Free-text note.

    Returns:
        201 if a new snapshot was created, 200 if an existing one was updated.
        422 on validation error.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    try:
        snapshot, created = snapshots_service.upsert_snapshot(get_db(), data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422

    status_code = 201 if created else 200
    return jsonify({"snapshot": snapshot}), status_code


@bp.delete("/<int:snapshot_id>")
def delete_snapshot(snapshot_id: int):
    """Delete a snapshot by ID.

    Returns:
        204 No Content on success, 404 if not found.
    """
    deleted = snapshots_service.delete_snapshot(get_db(), snapshot_id)
    if not deleted:
        return jsonify({"error": "Snapshot not found"}), 404
    return "", 204
