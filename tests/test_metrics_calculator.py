"""Unit tests for app.services.metrics_calculator.

All functions under test are pure (no database, no Flask context), so no
fixtures are required.  Each test class covers one public function.
"""

import pytest

from app.services.metrics_calculator import (
    calculate_avg_duration_losers,
    calculate_avg_duration_winners,
    calculate_avg_loss,
    calculate_avg_r_multiple,
    calculate_avg_win,
    calculate_discipline_score,
    calculate_expectancy,
    calculate_largest_loss,
    calculate_largest_win,
    calculate_max_drawdown,
    calculate_pnl_distribution,
    calculate_profit_factor,
    calculate_streak_history,
    calculate_streaks,
    calculate_win_rate,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _trade(
    pnl_net,
    r_multiple=None,
    duration_minutes=None,
    rules_followed_pct=None,
    exit_date="2025-01-01T10:00:00",
):
    """Build a minimal closed-trade dict for testing."""
    return {
        "pnl_net": pnl_net,
        "r_multiple": r_multiple,
        "duration_minutes": duration_minutes,
        "rules_followed_pct": rules_followed_pct,
        "exit_date": exit_date,
    }


# ---------------------------------------------------------------------------
# calculate_win_rate
# ---------------------------------------------------------------------------


class TestCalculateWinRate:
    def test_empty_returns_none(self):
        assert calculate_win_rate([]) is None

    def test_all_wins(self):
        trades = [_trade(100), _trade(200), _trade(50)]
        assert calculate_win_rate(trades) == 100.0

    def test_all_losses(self):
        trades = [_trade(-100), _trade(-200)]
        assert calculate_win_rate(trades) == 0.0

    def test_mixed(self):
        # 2 wins, 1 loss, 1 breakeven → 2/4 × 100 = 50.0
        trades = [_trade(100), _trade(200), _trade(-50), _trade(0)]
        assert calculate_win_rate(trades) == 50.0

    def test_single_win(self):
        assert calculate_win_rate([_trade(100)]) == 100.0

    def test_single_loss(self):
        assert calculate_win_rate([_trade(-100)]) == 0.0

    def test_breakeven_counted_in_denominator(self):
        # 1 win + 1 breakeven → 1/2 × 100 = 50, not 100
        trades = [_trade(100), _trade(0)]
        assert calculate_win_rate(trades) == 50.0

    def test_returns_float(self):
        assert isinstance(calculate_win_rate([_trade(100)]), float)


# ---------------------------------------------------------------------------
# calculate_profit_factor
# ---------------------------------------------------------------------------


class TestCalculateProfitFactor:
    def test_empty_returns_none(self):
        assert calculate_profit_factor([]) is None

    def test_no_losses_returns_none(self):
        trades = [_trade(100), _trade(200)]
        assert calculate_profit_factor(trades) is None

    def test_no_wins_returns_none(self):
        trades = [_trade(-100), _trade(-200)]
        assert calculate_profit_factor(trades) is None

    def test_basic(self):
        # wins=1000, losses=-500 → 2.0
        trades = [_trade(600), _trade(400), _trade(-300), _trade(-200)]
        assert calculate_profit_factor(trades) == pytest.approx(2.0)

    def test_equal_wins_losses(self):
        trades = [_trade(500), _trade(-500)]
        assert calculate_profit_factor(trades) == pytest.approx(1.0)

    def test_breakeven_excluded(self):
        # 1 win 100p, 1 loss -100p, 1 breakeven 0p → PF = 1.0
        trades = [_trade(100), _trade(-100), _trade(0)]
        assert calculate_profit_factor(trades) == pytest.approx(1.0)

    def test_returns_float(self):
        trades = [_trade(200), _trade(-100)]
        assert isinstance(calculate_profit_factor(trades), float)


# ---------------------------------------------------------------------------
# calculate_expectancy
# ---------------------------------------------------------------------------


class TestCalculateExpectancy:
    def test_empty_returns_none(self):
        assert calculate_expectancy([]) is None

    def test_all_wins(self):
        # win_rate=1.0, avg_win=200, loss_rate=0 → 200
        trades = [_trade(200), _trade(200)]
        assert calculate_expectancy(trades) == 200

    def test_all_losses(self):
        # win_rate=0, loss_rate=1, avg_loss=-100 → -100
        trades = [_trade(-100), _trade(-100)]
        assert calculate_expectancy(trades) == -100

    def test_mixed(self):
        # 1 win 400p, 1 loss -200p
        # win_rate=0.5, avg_win=400, loss_rate=0.5, avg_loss=200
        # expectancy = 0.5×400 - 0.5×200 = 100
        trades = [_trade(400), _trade(-200)]
        assert calculate_expectancy(trades) == 100

    def test_breakeven_dilutes_total(self):
        # 1 win 300p, 1 loss -100p, 1 breakeven 0p (total=3)
        # win_rate=1/3, loss_rate=1/3
        # avg_win=300, avg_loss=100
        # expectancy = int(1/3×300 − 1/3×100) = int(66.67) = 66
        trades = [_trade(300), _trade(-100), _trade(0)]
        assert calculate_expectancy(trades) == 66

    def test_returns_int(self):
        assert isinstance(calculate_expectancy([_trade(100)]), int)


# ---------------------------------------------------------------------------
# calculate_avg_r_multiple
# ---------------------------------------------------------------------------


class TestCalculateAvgRMultiple:
    def test_empty_returns_none(self):
        assert calculate_avg_r_multiple([]) is None

    def test_all_none_r_returns_none(self):
        trades = [_trade(100), _trade(-100), _trade(50)]
        assert calculate_avg_r_multiple(trades) is None

    def test_basic(self):
        trades = [
            _trade(100, r_multiple=2.0),
            _trade(-50, r_multiple=-0.5),
            _trade(80, r_multiple=1.0),
        ]
        # (2.0 + -0.5 + 1.0) / 3 ≈ 0.8333
        assert calculate_avg_r_multiple(trades) == pytest.approx(0.8333, abs=1e-3)

    def test_excludes_none_r(self):
        trades = [
            _trade(100, r_multiple=2.0),
            _trade(50, r_multiple=None),
        ]
        assert calculate_avg_r_multiple(trades) == pytest.approx(2.0)

    def test_returns_float(self):
        assert isinstance(calculate_avg_r_multiple([_trade(100, r_multiple=1.5)]), float)


# ---------------------------------------------------------------------------
# calculate_max_drawdown
# ---------------------------------------------------------------------------


class TestCalculateMaxDrawdown:
    def test_empty_returns_none(self):
        assert calculate_max_drawdown([]) is None

    def test_all_wins_returns_zero(self):
        trades = [
            _trade(100, exit_date="2025-01-01T10:00:00"),
            _trade(200, exit_date="2025-01-02T10:00:00"),
            _trade(150, exit_date="2025-01-03T10:00:00"),
        ]
        assert calculate_max_drawdown(trades) == 0.0

    def test_all_losses_returns_zero(self):
        # Equity never goes positive → peak stays 0 → no drawdown measurable
        trades = [
            _trade(-100, exit_date="2025-01-01T10:00:00"),
            _trade(-200, exit_date="2025-01-02T10:00:00"),
            _trade(-300, exit_date="2025-01-03T10:00:00"),
        ]
        assert calculate_max_drawdown(trades) == 0.0

    def test_basic_drawdown(self):
        # Equity: 0 → 200 → 100 (peak=200, trough=100) → DD = 50%
        trades = [
            _trade(200, exit_date="2025-01-01T10:00:00"),
            _trade(-100, exit_date="2025-01-02T10:00:00"),
        ]
        assert calculate_max_drawdown(trades) == pytest.approx(50.0)

    def test_recover_then_larger_drawdown(self):
        # Equity: 0 → 100 → 300 → 150 → 250 → -50 (from peak 300)
        # Peak=300, lowest subsequent=200 (300+(-100))=200 → DD=(300-200)/300×100=33.33%
        # Then drops further: 200+100=300 (new peak), -50 means 300-50=250 wait let me recalculate
        # trades: +100, +200, -150, +100 → cumulative: 100, 300, 150, 250
        # peak=300, trough=150 → DD=(300-150)/300×100=50%
        trades = [
            _trade(100, exit_date="2025-01-01T10:00:00"),
            _trade(200, exit_date="2025-01-02T10:00:00"),
            _trade(-150, exit_date="2025-01-03T10:00:00"),
            _trade(100, exit_date="2025-01-04T10:00:00"),
        ]
        assert calculate_max_drawdown(trades) == pytest.approx(50.0)

    def test_single_win(self):
        assert calculate_max_drawdown([_trade(100)]) == 0.0

    def test_single_loss(self):
        # Peak never exceeds 0 → 0.0
        assert calculate_max_drawdown([_trade(-100)]) == 0.0

    def test_returns_float(self):
        trades = [_trade(200, exit_date="2025-01-01T10:00:00"),
                  _trade(-100, exit_date="2025-01-02T10:00:00")]
        assert isinstance(calculate_max_drawdown(trades), float)

    def test_uses_exit_date_order(self):
        # List order: win, win, loss → max_dd would be small
        # exit_date order: loss, win, win → peak never exceeded before loss → 0.0
        trades = [
            _trade(200, exit_date="2025-01-03T10:00:00"),
            _trade(200, exit_date="2025-01-04T10:00:00"),
            _trade(-100, exit_date="2025-01-01T10:00:00"),  # chronologically first
        ]
        # Chronological: -100, +200, +200 → cumulative: -100, 100, 300
        # peak at -100 step: 0 (peak never > 0 yet); at 100: peak=100, dd=0;
        # at 300: peak=300, dd=0 → result=0.0
        assert calculate_max_drawdown(trades) == 0.0


# ---------------------------------------------------------------------------
# calculate_streaks
# ---------------------------------------------------------------------------


class TestCalculateStreaks:
    def test_empty(self):
        assert calculate_streaks([]) == (0, 0)

    def test_all_wins(self):
        trades = [_trade(100), _trade(200), _trade(50), _trade(80), _trade(10)]
        max_wins, max_losses = calculate_streaks(trades)
        assert max_wins == 5
        assert max_losses == 0

    def test_all_losses(self):
        trades = [_trade(-100), _trade(-200), _trade(-50), _trade(-80)]
        max_wins, max_losses = calculate_streaks(trades)
        assert max_wins == 0
        assert max_losses == 4

    def test_mixed(self):
        # W, W, L, L, L, W → max_wins=2, max_losses=3
        trades = [
            _trade(100, exit_date="2025-01-01T10:00:00"),
            _trade(100, exit_date="2025-01-02T10:00:00"),
            _trade(-50, exit_date="2025-01-03T10:00:00"),
            _trade(-50, exit_date="2025-01-04T10:00:00"),
            _trade(-50, exit_date="2025-01-05T10:00:00"),
            _trade(100, exit_date="2025-01-06T10:00:00"),
        ]
        assert calculate_streaks(trades) == (2, 3)

    def test_breakeven_resets_win_streak(self):
        # W, W, B, W → max_wins=2, not 3
        trades = [
            _trade(100, exit_date="2025-01-01T10:00:00"),
            _trade(100, exit_date="2025-01-02T10:00:00"),
            _trade(0,   exit_date="2025-01-03T10:00:00"),
            _trade(100, exit_date="2025-01-04T10:00:00"),
        ]
        max_wins, max_losses = calculate_streaks(trades)
        assert max_wins == 2

    def test_breakeven_resets_loss_streak(self):
        # L, L, B, L → max_losses=2, not 3
        trades = [
            _trade(-100, exit_date="2025-01-01T10:00:00"),
            _trade(-100, exit_date="2025-01-02T10:00:00"),
            _trade(0,    exit_date="2025-01-03T10:00:00"),
            _trade(-100, exit_date="2025-01-04T10:00:00"),
        ]
        max_wins, max_losses = calculate_streaks(trades)
        assert max_losses == 2

    def test_single_win(self):
        assert calculate_streaks([_trade(100)]) == (1, 0)

    def test_single_loss(self):
        assert calculate_streaks([_trade(-100)]) == (0, 1)

    def test_ordered_by_exit_date(self):
        # List order would give W, W, W → streak of 3
        # exit_date order: W, L, W, W → streak of 2
        trades = [
            _trade(100, exit_date="2025-01-03T10:00:00"),
            _trade(100, exit_date="2025-01-01T10:00:00"),
            _trade(-50, exit_date="2025-01-02T10:00:00"),
            _trade(100, exit_date="2025-01-04T10:00:00"),
        ]
        max_wins, _ = calculate_streaks(trades)
        assert max_wins == 2


# ---------------------------------------------------------------------------
# calculate_avg_win
# ---------------------------------------------------------------------------


class TestCalculateAvgWin:
    def test_empty_returns_none(self):
        assert calculate_avg_win([]) is None

    def test_no_wins_returns_none(self):
        trades = [_trade(-100), _trade(-200)]
        assert calculate_avg_win(trades) is None

    def test_basic(self):
        trades = [_trade(200), _trade(300)]
        assert calculate_avg_win(trades) == 250

    def test_breakeven_excluded(self):
        trades = [_trade(100), _trade(0), _trade(-100)]
        assert calculate_avg_win(trades) == 100

    def test_integer_truncation(self):
        # 100 + 100 + 101 = 301 / 3 = 100.33 → truncated to 100
        trades = [_trade(100), _trade(100), _trade(101)]
        assert calculate_avg_win(trades) == 100

    def test_returns_int(self):
        assert isinstance(calculate_avg_win([_trade(100)]), int)


# ---------------------------------------------------------------------------
# calculate_avg_loss
# ---------------------------------------------------------------------------


class TestCalculateAvgLoss:
    def test_empty_returns_none(self):
        assert calculate_avg_loss([]) is None

    def test_no_losses_returns_none(self):
        trades = [_trade(100), _trade(200)]
        assert calculate_avg_loss(trades) is None

    def test_basic(self):
        trades = [_trade(-100), _trade(-200)]
        assert calculate_avg_loss(trades) == -150

    def test_breakeven_excluded(self):
        trades = [_trade(100), _trade(0), _trade(-100)]
        assert calculate_avg_loss(trades) == -100

    def test_integer_truncation(self):
        # -100 + -100 + -101 = -301 / 3 = -100.33 → truncated to -100
        trades = [_trade(-100), _trade(-100), _trade(-101)]
        assert calculate_avg_loss(trades) == -100

    def test_returns_int(self):
        assert isinstance(calculate_avg_loss([_trade(-100)]), int)


# ---------------------------------------------------------------------------
# calculate_largest_win
# ---------------------------------------------------------------------------


class TestCalculateLargestWin:
    def test_empty_returns_none(self):
        assert calculate_largest_win([]) is None

    def test_basic(self):
        trades = [_trade(100), _trade(500), _trade(300)]
        assert calculate_largest_win(trades) == 500

    def test_mixed_signs(self):
        trades = [_trade(100), _trade(-500), _trade(300)]
        assert calculate_largest_win(trades) == 300

    def test_all_losses(self):
        trades = [_trade(-100), _trade(-200)]
        assert calculate_largest_win(trades) == -100  # max of negatives

    def test_returns_int(self):
        assert isinstance(calculate_largest_win([_trade(100)]), int)


# ---------------------------------------------------------------------------
# calculate_largest_loss
# ---------------------------------------------------------------------------


class TestCalculateLargestLoss:
    def test_empty_returns_none(self):
        assert calculate_largest_loss([]) is None

    def test_basic(self):
        trades = [_trade(-100), _trade(-500), _trade(-300)]
        assert calculate_largest_loss(trades) == -500

    def test_mixed_signs(self):
        trades = [_trade(100), _trade(-500), _trade(300)]
        assert calculate_largest_loss(trades) == -500

    def test_all_wins(self):
        trades = [_trade(100), _trade(200)]
        assert calculate_largest_loss(trades) == 100  # min of positives

    def test_returns_int(self):
        assert isinstance(calculate_largest_loss([_trade(-100)]), int)


# ---------------------------------------------------------------------------
# calculate_avg_duration_winners
# ---------------------------------------------------------------------------


class TestCalculateAvgDurationWinners:
    def test_empty_returns_none(self):
        assert calculate_avg_duration_winners([]) is None

    def test_no_wins_returns_none(self):
        trades = [_trade(-100, duration_minutes=60)]
        assert calculate_avg_duration_winners(trades) is None

    def test_basic(self):
        trades = [
            _trade(100, duration_minutes=60),
            _trade(200, duration_minutes=120),
        ]
        assert calculate_avg_duration_winners(trades) == pytest.approx(90.0)

    def test_excludes_none_duration(self):
        trades = [
            _trade(100, duration_minutes=60),
            _trade(200, duration_minutes=None),
        ]
        assert calculate_avg_duration_winners(trades) == pytest.approx(60.0)

    def test_losers_excluded(self):
        trades = [
            _trade(100, duration_minutes=60),
            _trade(-100, duration_minutes=120),
        ]
        assert calculate_avg_duration_winners(trades) == pytest.approx(60.0)

    def test_returns_float(self):
        result = calculate_avg_duration_winners([_trade(100, duration_minutes=60)])
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# calculate_avg_duration_losers
# ---------------------------------------------------------------------------


class TestCalculateAvgDurationLosers:
    def test_empty_returns_none(self):
        assert calculate_avg_duration_losers([]) is None

    def test_no_losses_returns_none(self):
        trades = [_trade(100, duration_minutes=60)]
        assert calculate_avg_duration_losers(trades) is None

    def test_basic(self):
        trades = [
            _trade(-100, duration_minutes=30),
            _trade(-200, duration_minutes=90),
        ]
        assert calculate_avg_duration_losers(trades) == pytest.approx(60.0)

    def test_excludes_none_duration(self):
        trades = [
            _trade(-100, duration_minutes=30),
            _trade(-200, duration_minutes=None),
        ]
        assert calculate_avg_duration_losers(trades) == pytest.approx(30.0)

    def test_winners_excluded(self):
        trades = [
            _trade(-100, duration_minutes=30),
            _trade(100, duration_minutes=120),
        ]
        assert calculate_avg_duration_losers(trades) == pytest.approx(30.0)

    def test_returns_float(self):
        result = calculate_avg_duration_losers([_trade(-100, duration_minutes=60)])
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# calculate_discipline_score
# ---------------------------------------------------------------------------


class TestCalculateDisciplineScore:
    def test_empty_returns_none(self):
        assert calculate_discipline_score([]) is None

    def test_all_none_returns_none(self):
        trades = [_trade(100), _trade(-100), _trade(50)]
        assert calculate_discipline_score(trades) is None

    def test_basic(self):
        trades = [
            _trade(100, rules_followed_pct=80.0),
            _trade(-50, rules_followed_pct=90.0),
        ]
        assert calculate_discipline_score(trades) == pytest.approx(85.0)

    def test_partial_none(self):
        trades = [
            _trade(100, rules_followed_pct=80.0),
            _trade(-50, rules_followed_pct=None),
            _trade(200, rules_followed_pct=100.0),
        ]
        assert calculate_discipline_score(trades) == pytest.approx(90.0)

    def test_rounding(self):
        trades = [
            _trade(100, rules_followed_pct=66.6),
            _trade(100, rules_followed_pct=66.6),
            _trade(100, rules_followed_pct=66.6),
        ]
        assert calculate_discipline_score(trades) == pytest.approx(66.6, abs=0.1)

    def test_returns_float(self):
        result = calculate_discipline_score([_trade(100, rules_followed_pct=75.0)])
        assert isinstance(result, float)


class TestCalculatePnlDistribution:
    def test_empty_returns_empty(self):
        result = calculate_pnl_distribution([])
        assert result == {"bins": [], "total": 0}

    def test_single_trade(self):
        result = calculate_pnl_distribution([10000])
        assert result["total"] == 1
        assert len(result["bins"]) == 1
        assert result["bins"][0]["count"] == 1

    def test_all_same_value(self):
        result = calculate_pnl_distribution([5000, 5000, 5000])
        assert result["total"] == 3
        assert len(result["bins"]) == 1
        assert result["bins"][0]["count"] == 3

    def test_all_losses(self):
        values = [-30000, -20000, -10000, -5000, -1000]
        result = calculate_pnl_distribution(values)
        assert result["total"] == 5
        for b in result["bins"]:
            assert b["midpoint"] < 0

    def test_all_wins(self):
        values = [1000, 5000, 10000, 20000, 30000]
        result = calculate_pnl_distribution(values)
        assert result["total"] == 5
        for b in result["bins"]:
            assert b["midpoint"] > 0

    def test_mixed_signs_has_both_sides(self):
        values = [-20000, -10000, 0, 10000, 20000]
        result = calculate_pnl_distribution(values)
        has_loss_bin = any(b["midpoint"] < 0 for b in result["bins"])
        has_win_bin = any(b["midpoint"] > 0 for b in result["bins"])
        assert has_loss_bin
        assert has_win_bin

    def test_total_equals_input_length(self):
        values = [-500, -100, 0, 200, 800, 1500]
        result = calculate_pnl_distribution(values)
        assert result["total"] == len(values)

    def test_count_sum_equals_total(self):
        values = [-300, -100, 100, 200, 500, 1000, 1500, -50]
        result = calculate_pnl_distribution(values)
        assert sum(b["count"] for b in result["bins"]) == result["total"]

    def test_bin_count_capped_at_20(self):
        # 1000 distinct values — Sturges would give >20 without the cap
        values = list(range(-50000, 50000, 100))  # 1000 values
        result = calculate_pnl_distribution(values)
        assert len(result["bins"]) <= 20

    def test_midpoints_are_decimal_pounds(self):
        # 1000p = £10.00; midpoint should be in pounds range, not pence
        values = [80000, 90000, 100000, 110000, 120000]
        result = calculate_pnl_distribution(values)
        for b in result["bins"]:
            assert abs(b["midpoint"]) < 10000  # not in pence (would be ~100000)

    def test_bins_have_required_keys(self):
        result = calculate_pnl_distribution([10000, 20000, -5000])
        for b in result["bins"]:
            assert "label" in b
            assert "min" in b
            assert "max" in b
            assert "count" in b
            assert "midpoint" in b

    def test_negative_single_trade(self):
        result = calculate_pnl_distribution([-7500])
        assert result["total"] == 1


# ---------------------------------------------------------------------------
# calculate_streak_history
# ---------------------------------------------------------------------------


class TestCalculateStreakHistory:
    def _t(self, pnl_net, exit_date="2024-01-01", id_=1):
        return {"pnl_net": pnl_net, "exit_date": exit_date, "id": id_}

    def test_empty(self):
        r = calculate_streak_history([])
        assert r == {"runs": [], "current_streak": {"type": None, "count": 0}, "total_trades": 0}

    def test_all_wins(self):
        trades = [self._t(100, f"2024-01-0{i}", i) for i in range(1, 4)]
        r = calculate_streak_history(trades)
        assert r["runs"] == [
            {"type": "win", "count": 3, "start_date": "2024-01-01", "end_date": "2024-01-03"}
        ]
        assert r["current_streak"] == {"type": "win", "count": 3}
        assert r["total_trades"] == 3

    def test_all_losses(self):
        trades = [self._t(-100, f"2024-01-0{i}", i) for i in range(1, 4)]
        r = calculate_streak_history(trades)
        assert len(r["runs"]) == 1
        assert r["runs"][0]["type"] == "loss"
        assert r["runs"][0]["count"] == 3

    def test_win_then_loss(self):
        trades = [
            self._t(100, "2024-01-01", 1), self._t(100, "2024-01-02", 2),
            self._t(-50, "2024-01-03", 3), self._t(-50, "2024-01-04", 4), self._t(-50, "2024-01-05", 5),
        ]
        r = calculate_streak_history(trades)
        assert len(r["runs"]) == 2
        assert r["runs"][0] == {"type": "win",  "count": 2, "start_date": "2024-01-01", "end_date": "2024-01-02"}
        assert r["runs"][1] == {"type": "loss", "count": 3, "start_date": "2024-01-03", "end_date": "2024-01-05"}

    def test_breakeven_is_own_run(self):
        trades = [
            self._t(100, "2024-01-01", 1), self._t(100, "2024-01-02", 2),
            self._t(0,   "2024-01-03", 3), self._t(100, "2024-01-04", 4),
        ]
        r = calculate_streak_history(trades)
        assert len(r["runs"]) == 3
        assert r["runs"][1] == {"type": "breakeven", "count": 1, "start_date": "2024-01-03", "end_date": "2024-01-03"}
        assert r["runs"][2] == {"type": "win", "count": 1, "start_date": "2024-01-04", "end_date": "2024-01-04"}

    def test_pnl_none_is_breakeven(self):
        trades = [self._t(None, "2024-01-01", 1)]
        r = calculate_streak_history(trades)
        assert r["runs"][0]["type"] == "breakeven"
        assert r["runs"][0]["count"] == 1

    def test_current_streak_is_last_run(self):
        trades = [
            self._t(100, "2024-01-01", 1), self._t(-50, "2024-01-02", 2), self._t(-50, "2024-01-03", 3),
        ]
        r = calculate_streak_history(trades)
        assert r["current_streak"] == {"type": "loss", "count": 2}

    def test_ordered_by_exit_date(self):
        # Passed in reverse order — should sort to loss, win, win
        trades = [
            self._t(100, "2024-01-03", 3), self._t(-50, "2024-01-01", 1), self._t(100, "2024-01-02", 2),
        ]
        r = calculate_streak_history(trades)
        assert r["runs"][0]["type"] == "loss"
        assert r["runs"][1]["type"] == "win"

    def test_total_trades(self):
        trades = [self._t(100, f"2024-01-0{i}", i) for i in range(1, 6)]
        assert calculate_streak_history(trades)["total_trades"] == 5

    def test_multiple_breakeven_each_own_run(self):
        trades = [self._t(0, "2024-01-01", 1), self._t(0, "2024-01-02", 2)]
        r = calculate_streak_history(trades)
        assert len(r["runs"]) == 2
        assert all(run["type"] == "breakeven" for run in r["runs"])
