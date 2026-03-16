"""Monzo CSV parser service for Jade.

Validates and parses Monzo Plus/Premium CSV exports (16 columns).
Does NOT insert into the database — that is handled by the upload
endpoint (Phase 2.2).

Money convention: Monzo CSV contains decimal pounds. This module
converts to integer pence for consistency with the database layer.
"""

import csv
import io
import json
import sqlite3
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MONZO_PROFILE_NAME: str = "Monzo"

_MONZO_HEADERS: tuple[str, ...] = (
    "Transaction ID",
    "Date",
    "Time",
    "Type",
    "Name",
    "Emoji",
    "Category",
    "Amount",
    "Currency",
    "Local amount",
    "Local currency",
    "Notes and #tags",
    "Address",
    "Receipt",
    "Description",
    "Category split",
)

_MONZO_HEADERS_SET: frozenset[str] = frozenset(_MONZO_HEADERS)

_REQUIRED_ROW_FIELDS: frozenset[str] = frozenset({
    "Transaction ID",
    "Date",
    "Name",
    "Amount",
    "Currency",
})


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _to_pence(value: object) -> int:
    """Convert a decimal monetary value to integer pence.

    Uses ``Decimal`` for exact arithmetic to avoid IEEE 754 rounding
    errors (e.g. ``0.10 + 0.20 != 0.30`` with floats).

    Args:
        value: A numeric value in pounds (e.g. ``5.10``, ``-34.50``).

    Returns:
        Integer pence (e.g. ``510``, ``-3450``).
    """
    d = Decimal(str(value))
    return int((d * 100).to_integral_value(rounding=ROUND_HALF_UP))


def _normalize_header(header: str) -> str:
    """Strip whitespace and BOM characters from a CSV header.

    Monzo CSVs exported on Windows may have a UTF-8 BOM (``\\ufeff``)
    prefixed to the very first header.

    Args:
        header: Raw header string from the CSV reader.

    Returns:
        Cleaned header string.
    """
    return header.strip().lstrip("\ufeff")


def _parse_monzo_date(value: str, row_num: int) -> str:
    """Validate and return an ISO 8601 date string from a Monzo CSV row.

    Monzo dates look like: ``2024-01-15T12:20:18Z``

    Args:
        value: The raw date string from the CSV.
        row_num: 1-based row number for error messages.

    Returns:
        The validated date string (unchanged).

    Raises:
        ValueError: If the date cannot be parsed.
    """
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise ValueError(
            f"Row {row_num}: invalid date format: {value!r}"
        )
    return value


def _get_monzo_profile(db: sqlite3.Connection) -> dict:
    """Load the Monzo import profile from the database.

    Args:
        db: Open database connection.

    Returns:
        Dict with profile fields, including parsed ``column_mapping``.

    Raises:
        ValueError: If the Monzo profile is not found or is inactive.
    """
    row = db.execute(
        "SELECT * FROM import_profiles WHERE name = ? AND is_active = 1",
        (_MONZO_PROFILE_NAME,),
    ).fetchone()
    if row is None:
        raise ValueError(
            f"Import profile '{_MONZO_PROFILE_NAME}' not found or inactive"
        )
    profile = dict(row)
    profile["column_mapping"] = json.loads(profile["column_mapping"])
    return profile


def _get_valid_categories(db: sqlite3.Connection) -> set[str]:
    """Return the set of all valid category names.

    Args:
        db: Open database connection.

    Returns:
        Set of snake_case category name strings.
    """
    rows = db.execute("SELECT name FROM categories").fetchall()
    return {r["name"] for r in rows}


def _get_existing_monzo_ids(
    db: sqlite3.Connection,
    monzo_ids: list[str],
) -> set[str]:
    """Return the set of monzo_ids that already exist in the database.

    Uses batched IN queries to avoid exceeding the SQLite variable limit
    (default ``SQLITE_MAX_VARIABLE_NUMBER`` is 999).

    Args:
        db: Open database connection.
        monzo_ids: List of Monzo transaction IDs to check.

    Returns:
        Set of monzo_ids that are already in the transactions table.
    """
    if not monzo_ids:
        return set()

    existing: set[str] = set()
    batch_size = 500
    for i in range(0, len(monzo_ids), batch_size):
        batch = monzo_ids[i : i + batch_size]
        placeholders = ",".join("?" * len(batch))
        rows = db.execute(
            f"SELECT monzo_id FROM transactions WHERE monzo_id IN ({placeholders})",
            batch,
        ).fetchall()
        existing.update(r["monzo_id"] for r in rows)
    return existing


