"""Tag API routes for Jade.

Two blueprints live in this file:
  bp         — registered at /api/tags    (tag CRUD)
  trades_bp  — registered at /api/trades  (trade-tag association)

All business logic is delegated to app.services.tags.
"""

from flask import Blueprint, jsonify, request

from app.db import get_db
from app.services import tags as tag_service

bp = Blueprint("tags", __name__, url_prefix="/api/tags")
trades_bp = Blueprint("trade_tags", __name__, url_prefix="/api/trades")


# ---------------------------------------------------------------------------
# Tags CRUD
# ---------------------------------------------------------------------------


@bp.get("/")
def list_tags():
    """List all tags.

    Query params:
        group_name (str): Filter to a single group.

    Returns:
        JSON envelope with 'tags' array.
    """
    group_name = request.args.get("group_name") or None
    tags = tag_service.list_tags(get_db(), group_name=group_name)
    return jsonify({"tags": tags}), 200


@bp.post("/")
def create_tag():
    """Create a new tag.

    Request body (JSON):
        name (str, required): Tag display name, must be unique.
        group_name (str, optional): One of general/setup/mistake/pattern/market.

    Returns:
        201 with the created tag, 400 on missing body, 422 on validation error.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    try:
        result = tag_service.create_tag(get_db(), data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    return jsonify({"tag": result}), 201


@bp.delete("/<int:tag_id>")
def delete_tag(tag_id: int):
    """Delete a tag and all its trade associations.

    Returns:
        204 No Content on success, 404 if not found.
    """
    deleted = tag_service.delete_tag(get_db(), tag_id)
    if not deleted:
        return jsonify({"error": "Tag not found"}), 404
    return "", 204


# ---------------------------------------------------------------------------
# Trade-tag association
# ---------------------------------------------------------------------------


@trades_bp.post("/<int:trade_id>/tags")
def add_tags_to_trade(trade_id: int):
    """Add one or more tags to a trade.

    Request body (JSON):
        tag_ids (list[int], required): IDs of tags to attach.

    Returns:
        200 with the full updated tag list, 400 or 422 on error.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
    tag_ids = data.get("tag_ids")
    if not isinstance(tag_ids, list) or not tag_ids:
        return jsonify({"error": "tag_ids must be a non-empty list"}), 422
    try:
        result = tag_service.add_tags_to_trade(get_db(), trade_id, tag_ids)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    return jsonify({"tags": result}), 200


@trades_bp.delete("/<int:trade_id>/tags/<int:tag_id>")
def remove_tag_from_trade(trade_id: int, tag_id: int):
    """Remove a tag from a trade.

    Returns:
        204 No Content on success, 404 if the association does not exist.
    """
    removed = tag_service.remove_tag_from_trade(get_db(), trade_id, tag_id)
    if not removed:
        return jsonify({"error": "Tag association not found"}), 404
    return "", 204
