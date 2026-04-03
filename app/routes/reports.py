"""Reports API routes for Jade.

Blueprint registered at /api/reports.
All business logic is delegated to app.services.reports.
"""

from flask import Blueprint, jsonify, request

from app.db import get_db
from app.services import metrics_calculator as metrics_service
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


@bp.get("/trading-performance")
def trading_performance_report():
    """Aggregate trading performance metrics across a filtered trade set.

    Query params:
        account_id (int): Filter by trading account.
        strategy_id (int): Filter by strategy.
        asset_class (str): Filter by asset class (e.g. stocks, forex, crypto).
        start_date (str): ISO 8601 date — include trades with exit_date >= this.
        end_date (str): ISO 8601 date — include trades with exit_date <= this.

    Returns:
        JSON with ``filters``, ``summary`` counts, and all aggregate ``metrics``.
        Metrics that cannot be computed are returned as null.
    """
    account_id  = request.args.get("account_id",  None, type=int)
    strategy_id = request.args.get("strategy_id", None, type=int)
    asset_class = request.args.get("asset_class", None, type=str)
    start_date  = request.args.get("start_date",  None, type=str)
    end_date    = request.args.get("end_date",    None, type=str)

    try:
        data = metrics_service.get_trading_performance(
            get_db(),
            account_id=account_id,
            strategy_id=strategy_id,
            asset_class=asset_class,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422

    return jsonify(data), 200
