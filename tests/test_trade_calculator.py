"""Unit tests for app.services.trade_calculator.

All functions under test are pure, so no database or Flask context is
required.  Tests use round pence values to make expected results
immediately obvious.
"""

import pytest

from app.services.trade_calculator import (
    calculate_duration_minutes,
    calculate_gross_pnl,
    calculate_net_pnl,
    calculate_pnl_percentage,
    calculate_r_multiple,
)


# ---------------------------------------------------------------------------
# calculate_gross_pnl
# ---------------------------------------------------------------------------


class TestCalculateGrossPnl:
    def test_long_profit(self):
        # entry £100 (10_000p), exit £110 (11_000p), 10 units
        # profit per unit = 1_000p, total = 10_000p (£100)
        assert calculate_gross_pnl(10_000, 11_000, 10.0, "long") == 10_000

    def test_long_loss(self):
        # entry £110, exit £100, 10 units → -10_000p loss
        assert calculate_gross_pnl(11_000, 10_000, 10.0, "long") == -10_000

    def test_long_breakeven(self):
        assert calculate_gross_pnl(10_000, 10_000, 10.0, "long") == 0

    def test_short_profit(self):
        # Short: entry £110, exit £100, 10 units → 10_000p profit
        assert calculate_gross_pnl(11_000, 10_000, 10.0, "short") == 10_000

    def test_short_loss(self):
        # Short: entry £100, exit £110, 10 units → -10_000p loss
        assert calculate_gross_pnl(10_000, 11_000, 10.0, "short") == -10_000

    def test_fractional_position(self):
        # 0.5 units, £200 move per unit → £100 profit = 10_000p
        assert calculate_gross_pnl(10_000, 30_000, 0.5, "long") == 10_000

    def test_direction_case_insensitive(self):
        assert calculate_gross_pnl(10_000, 11_000, 1.0, "LONG") == 1_000
        assert calculate_gross_pnl(11_000, 10_000, 1.0, "SHORT") == 1_000

    def test_invalid_direction_raises(self):
        with pytest.raises(ValueError, match="long.*short"):
            calculate_gross_pnl(10_000, 11_000, 1.0, "sideways")

    def test_result_is_int(self):
        result = calculate_gross_pnl(10_000, 11_000, 10.0, "long")
        assert isinstance(result, int)

    def test_rounding(self):
        # 3 units × 1p diff → 3p exactly (no rounding ambiguity)
        assert calculate_gross_pnl(10_000, 10_001, 3.0, "long") == 3


# ---------------------------------------------------------------------------
# calculate_net_pnl
# ---------------------------------------------------------------------------


class TestCalculateNetPnl:
    def test_both_fees(self):
        # gross=£1000, entry_fee=£5, exit_fee=£5 → net=£990
        assert calculate_net_pnl(100_000, 500, 500) == 99_000

    def test_zero_fees(self):
        assert calculate_net_pnl(100_000, 0, 0) == 100_000

    def test_entry_fee_only(self):
        assert calculate_net_pnl(100_000, 500, 0) == 99_500

    def test_exit_fee_only(self):
        assert calculate_net_pnl(100_000, 0, 500) == 99_500

    def test_fees_exceed_profit(self):
        assert calculate_net_pnl(500, 300, 300) == -100

    def test_loss_with_fees(self):
        # Already losing; fees make it worse
        assert calculate_net_pnl(-50_000, 500, 500) == -51_000

    def test_result_is_int(self):
        result = calculate_net_pnl(100_000, 500, 500)
        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# calculate_pnl_percentage
# ---------------------------------------------------------------------------