def _parse_monzo_row(
    row: dict[str, str],
    row_num: int,
    column_mapping: dict[str, str | None],
    valid_categories: set[str],
) -> dict:
    """Parse a single Monzo CSV row into a transaction dict.

    The returned dict uses transaction-table field names and has monetary
    values already converted to integer pence.

    Args:
        row: A ``csv.DictReader`` row (header → value).
        row_num: 1-based row number for error messages.
        column_mapping: Maps Monzo header names to transaction field names.
        valid_categories: Set of valid category snake_case names.

    Returns:
        Dict ready for database insertion (field names match the
        ``transactions`` table).

    Raises:
        ValueError: If a required field is missing or invalid.
    """
    # --- Required fields must be non-empty ---
    for field in _REQUIRED_ROW_FIELDS:
        val = row.get(field, "").strip()
        if not val:
            raise ValueError(
                f"Row {row_num}: required field '{field}' is empty"
            )

    monzo_id = row["Transaction ID"].strip()
    date = _parse_monzo_date(row["Date"].strip(), row_num)
    name = row["Name"].strip()

    # --- Amount: signed decimal pounds → integer pence ---
    try:
        amount_str = row["Amount"].strip()
        amount_pence = _to_pence(amount_str)
    except Exception:
        raise ValueError(
            f"Row {row_num}: invalid amount: {row['Amount']!r}"
        )

    if amount_pence == 0:
        raise ValueError(f"Row {row_num}: amount is zero")

    # --- Category: validate against known categories, fall back to 'general' ---
    raw_category = row.get("Category", "").strip()
    if raw_category and raw_category in valid_categories:
        category = raw_category
    else:
        category = "general"

    is_income = 1 if amount_pence > 0 else 0

    # --- Optional fields ---
    type_ = row.get("Type", "").strip() or None
    emoji = row.get("Emoji", "").strip() or None
    currency = row.get("Currency", "").strip() or "GBP"
    notes = row.get("Notes and #tags", "").strip() or None
    address = row.get("Address", "").strip() or None
    description = row.get("Description", "").strip() or None

    # --- Local amount/currency (foreign transactions only) ---
    local_amount_pence = None
    local_amount_str = row.get("Local amount", "").strip()
    if local_amount_str:
        try:
            local_amount_pence = _to_pence(local_amount_str)
        except Exception:
            raise ValueError(
                f"Row {row_num}: invalid local amount: {local_amount_str!r}"
            )

    local_currency = row.get("Local currency", "").strip() or None

    # --- Category split: append to notes if present ---
    category_split = row.get("Category split", "").strip()
    if category_split:
        split_text = f"[Category split: {category_split}]"
        notes = f"{notes} {split_text}" if notes else split_text

    return {
        "monzo_id": monzo_id,
        "date": date,
        "type": type_,
        "name": name,
        "emoji": emoji,
        "category": category,
        "amount": amount_pence,
        "currency": currency,
        "local_amount": local_amount_pence,
        "local_currency": local_currency,
        "notes": notes,
        "address": address,
        "description": description,
        "is_income": is_income,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_csv(
    file_stream: io.TextIOWrapper | io.StringIO,
) -> dict:
    """Validate that a file stream contains a valid Monzo CSV.

    Checks that the file is readable as CSV, has a header row, and that
    the header contains all 16 expected Monzo columns.  Extra columns
    are tolerated (Monzo may add new ones in the future).

    Args:
        file_stream: A text-mode file-like object positioned at the start.

    Returns:
        Dict with validation results::

            {
                "valid": bool,
                "headers": [str, ...],
                "expected_headers": [str, ...],
                "missing_headers": [str, ...],
                "extra_headers": [str, ...],
                "row_count": int,
                "error": str | None,
            }

    Note:
        This function reads the entire stream to count rows.  The caller
        should rewind or re-open the stream before calling
        ``parse_monzo_csv()``.
    """
    try:
        reader = csv.reader(file_stream)
        raw_headers = next(reader, None)
    except csv.Error as exc:
        return {
            "valid": False,
            "headers": [],
            "expected_headers": list(_MONZO_HEADERS),
            "missing_headers": list(_MONZO_HEADERS),
            "extra_headers": [],
            "row_count": 0,
            "error": f"Cannot parse as CSV: {exc}",
        }

    if raw_headers is None:
        return {
            "valid": False,
            "headers": [],
            "expected_headers": list(_MONZO_HEADERS),
            "missing_headers": list(_MONZO_HEADERS),
            "extra_headers": [],
            "row_count": 0,
            "error": "File is empty",
        }

    headers = [_normalize_header(h) for h in raw_headers]
    headers_set = frozenset(headers)

    missing = sorted(_MONZO_HEADERS_SET - headers_set)
    extra = sorted(headers_set - _MONZO_HEADERS_SET)

    # Count data rows
    row_count = sum(1 for _ in reader)

    valid = len(missing) == 0

    return {
        "valid": valid,
        "headers": headers,
        "expected_headers": list(_MONZO_HEADERS),
        "missing_headers": missing,
        "extra_headers": extra,
        "row_count": row_count,
        "error": f"Missing headers: {', '.join(missing)}" if missing else None,
    }


def parse_monzo_csv(
    file_stream: io.TextIOWrapper | io.StringIO,
    db: sqlite3.Connection,
) -> dict:
    """Parse a Monzo CSV file stream and return structured results.

    Validates each row, converts monetary values to pence, and checks
    for duplicates via ``monzo_id``.  Does **not** insert into the
    database — the caller (upload endpoint) handles insertion.

    Uses a two-pass approach for efficiency:

    1. First pass collects all ``monzo_id`` values and performs a single
       batch deduplication query.
    2. Second pass parses each row into a transaction dict.

    Per-row errors are collected into the ``errors`` list rather than
    aborting the entire parse, so a CSV with a few bad rows can still
    import the valid ones.

    Args:
        file_stream: A text-mode file-like object positioned at the
            start, containing a valid Monzo CSV (header already
            verified via ``validate_csv``).
        db: Open database connection (used for dedup lookups, category
            validation, and loading the Monzo import profile).

    Returns:
        Dict with parse results::

            {
                "rows": [dict, ...],       # transaction dicts ready for INSERT
                "duplicates": [dict, ...],  # skipped rows (already in DB)
                "errors": [dict, ...],      # rows that failed validation
                "total": int,              # total data rows in CSV
                "new_count": int,          # len(rows)
                "duplicate_count": int,    # len(duplicates)
                "error_count": int,        # len(errors)
            }

    Raises:
        ValueError: If the Monzo import profile is not found, or if the
            CSV headers are invalid.
    """
    # Load import profile for column mapping
    profile = _get_monzo_profile(db)
    column_mapping = profile["column_mapping"]

    # Load valid categories for row-level validation
    valid_categories = _get_valid_categories(db)

    # Parse CSV with DictReader
    reader = csv.DictReader(file_stream)

    if reader.fieldnames is None:
        raise ValueError("CSV file is empty or has no header row")

    # Validate headers
    actual_headers = frozenset(
        _normalize_header(h) for h in reader.fieldnames
    )
    missing = _MONZO_HEADERS_SET - actual_headers
    if missing:
        raise ValueError(
            f"CSV is missing required Monzo headers: {', '.join(sorted(missing))}"
        )

    # --- First pass: collect rows and monzo_ids for batch dedup ---
    raw_rows: list[dict[str, str]] = []
    monzo_ids: list[str] = []
    for row in reader:
        raw_rows.append(row)
        tid = row.get("Transaction ID", "").strip()
        if tid:
            monzo_ids.append(tid)

    existing_ids = _get_existing_monzo_ids(db, monzo_ids)

    # --- Second pass: parse each row ---
    parsed_rows: list[dict] = []
    duplicates: list[dict] = []
    errors: list[dict] = []

    for idx, row in enumerate(raw_rows, start=2):  # row 1 is header
        monzo_id = row.get("Transaction ID", "").strip()

        # Check duplicate
        if monzo_id in existing_ids:
            duplicates.append({
                "row_num": idx,
                "monzo_id": monzo_id,
                "name": row.get("Name", "").strip(),
                "date": row.get("Date", "").strip(),
            })
            continue

        # Parse row
        try:
            parsed = _parse_monzo_row(
                row, idx, column_mapping, valid_categories,
            )
            parsed_rows.append(parsed)
        except ValueError as exc:
            errors.append({
                "row_num": idx,
                "error": str(exc),
            })

    return {
        "rows": parsed_rows,
        "duplicates": duplicates,
        "errors": errors,
        "total": len(raw_rows),
        "new_count": len(parsed_rows),
        "duplicate_count": len(duplicates),
        "error_count": len(errors),
    }
