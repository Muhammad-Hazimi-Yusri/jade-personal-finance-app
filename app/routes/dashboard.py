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
        limit (int): Number of recent transactions, default 10, max 50.

    Returns:
        JSON envelope with summary, income_vs_expenses, spending_by_category,
        cash_flow, budget_status, and recent_transactions.
    """
    months = request.args.get("months", 6, type=int)
    limit = request.args.get("limit", 10, type=int)

    try:
        data = dashboard_service.get_finance_dashboard(
            get_db(), months=months, limit=limit
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422

    return jsonify(data), 200
