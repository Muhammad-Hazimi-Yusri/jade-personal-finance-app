"""Upload API routes for Jade.

Blueprint registered at /api/upload.
Handles CSV file uploads for Monzo bank statement imports.
"""

import io
import sqlite3

from flask import Blueprint, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from app.db import get_db
from app.services import csv_parser

bp = Blueprint("upload", __name__, url_prefix="/api/upload")

_MAX_FILE_SIZE_MB: int = 10

_INSERT_COLUMNS: tuple[str, ...] = (
    "monzo_id", "date", "type", "name", "emoji", "category",
    "amount", "currency", "local_amount", "local_currency",
    "notes", "address", "description", "is_income", "custom_category",
)

_INSERT_SQL: str = (
    f"INSERT INTO transactions ({', '.join(_INSERT_COLUMNS)}) "
    f"VALUES ({', '.join('?' * len(_INSERT_COLUMNS))})"
)


@bp.errorhandler(RequestEntityTooLarge)
def handle_too_large(e):
    """Return JSON 413 instead of Flask's default HTML error page."""
    return jsonify({
        "error": f"File exceeds maximum size of {_MAX_FILE_SIZE_MB}MB"
    }), 413


@bp.post("/monzo")
def upload_monzo():
    """Upload and import a Monzo CSV bank statement.

    Expects a multipart/form-data request with a ``file`` field
    containing a CSV file (<=10 MB, .csv extension).

    The endpoint validates the file, parses rows with deduplication
    via ``monzo_id``, bulk-inserts new transactions, and returns an
    import summary.

    Returns:
        JSON with ``imported``, ``skipped``, ``errors``, and ``total``.
    """
    # --- File presence ---
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]

    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    # --- Extension check ---
    if not file.filename.lower().endswith(".csv"):
        return jsonify({"error": "Only .csv files are accepted"}), 400

    # --- Read and decode ---
    try:
        raw_bytes = file.read()
    except Exception:
        return jsonify({"error": "Failed to read uploaded file"}), 400

    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return jsonify({"error": "File is not valid UTF-8 text"}), 400

    # --- Validate CSV headers ---
    validation = csv_parser.validate_csv(io.StringIO(text))

    if not validation["valid"]:
        return jsonify({
            "error": validation["error"],
            "missing_headers": validation["missing_headers"],
        }), 422

    # --- Parse rows (includes dedup via monzo_id) ---
    db = get_db()

    try:
        result = csv_parser.parse_monzo_csv(io.StringIO(text), db)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422

    # --- Bulk insert new rows ---
    imported_ids: list[int] = []

    try:
        if result["rows"]:
            params = [
                tuple(row.get(col) for col in _INSERT_COLUMNS)
                for row in result["rows"]
            ]
            db.executemany(_INSERT_SQL, params)
            db.commit()

            # Collect auto-generated IDs of the inserted transactions
            monzo_ids = [r["monzo_id"] for r in result["rows"]]
            placeholders = ",".join("?" * len(monzo_ids))
            id_rows = db.execute(
                f"SELECT id FROM transactions WHERE monzo_id IN ({placeholders})",
                monzo_ids,
            ).fetchall()
            imported_ids = [r[0] for r in id_rows]
    except sqlite3.IntegrityError as exc:
        db.rollback()
        return jsonify({"error": f"Database integrity error: {exc}"}), 409
    except Exception as exc:
        db.rollback()
        return jsonify({"error": f"Import failed: {exc}"}), 500

    return jsonify({
        "imported": result["new_count"],
        "skipped": result["duplicate_count"],
        "errors": result["errors"],
        "total": result["total"],
        "imported_ids": imported_ids,
    }), 200
