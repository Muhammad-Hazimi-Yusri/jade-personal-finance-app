"""Tests for transfer-aware spending aggregation.

Covers:
  - `_detect_transfer_category` correctly identifies Pot transfers,
    Flex repayments, and known investment providers.
  - Dashboard KPIs (`get_summary`, `get_income_vs_expenses`,
    `get_spending_by_category`, `get_cash_flow`) exclude `savings`
    and `transfers` categories from income/expense sums while
    leaving the running balance unchanged.
  - `recategorize_transfers` is idempotent and respects
    `custom_category` user overrides.
"""

import sqlite3
from pathlib import Path

import pytest

from app.services.csv_parser import (
    TRANSFER_CATEGORIES,
    _detect_transfer_category,
)
from app.services.dashboard import (
    get_cash_flow,
    get_income_vs_expenses,
    get_spending_by_category,
    get_summary,
)
from app.services.transactions import recategorize_transfers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_MIGRATIONS = Path(__file__).parent.parent / "app" / "migrations"


def _build_db() -> sqlite3.Connection:
    """In-memory SQLite seeded with every migration in order."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # schema_version is created by db.run_migrations, replicate minimally
    conn.execute(
        """
        CREATE TABLE schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now')),
            description TEXT
        )
        """
    )

    for sql_file in sorted(_MIGRATIONS.glob("*.sql")):
        conn.executescript(sql_file.read_text())
        version = int(sql_file.stem.split("_")[0])
        conn.execute(
            "INSERT INTO schema_version (version, description) VALUES (?, ?)",
            (version, sql_file.stem),
        )

    # Seed minimal categories used by tests.
    conn.executemany(
        "INSERT OR IGNORE INTO categories (name, label, colour) VALUES (?, ?, ?)",
        [
            ("general", "General", "#6B7280"),
            ("bills", "Bills", "#EF4444"),
            ("groceries", "Groceries", "#10B981"),
            ("savings", "Savings", "#00A86B"),
            ("transfers", "Transfers", "#3B82F6"),
            ("income", "Income", "#22D3EE"),
        ],
    )

    conn.commit()
    return conn


def _insert_tx(
    db: sqlite3.Connection,
    *,
    date: str,
    name: str,
    amount: int,
    category: str = "general",
    type_: str | None = None,
    custom_category: str | None = None,
) -> int:
    """Insert a single transaction and return its row id."""
    cur = db.execute(
        """
        INSERT INTO transactions
            (date, type, name, category, amount, currency,
             is_income, custom_category)
        VALUES (?, ?, ?, ?, ?, 'GBP', ?, ?)
        """,
        (date, type_, name, category, amount, 1 if amount > 0 else 0, custom_category),
    )
    db.commit()
    return cur.lastrowid


# ---------------------------------------------------------------------------
# _detect_transfer_category
# ---------------------------------------------------------------------------


class TestDetectTransferCategory:
    def test_pot_transfer_out(self):
        assert _detect_transfer_category("Pot transfer", "Rainy day Pot", -50000) == "savings"

    def test_pot_transfer_in(self):
        # Positive amount (pot withdrawal) is still a transfer
        assert _detect_transfer_category("Pot transfer", "Rainy day Pot", 50000) == "savings"

    def test_flex_repayment_negative(self):
        assert _detect_transfer_category("Flex", "", -29501) == "transfers"

    def test_flex_returned_to_account_positive(self):
        # Returned-from-Flex is income, not a transfer
        assert _detect_transfer_category("Flex", "Traintickets.com", 570) is None

    def test_moneybox_faster_payment(self):
        assert _detect_transfer_category("Faster payment", "Moneybox Cash LISA", -100000) == "savings"

    def test_trading_212(self):
        assert _detect_transfer_category("Faster payment", "Trading 212", -1000) == "savings"

    def test_seccl(self):
        assert _detect_transfer_category("Faster payment", "Seccl", -395) == "savings"

    def test_seccl_case_insensitive(self):
        assert _detect_transfer_category("Faster payment", "SECCL", -395) == "savings"

    def test_regular_card_payment(self):
        assert _detect_transfer_category("Card payment", "Tesco", -2345) is None

    def test_direct_debit_unchanged(self):
        assert _detect_transfer_category("Direct Debit", "Talkmobile", -795) is None

    def test_unknown_faster_payment(self):
        assert _detect_transfer_category("Faster payment", "Aiman Hazim Shafizam", -24200) is None


# ---------------------------------------------------------------------------
# Dashboard exclusion
# ---------------------------------------------------------------------------


class TestDashboardExcludesTransfers:
    @pytest.fixture
    def db(self):
        conn = _build_db()
        # February 2026 data — a small, representative mix.
        _insert_tx(conn, date="2026-02-02", name="Talkmobile", amount=-795, category="bills", type_="Direct Debit")
        _insert_tx(conn, date="2026-02-05", name="Tesco", amount=-3450, category="groceries", type_="Card payment")
        _insert_tx(conn, date="2026-02-10", name="Salary", amount=250000, category="income", type_="Faster payment")
        # Transfers that should NOT be counted as income/expense.
        _insert_tx(conn, date="2026-02-16", name="Rainy day Pot", amount=-700, category="savings", type_="Pot transfer")
        _insert_tx(conn, date="2026-02-20", name="Rainy day Pot", amount=100000, category="savings", type_="Pot transfer")
        _insert_tx(conn, date="2026-02-22", name="Flex", amount=-29501, category="transfers", type_="Flex")
        return conn

    def test_summary_expenses_exclude_transfers(self, db):
        result = get_summary(db, start_date="2026-02-01", end_date="2026-02-28")
        # Real spending: 7.95 (bills) + 34.50 (groceries) = 42.45
        assert result["expenses"] == 42.45

    def test_summary_income_excludes_pot_withdrawal(self, db):
        result = get_summary(db, start_date="2026-02-01", end_date="2026-02-28")
        # Real income: 2500.00 salary only — pot withdrawal of £1000 excluded
        assert result["income"] == 2500.00

    def test_summary_balance_still_includes_transfers(self, db):
        result = get_summary(db, start_date="2026-02-01", end_date="2026-02-28")
        # Balance = SUM of all amounts in pence / 100
        # = -795 -3450 +250000 -700 +100000 -29501 = 315554 / 100 = 3155.54
        assert result["balance"] == 3155.54

    def test_savings_rate_uses_clean_figures(self, db):
        result = get_summary(db, start_date="2026-02-01", end_date="2026-02-28")
        # net = 2500 - 42.45 = 2457.55
        assert result["net"] == 2457.55
        # savings_rate = 2457.55 / 2500 * 100 = 98.3%
        assert result["savings_rate"] == 98.3

    def test_income_vs_expenses_excludes_transfers(self, db):
        rows = get_income_vs_expenses(
            db, months=1, start_date="2026-02-01", end_date="2026-02-28"
        )
        feb = next(r for r in rows if r["month"].startswith("Feb"))
        assert feb["income"] == 2500.00
        assert feb["expenses"] == 42.45

    def test_spending_by_category_omits_transfer_categories(self, db):
        rows = get_spending_by_category(db, start_date="2026-02-01", end_date="2026-02-28")
        categories_seen = {r["category"] for r in rows}
        assert "savings" not in categories_seen
        assert "transfers" not in categories_seen
        assert "bills" in categories_seen
        assert "groceries" in categories_seen

    def test_cash_flow_excludes_transfers(self, db):
        rows = get_cash_flow(
            db, months=1, start_date="2026-02-01", end_date="2026-02-28"
        )
        feb = next(r for r in rows if r["month"].startswith("Feb"))
        assert feb["income"] == 2500.00
        assert feb["expenses"] == 42.45
        assert feb["net"] == 2457.55

    def test_transfer_categories_constant(self):
        # Documents the contract — if this changes, KPI behaviour changes.
        assert TRANSFER_CATEGORIES == ("savings", "transfers")


# ---------------------------------------------------------------------------
# recategorize_transfers service function
# ---------------------------------------------------------------------------


class TestRecategorizeTransfers:
    def test_pot_transfer_moves_to_savings(self):
        db = _build_db()
        tx_id = _insert_tx(
            db, date="2026-02-16", name="Rainy day Pot", amount=-700,
            category="general", type_="Pot transfer",
        )

        result = recategorize_transfers(db)
        assert result["pot_transfers"] == 1
        assert result["total"] == 1

        row = db.execute("SELECT category FROM transactions WHERE id=?", (tx_id,)).fetchone()
        assert row["category"] == "savings"

    def test_flex_moves_to_transfers(self):
        db = _build_db()
        tx_id = _insert_tx(
            db, date="2026-03-01", name="Flex", amount=-29501,
            category="general", type_="Flex",
        )

        result = recategorize_transfers(db)
        assert result["flex_repayments"] == 1

        row = db.execute("SELECT category FROM transactions WHERE id=?", (tx_id,)).fetchone()
        assert row["category"] == "transfers"

    def test_moneybox_lisa_moves_to_savings(self):
        db = _build_db()
        tx_id = _insert_tx(
            db, date="2026-03-24", name="Moneybox Cash LISA", amount=-100000,
            category="general", type_="Faster payment",
        )

        result = recategorize_transfers(db)
        assert result["investment_providers"] == 1

        row = db.execute("SELECT category FROM transactions WHERE id=?", (tx_id,)).fetchone()
        assert row["category"] == "savings"

    def test_custom_category_is_preserved(self):
        db = _build_db()
        tx_id = _insert_tx(
            db, date="2026-02-16", name="Rainy day Pot", amount=-700,
            category="general", type_="Pot transfer", custom_category="bills",
        )

        result = recategorize_transfers(db)
        assert result["total"] == 0

        row = db.execute("SELECT category FROM transactions WHERE id=?", (tx_id,)).fetchone()
        assert row["category"] == "general"

    def test_idempotent_second_run_is_zero(self):
        db = _build_db()
        _insert_tx(
            db, date="2026-02-16", name="Rainy day Pot", amount=-700,
            category="general", type_="Pot transfer",
        )

        first = recategorize_transfers(db)
        second = recategorize_transfers(db)
        assert first["total"] == 1
        assert second["total"] == 0

    def test_regular_payment_untouched(self):
        db = _build_db()
        tx_id = _insert_tx(
            db, date="2026-02-05", name="Tesco", amount=-3450,
            category="groceries", type_="Card payment",
        )

        recategorize_transfers(db)
        row = db.execute("SELECT category FROM transactions WHERE id=?", (tx_id,)).fetchone()
        assert row["category"] == "groceries"

    def test_flex_positive_amount_untouched(self):
        # Returned-from-Flex (positive amount) is income, not a transfer.
        db = _build_db()
        tx_id = _insert_tx(
            db, date="2026-04-03", name="Traintickets.com", amount=570,
            category="income", type_="Flex",
        )

        result = recategorize_transfers(db)
        assert result["flex_repayments"] == 0

        row = db.execute("SELECT category FROM transactions WHERE id=?", (tx_id,)).fetchone()
        assert row["category"] == "income"
