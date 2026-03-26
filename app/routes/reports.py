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
            Ignored when start_date/end_date are provided.
        start_date (str): ISO 8601 date for "current" period start.
        end_date (str): ISO 8601 date for "current" period end.
            Previous period is auto-computed as the same duration shifted back.

    Returns:
        JSON with current_period, previous_period, categories, and totals.
    """
    period = request.args.get("period", "month", type=str)
    start_date = request.args.get("start_date", None, type=str)
    end_date = request.args.get("end_date", None, type=str)

    try:
        data = reports_service.get_spending_comparison(
            get_db(),
            period=period,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422

    return jsonify(data), 200
