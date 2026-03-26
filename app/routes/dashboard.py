"""Dashboard API routes for Jade.

Blueprint registered at /api/dashboard.
All business logic is delegated to app.services.dashboard.
"""

from flask import Blueprint, jsonify, request

from app.db import get_db
from app.services import dashboard as dashboard_service

bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@bp.get("/finance")
def finance_dashboard():
    """Finance dashboard overview.

    Query params:
        months (int): Number of months for chart history, default 6, max 24.
            Ignored when start_date/end_date are provided.
        start_date (str): ISO 8601 date for range start (inclusive).
        end_date (str): ISO 8601 date for range end (inclusive).
        limit (int): Number of recent transactions, default 10, max 50.

    Returns:
        JSON envelope with summary, income_vs_expenses, spending_by_category,
        cash_flow, budget_status, and recent_transactions.
    """
    months = request.args.get("months", 6, type=int)
    limit = request.args.get("limit", 10, type=int)
    start_date = request.args.get("start_date", None, type=str)
    end_date = request.args.get("end_date", None, type=str)

    try:
        data = dashboard_service.get_finance_dashboard(
            get_db(),
            months=months,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422

    return jsonify(data), 200
