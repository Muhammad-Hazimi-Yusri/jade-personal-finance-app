"""Daily journal API routes for Jade.

Blueprint registered at /api/journal.
All business logic is delegated to app.services.journal.
"""

from flask import Blueprint, jsonify, request

from app.db import get_db
from app.services import journal as journal_service

bp = Blueprint("journal", __name__, url_prefix="/api/journal")


@bp.get("/")
def list_entries():
    """List journal entries ordered by date descending.

    Query params:
        limit (int): Number of entries to return (default 50, max 200).
        offset (int): Number of entries to skip (default 0).

    Returns:
        JSON array of journal entry objects.
    """
    limit = request.args.get("limit", 50)
    offset = request.args.get("offset", 0)
    try:
        entries = journal_service.list_entries(get_db(), limit=limit, offset=offset)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 422
    return jsonify({"entries": entries}), 200


@bp.get("/<date>")
def get_entry(date: str):
    """Get the journal entry for a specific date.

    Args:
        date: YYYY-MM-DD date string in the URL path.

    Returns:
        JSON journal entry object, or 404 if no entry exists for that date.
    """
    entry = journal_service.get_entry(get_db(), date)
    if entry is None:
        return jsonify({"error": "No journal entry found for this date"}), 404
    return jsonify({"entry": entry}), 200


@bp.post("/")
def upsert_entry():
    """Create or update the journal entry for a given date.

    Request body (JSON):
        date (str, required): YYYY-MM-DD date string.
        market_outlook (str, optional): Overall market view for the day.
        plan (str, optional): What you planned to do.
        review (str, optional): End-of-day review.
        mood (int, optional): 1 (terrible) to 5 (great).
        lessons (str, optional): Key takeaways.

    Returns:
        201 if created, 200 if updated, 422 on validation error.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    date = data.get("date")
    if not date:
        return jsonify({"error": "date is required"}), 422

    try:
        entry = journal_service.upsert_entry(get_db(), date, data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422

    status_code = 201 if entry["created_at"] == entry["updated_at"] else 200
    return jsonify({"entry": entry}), status_code


@bp.delete("/<date>")
def delete_entry(date: str):
    """Delete the journal entry for a specific date.

    Args:
        date: YYYY-MM-DD date string in the URL path.

    Returns:
        204 No Content on success, 404 if no entry exists for that date.
    """
    deleted = journal_service.delete_entry(get_db(), date)
    if not deleted:
        return jsonify({"error": "No journal entry found for this date"}), 404
    return "", 204
