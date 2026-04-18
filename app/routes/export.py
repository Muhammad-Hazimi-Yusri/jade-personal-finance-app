"""Data export API routes for Jade.

Blueprint registered at /api/export. Provides CSV exports of the two main
ledgers (transactions, trades) and a single JSON blob containing every
user-owned table for full portability / offline backup.

All monetary values are converted from integer pence (storage) to decimal
GBP at the API boundary, matching the convention used everywhere else.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Iterable

from flask import Blueprint, Response, jsonify

from app.db import get_db

bp = Blueprint("export", __name__, url_prefix="/api/export")


# Columns stored as integer pence that must be converted to decimal on export.
_PENCE_COLUMNS = {
    "transactions": {"amount", "local_amount"},
    "trades": {
        "entry_price", "entry_fee", "exit_price", "exit_fee",
        "stop_loss", "take_profit", "risk_amount",
        "pnl", "pnl_net", "mae", "mfe", "strike_price",
    },
    "budgets": {"amount"},
    "trading_accounts": {"initial_balance"},
    "account_snapshots": {"balance", "equity"},
}


def _pence_to_decimal(value: Any) -> Any:
    """Convert a pence integer to a 2dp decimal float, preserving NULL."""
    if value is None:
        return None
    return round(int(value) / 100, 2)


def _row_to_dict(row, table: str) -> dict[str, Any]:
    """Convert a sqlite3.Row to a dict, converting pence columns to decimal."""
    pence_cols = _PENCE_COLUMNS.get(table, set())
    return {
        key: _pence_to_decimal(row[key]) if key in pence_cols else row[key]
        for key in row.keys()
    }


def _fetch_all(table: str) -> list[dict[str, Any]]:
    """Return every row in `table` as a list of dicts, pence→decimal."""
    db = get_db()
    rows = db.execute(f"SELECT * FROM {table}").fetchall()  # table name fixed by us, safe
    return [_row_to_dict(r, table) for r in rows]


def _rows_to_csv(rows: Iterable[dict[str, Any]]) -> str:
    """Serialise an iterable of dicts into a CSV string.

    Uses the keys of the first row as the header. Empty input returns an
    empty string (the caller still sends a 200 — clients get a valid,
    zero-row CSV).
    """
    rows = list(rows)
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def _csv_response(body: str, filename: str) -> Response:
    """Build a CSV download response with a sensible filename."""
    return Response(
        body,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@bp.get("/transactions.csv")
def export_transactions_csv():
    """Download all transactions as CSV."""
    rows = _fetch_all("transactions")
    body = _rows_to_csv(rows)
    stamp = datetime.utcnow().strftime("%Y%m%d")
    return _csv_response(body, f"jade-transactions-{stamp}.csv")


@bp.get("/trades.csv")
def export_trades_csv():
    """Download all trades as CSV."""
    rows = _fetch_all("trades")
    body = _rows_to_csv(rows)
    stamp = datetime.utcnow().strftime("%Y%m%d")
    return _csv_response(body, f"jade-trades-{stamp}.csv")


@bp.get("/all.json")
def export_all_json():
    """Download a single JSON blob with every user-owned table.

    Suitable as a full backup / portability export. Monetary values are
    decimal GBP; dates are stored as-is (ISO strings per app convention).
    """
    tables = [
        "transactions",
        "trades",
        "categories",
        "category_rules",
        "trading_accounts",
        "strategies",
        "tags",
        "trade_tags",
        "budgets",
        "daily_journal",
        "account_snapshots",
        "import_profiles",
    ]
    payload = {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "schema_version": _current_schema_version(),
        "data": {table: _fetch_all(table) for table in tables},
    }
    response = jsonify(payload)
    stamp = datetime.utcnow().strftime("%Y%m%d")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="jade-export-{stamp}.json"'
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def _current_schema_version() -> int | None:
    """Return the highest applied migration version, or None if unknown."""
    try:
        row = get_db().execute(
            "SELECT MAX(version) AS v FROM schema_version"
        ).fetchone()
        return row["v"] if row else None
    except Exception:
        return None
