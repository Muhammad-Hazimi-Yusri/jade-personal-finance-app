"""Reports API routes for Jade.

Blueprint registered at /api/reports.
All business logic is delegated to app.services.reports.
"""

from flask import Blueprint, jsonify, request

from app.db import get_db
from app.services import reports as reports_service

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@bp.get("/spending")
def spending_report():
    """Spending comparison between current and previous period.

    Query params:
        period (str): Comparison type, default ``"month"``.
            Currently only ``"month"`` is supported.

    Returns:
        JSON with current_period, previous_period, categories, and totals.
    """
    period = request.args.get("period", "month", type=str)

    try:
        data = reports_service.get_spending_comparison(
            get_db(), period=period
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422

    return jsonify(data), 200