class TestCalculatePnlPercentage:
    def test_basic_profit(self):
        # net=£100 (10_000p), entry=£100 (10_000p), size=1.0 → 100%
        assert calculate_pnl_percentage(10_000, 10_000, 1.0) == pytest.approx(100.0)

    def test_uses_net_not_gross(self):
        # Key bug-coverage test.
        # net=9_000p (£90), entry=10_000p (£100), size=10.0 → 9%
        # If gross (10_000p) were used instead the result would be 10%.
        result = calculate_pnl_percentage(9_000, 10_000, 10.0)
        assert result == pytest.approx(9.0)
        assert result != pytest.approx(10.0)

    def test_zero_entry_price_returns_none(self):
        assert calculate_pnl_percentage(10_000, 0, 10.0) is None

    def test_zero_position_size_returns_none(self):
        assert calculate_pnl_percentage(10_000, 10_000, 0.0) is None

    def test_loss_is_negative_percentage(self):
        result = calculate_pnl_percentage(-10_000, 10_000, 1.0)
        assert result == pytest.approx(-100.0)

    def test_partial_gain(self):
        # net=£5 (500p), entry=£100 (10_000p), size=1.0 → 5%
        assert calculate_pnl_percentage(500, 10_000, 1.0) == pytest.approx(5.0)

    def test_result_is_float(self):
        result = calculate_pnl_percentage(10_000, 10_000, 1.0)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# calculate_r_multiple
# ---------------------------------------------------------------------------


class TestCalculateRMultiple:
    def test_two_r_profit(self):
        # net=20_000p risk=10_000p → 2.0R
        assert calculate_r_multiple(20_000, 10_000) == pytest.approx(2.0)

    def test_fractional_loss(self):
        # net=-5_000p risk=10_000p → -0.5R
        assert calculate_r_multiple(-5_000, 10_000) == pytest.approx(-0.5)

    def test_none_risk_returns_none(self):
        assert calculate_r_multiple(20_000, None) is None

    def test_zero_risk_returns_none(self):
        assert calculate_r_multiple(20_000, 0) is None

    def test_one_r(self):
        assert calculate_r_multiple(10_000, 10_000) == pytest.approx(1.0)

    def test_result_is_float(self):
        result = calculate_r_multiple(20_000, 10_000)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# calculate_duration_minutes
# ---------------------------------------------------------------------------


class TestCalculateDurationMinutes:
    def test_ninety_minutes(self):
        assert calculate_duration_minutes(
            "2025-01-15T09:00:00", "2025-01-15T10:30:00"
        ) == 90

    def test_same_datetime_is_zero(self):
        assert calculate_duration_minutes(
            "2025-01-15T09:00:00", "2025-01-15T09:00:00"
        ) == 0

    def test_multi_day(self):
        # 2 full days = 2880 minutes
        assert calculate_duration_minutes(
            "2025-01-13T09:00:00", "2025-01-15T09:00:00"
        ) == 2880

    def test_truncation_not_rounding(self):
        # 89 min 59 sec → should truncate to 89, not round to 90
        assert calculate_duration_minutes(
            "2025-01-15T09:00:00", "2025-01-15T10:29:59"
        ) == 89

    def test_invalid_entry_date_returns_none(self):
        assert calculate_duration_minutes("not-a-date", "2025-01-15T10:00:00") is None

    def test_invalid_exit_date_returns_none(self):
        assert calculate_duration_minutes("2025-01-15T09:00:00", "not-a-date") is None

    def test_none_entry_returns_none(self):
        assert calculate_duration_minutes(None, "2025-01-15T10:00:00") is None

    def test_none_exit_returns_none(self):
        assert calculate_duration_minutes("2025-01-15T09:00:00", None) is None

    def test_date_only_strings(self):
        # Date-only ISO strings are valid — midnight assumed
        assert calculate_duration_minutes("2025-01-15", "2025-01-16") == 1440

    def test_whitespace_stripped(self):
        assert calculate_duration_minutes(
            "2025-01-15T09:00:00", "  2025-01-15T10:30:00  "
        ) == 90

    def test_result_is_int(self):
        result = calculate_duration_minutes(
            "2025-01-15T09:00:00", "2025-01-15T10:30:00"
        )
        assert isinstance(result, int)
