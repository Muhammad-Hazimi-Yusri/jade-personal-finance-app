"""Generate demo-data/seed.sql for the Jade demo instance.

Deterministic — ``random.seed(42)`` fixes every choice so the committed
``seed.sql`` is byte-stable across runs.

Run from the project root::

    python demo-data/generate_seed.py

The generated seed assumes the target database has already been migrated
and that :func:`app.db.init_db` has seeded the default categories and
import profiles — this script only populates the domain tables.
"""

from __future__ import annotations

import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.trade_calculator import (  # noqa: E402
    calculate_duration_minutes,
    calculate_gross_pnl,
    calculate_net_pnl,
    calculate_pnl_percentage,
    calculate_r_multiple,
)

RNG = random.Random(42)
TODAY = date(2026, 4, 15)
TX_START = date(2025, 10, 15)
TRADE_START = date(2025, 11, 3)
JOURNAL_START = date(2026, 1, 15)
SNAPSHOT_START = date(2025, 11, 1)

OUTPUT_PATH = ROOT / "demo-data" / "seed.sql"


# ---------------------------------------------------------------------------
# SQL helpers
# ---------------------------------------------------------------------------

def sql_lit(value: Any) -> str:
    """Render a Python value as a SQL literal."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value:  # NaN
            return "NULL"
        return repr(round(value, 6))
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def insert_batch(table: str, columns: list[str], rows: list[tuple]) -> str:
    """Build one multi-row INSERT statement for `rows`."""
    if not rows:
        return ""
    col_list = ", ".join(columns)
    values_sql = ",\n    ".join("(" + ", ".join(sql_lit(v) for v in row) + ")" for row in rows)
    return f"INSERT INTO {table} ({col_list}) VALUES\n    {values_sql};\n"


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

MERCHANTS = {
    "groceries": [
        ("Tesco", "🛒", 8, 65),
        ("Sainsbury's", "🛒", 10, 70),
        ("Lidl", "🛒", 6, 45),
        ("M&S Food", "🛒", 12, 55),
        ("Waitrose", "🛒", 15, 80),
        ("Co-op", "🛒", 5, 35),
    ],
    "eating_out": [
        ("Pret A Manger", "🥪", 4, 15),
        ("Nando's", "🍗", 14, 35),
        ("Wagamama", "🍜", 15, 40),
        ("Itsu", "🍣", 7, 18),
        ("Costa Coffee", "☕", 3, 8),
        ("Greggs", "🥐", 2, 8),
        ("Dishoom", "🍛", 25, 55),
        ("Franco Manca", "🍕", 12, 28),
    ],
    "transport": [
        ("TfL Travel", "🚇", 2, 8),
        ("Uber", "🚗", 5, 40),
        ("Trainline", "🚆", 8, 85),
        ("Shell", "⛽", 35, 75),
    ],
    "shopping": [
        ("Amazon", "📦", 10, 180),
        ("Zara", "🛍️", 20, 120),
        ("Uniqlo", "🛍️", 15, 90),
        ("Apple", "📱", 50, 250),
        ("John Lewis", "🛍️", 25, 200),
    ],
    "entertainment": [
        ("Odeon Cinema", "🎬", 10, 22),
        ("Vue Cinema", "🎬", 9, 20),
        ("Steam", "🎮", 8, 45),
        ("Ticketmaster", "🎫", 25, 95),
    ],
    "holidays": [
        ("Ryanair", "✈️", 45, 180),
        ("Booking.com", "🏨", 80, 400),
        ("Airbnb", "🏡", 100, 350),
        ("British Airways", "✈️", 120, 450),
    ],
    "personal_care": [
        ("Boots", "💊", 5, 30),
        ("Superdrug", "💊", 4, 25),
        ("Toni & Guy", "✂️", 25, 60),
    ],
}

# (name, emoji, amount_pence, category, day_of_month)
FIXED_BILLS = [
    ("Property Mgmt", "🏠", 110000, "bills", 1),
    ("Netflix", "📺", 1099, "entertainment", 15),
    ("Spotify", "🎵", 1099, "entertainment", 15),
    ("PureGym", "🏋️", 3200, "personal_care", 5),
    ("EE Mobile", "📱", 2000, "bills", 8),
    ("Thames Water", "💧", 3500, "bills", 20),
    ("Octopus Energy", "⚡", 8500, "bills", 22),
    ("Council Tax", "📄", 14500, "bills", 25),
]


def month_iter(start: date, end: date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


def gen_transactions() -> list[dict]:
    rows: list[dict] = []

    def push(d: date, name: str, emoji: str, category: str,
             amount_pence: int, is_income: int = 0,
             ttype: str = "Card payment") -> None:
        hour = RNG.randint(7, 22)
        minute = RNG.randint(0, 59)
        iso = f"{d.isoformat()}T{hour:02d}:{minute:02d}:00Z"
        rows.append({
            "date": iso,
            "type": ttype,
            "name": name,
            "emoji": emoji,
            "category": category,
            "amount": amount_pence,
            "currency": "GBP",
            "is_income": is_income,
        })

    # Monthly salary + fixed bills + weekly savings
    for y, m in month_iter(TX_START, TODAY):
        try:
            salary_d = date(y, m, 28)
        except ValueError:
            salary_d = date(y, m, 1)
        if TX_START <= salary_d <= TODAY:
            push(salary_d, "Acme Ltd Payroll", "💼", "income",
                 RNG.randint(270000, 290000), is_income=1, ttype="Faster payment")

        for name, emoji, amount, category, dom in FIXED_BILLS:
            try:
                bill_d = date(y, m, dom)
            except ValueError:
                continue
            if bill_d < TX_START or bill_d > TODAY:
                continue
            jitter = RNG.randint(-500, 800) if name in ("Thames Water", "Octopus Energy") else 0
            push(bill_d, name, emoji, category, -(amount + jitter), ttype="Direct debit")

        for dom in (5, 12, 19, 26):
            try:
                sv_d = date(y, m, dom)
            except ValueError:
                continue
            if sv_d < TX_START or sv_d > TODAY:
                continue
            push(sv_d, "Savings Pot Transfer", "🏦", "savings",
                 -RNG.randint(15000, 40000), ttype="Faster payment")

    # Daily discretionary
    cur = TX_START
    while cur <= TODAY:
        weekday = cur.weekday()

        if RNG.random() < 0.50:
            name, emoji, lo, hi = RNG.choice(MERCHANTS["groceries"])
            push(cur, name, emoji, "groceries", -RNG.randint(lo * 100, hi * 100))

        n_eat = RNG.choices([0, 1, 2], weights=[20, 60, 20])[0]
        for _ in range(n_eat):
            name, emoji, lo, hi = RNG.choice(MERCHANTS["eating_out"])
            push(cur, name, emoji, "eating_out", -RNG.randint(lo * 100, hi * 100))

        if RNG.random() < (0.65 if weekday < 5 else 0.25):
            name, emoji, lo, hi = RNG.choice(MERCHANTS["transport"])
            push(cur, name, emoji, "transport", -RNG.randint(lo * 100, hi * 100))

        if RNG.random() < 0.13:
            name, emoji, lo, hi = RNG.choice(MERCHANTS["shopping"])
            push(cur, name, emoji, "shopping", -RNG.randint(lo * 100, hi * 100))

        if RNG.random() < 0.09:
            name, emoji, lo, hi = RNG.choice(MERCHANTS["entertainment"])
            push(cur, name, emoji, "entertainment", -RNG.randint(lo * 100, hi * 100))

        if RNG.random() < 0.06:
            name, emoji, lo, hi = RNG.choice(MERCHANTS["personal_care"])
            push(cur, name, emoji, "personal_care", -RNG.randint(lo * 100, hi * 100))

        cur += timedelta(days=1)

    # Occasional holidays
    for y, m in [(2025, 11), (2026, 2), (2026, 4)]:
        try:
            hd = date(y, m, RNG.randint(5, 25))
        except ValueError:
            continue
        if hd < TX_START or hd > TODAY:
            continue
        name, emoji, lo, hi = RNG.choice(MERCHANTS["holidays"])
        push(hd, name, emoji, "holidays", -RNG.randint(lo * 100, hi * 100))

    rows.sort(key=lambda r: r["date"])
    for i, r in enumerate(rows, start=1):
        r["monzo_id"] = f"demo_tx_{i:06d}"
    return rows


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------

ASSET_POOL = [
    ("stocks", ["AAPL", "MSFT", "TSLA", "NVDA", "META", "AMZN"], 55),
    ("forex",  ["EURUSD", "GBPUSD", "USDJPY"], 20),
    ("crypto", ["BTCUSD", "ETHUSD"], 15),
    ("options", ["SPY 500C", "SPY 495P", "QQQ 420C"], 10),
]

TIMEFRAMES = ["15m", "1h", "4h", "D"]
SETUPS = ["breakout", "pullback", "reversal", "news"]
CONDITIONS = ["trending", "ranging", "volatile", "choppy"]
ENTRY_REASONS = [
    "Clean breakout above consolidation on rising volume",
    "Pullback to 20-EMA with bullish confirmation candle",
    "Double bottom reversal at key support",
    "News-driven momentum after strong earnings beat",
    "Trend continuation after bull flag resolution",
    "Mean reversion from oversold RSI in ranging market",
]
EXIT_REASONS = [
    "Target hit at resistance",
    "Stopped out on adverse move",
    "Time-based exit ahead of weekend",
    "Trailing stop triggered",
    "Closed on exhaustion candle",
    "Scaled out into strength",
]


def pick_asset() -> tuple[str, str]:
    classes = [a for a, _, _ in ASSET_POOL]
    weights = [w for _, _, w in ASSET_POOL]
    asset = RNG.choices(classes, weights=weights)[0]
    symbols = {a: s for a, s, _ in ASSET_POOL}[asset]
    return asset, RNG.choice(symbols)


def nominal_for(asset_class: str) -> tuple[int, float]:
    """Return a (entry_price_pence, position_size) that gives a reasonable notional."""
    if asset_class == "stocks":
        entry = RNG.randint(5000, 40000)        # £50 – £400 per share
        size = float(RNG.randint(20, 150))
    elif asset_class == "forex":
        entry = RNG.randint(110000, 140000)     # ~1.10 – 1.40 quoted as pence
        size = float(RNG.randint(1, 5))         # mini lots
    elif asset_class == "crypto":
        entry = RNG.randint(1500000, 5000000)   # £15k – £50k per unit
        size_choices = [0.05, 0.1, 0.15, 0.25, 0.5]
        size = RNG.choice(size_choices)
    else:  # options
        entry = RNG.randint(200, 1500)          # £2 – £15 per contract
        size = float(RNG.randint(5, 30))
    return entry, size


def gen_trades() -> list[dict]:
    trades: list[dict] = []

    # Closed trades
    closed_dates: list[date] = []
    d = TRADE_START
    # Leave a 10-day buffer for open trades
    closed_end = TODAY - timedelta(days=10)
    while len(closed_dates) < 80 and d <= closed_end:
        if d.weekday() < 5:  # weekdays only
            closed_dates.append(d)
        d += timedelta(days=1)
    # Pad if weekends trimmed us below 80
    while len(closed_dates) < 80:
        extra = closed_dates[-1] + timedelta(days=1)
        if extra.weekday() < 5:
            closed_dates.append(extra)
        d = extra + timedelta(days=1)
    closed_dates = closed_dates[:80]

    for entry_d in closed_dates:
        asset, symbol = pick_asset()
        direction = RNG.choices(["long", "short"], weights=[65, 35])[0]
        entry_price, size = nominal_for(asset)
        entry_fee = RNG.randint(100, 400)
        exit_fee = RNG.randint(100, 400)
        risk_amount = RNG.randint(5000, 25000)  # £50 – £250 risked

        is_win = RNG.random() < 0.58
        if is_win:
            r_target = RNG.uniform(0.4, 1.8)
        else:
            r_target = -RNG.uniform(0.4, 1.0)
        target_pnl_net = int(round(r_target * risk_amount))
        target_gross = target_pnl_net + entry_fee + exit_fee
        delta = target_gross / size
        if direction == "long":
            exit_price = entry_price + int(round(delta))
        else:
            exit_price = entry_price - int(round(delta))
        if exit_price <= 0:
            exit_price = max(1, entry_price // 2)

        # risk distance = (risk_amount / size) pence
        risk_distance = max(1, int(round(risk_amount / size)))
        if direction == "long":
            stop_loss = entry_price - risk_distance
            take_profit = entry_price + int(round(risk_distance * RNG.uniform(1.5, 2.5)))
        else:
            stop_loss = entry_price + risk_distance
            take_profit = entry_price - int(round(risk_distance * RNG.uniform(1.5, 2.5)))
        stop_loss = max(1, stop_loss)
        take_profit = max(1, take_profit)

        entry_hour = RNG.randint(9, 15)
        entry_min = RNG.choice([0, 5, 15, 30, 45])
        entry_iso = f"{entry_d.isoformat()}T{entry_hour:02d}:{entry_min:02d}:00"

        duration_minutes_target = RNG.choice([30, 60, 90, 120, 240, 360, 1440, 2880])
        exit_dt = datetime.fromisoformat(entry_iso) + timedelta(minutes=duration_minutes_target)
        exit_iso = exit_dt.strftime("%Y-%m-%dT%H:%M:%S")

        gross = calculate_gross_pnl(entry_price, exit_price, size, direction)
        net = calculate_net_pnl(gross, entry_fee, exit_fee)
        pct = calculate_pnl_percentage(net, entry_price, size)
        r_mult = calculate_r_multiple(net, risk_amount)
        dur = calculate_duration_minutes(entry_iso, exit_iso)

        trades.append({
            "account_id": 1,
            "symbol": symbol,
            "asset_class": asset,
            "direction": direction,
            "entry_date": entry_iso,
            "entry_price": entry_price,
            "position_size": size,
            "entry_fee": entry_fee,
            "exit_date": exit_iso,
            "exit_price": exit_price,
            "exit_fee": exit_fee,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk_amount": risk_amount,
            "pnl": gross,
            "pnl_net": net,
            "pnl_percentage": pct,
            "r_multiple": r_mult,
            "mae": None,
            "mfe": None,
            "mae_percentage": None,
            "mfe_percentage": None,
            "duration_minutes": dur,
            "strategy_id": RNG.choice([1, 2, 3]),
            "timeframe": RNG.choice(TIMEFRAMES),
            "setup_type": RNG.choice(SETUPS),
            "market_condition": RNG.choice(CONDITIONS),
            "entry_reason": RNG.choice(ENTRY_REASONS),
            "exit_reason": RNG.choice(EXIT_REASONS),
            "confidence": RNG.randint(4, 9),
            "emotion_before": RNG.randint(2, 5),
            "emotion_during": RNG.randint(2, 5),
            "emotion_after": 4 if is_win else RNG.randint(1, 3),
            "rules_followed_pct": round(RNG.uniform(60, 100), 1),
            "psychology_notes": None,
            "post_trade_review": None,
            "option_type": ("call" if "C" in symbol else "put") if asset == "options" else None,
            "strike_price": RNG.randint(45000, 55000) if asset == "options" else None,
            "expiry_date": (entry_d + timedelta(days=30)).isoformat() if asset == "options" else None,
            "implied_volatility": round(RNG.uniform(18, 45), 2) if asset == "options" else None,
            "trade_type": "trade",
            "notes": None,
            "screenshot_path": None,
            "is_open": 0,
            "_is_win": is_win,
        })

    # Open trades
    open_offsets = [2, 3, 5, 7, 9]
    for offset in open_offsets:
        entry_d = TODAY - timedelta(days=offset)
        asset, symbol = pick_asset()
        direction = RNG.choices(["long", "short"], weights=[65, 35])[0]
        entry_price, size = nominal_for(asset)
        entry_fee = RNG.randint(100, 400)
        risk_amount = RNG.randint(5000, 25000)
        risk_distance = max(1, int(round(risk_amount / size)))
        if direction == "long":
            stop_loss = entry_price - risk_distance
            take_profit = entry_price + int(round(risk_distance * 2))
        else:
            stop_loss = entry_price + risk_distance
            take_profit = entry_price - int(round(risk_distance * 2))
        stop_loss = max(1, stop_loss)
        take_profit = max(1, take_profit)

        entry_hour = RNG.randint(9, 15)
        entry_min = RNG.choice([0, 5, 15, 30, 45])
        entry_iso = f"{entry_d.isoformat()}T{entry_hour:02d}:{entry_min:02d}:00"

        trades.append({
            "account_id": 1,
            "symbol": symbol,
            "asset_class": asset,
            "direction": direction,
            "entry_date": entry_iso,
            "entry_price": entry_price,
            "position_size": size,
            "entry_fee": entry_fee,
            "exit_date": None,
            "exit_price": None,
            "exit_fee": 0,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk_amount": risk_amount,
            "pnl": None,
            "pnl_net": None,
            "pnl_percentage": None,
            "r_multiple": None,
            "mae": None,
            "mfe": None,
            "mae_percentage": None,
            "mfe_percentage": None,
            "duration_minutes": None,
            "strategy_id": RNG.choice([1, 2, 3]),
            "timeframe": RNG.choice(TIMEFRAMES),
            "setup_type": RNG.choice(SETUPS),
            "market_condition": RNG.choice(CONDITIONS),
            "entry_reason": RNG.choice(ENTRY_REASONS),
            "exit_reason": None,
            "confidence": RNG.randint(4, 9),
            "emotion_before": RNG.randint(2, 5),
            "emotion_during": RNG.randint(2, 5),
            "emotion_after": None,
            "rules_followed_pct": None,
            "psychology_notes": None,
            "post_trade_review": None,
            "option_type": ("call" if "C" in symbol else "put") if asset == "options" else None,
            "strike_price": RNG.randint(45000, 55000) if asset == "options" else None,
            "expiry_date": (entry_d + timedelta(days=30)).isoformat() if asset == "options" else None,
            "implied_volatility": round(RNG.uniform(18, 45), 2) if asset == "options" else None,
            "trade_type": "trade",
            "notes": None,
            "screenshot_path": None,
            "is_open": 1,
            "_is_win": None,
        })

    return trades


# ---------------------------------------------------------------------------
# Account snapshots
# ---------------------------------------------------------------------------

def gen_snapshots(trades: list[dict], initial_balance: int) -> list[dict]:
    closed = [t for t in trades if t["is_open"] == 0]
    # Map closing date → running pnl_net delta
    closes_by_day: dict[date, int] = {}
    for t in closed:
        d = datetime.fromisoformat(t["exit_date"]).date()
        closes_by_day[d] = closes_by_day.get(d, 0) + t["pnl_net"]

    snapshots: list[dict] = []
    running = initial_balance
    cur = SNAPSHOT_START
    while cur <= TODAY:
        running += closes_by_day.get(cur, 0)
        snapshots.append({
            "account_id": 1,
            "date": cur.isoformat(),
            "balance": running,
            "equity": running,
            "note": None,
        })
        cur += timedelta(days=1)
    return snapshots


# ---------------------------------------------------------------------------
# Daily journal
# ---------------------------------------------------------------------------

OUTLOOKS = [
    "SPX consolidating under ATH; watching for breakout.",
    "Risk-off tone — treasuries bid, equities soft.",
    "FOMC day, expect volatility into the print.",
    "Gap-up open on strong Asia session, fade risk.",
    "Choppy range — waiting for cleaner setups.",
    "Earnings-heavy week, size down until mid-week.",
]
PLANS = [
    "Trade only A+ breakouts, skip pullbacks.",
    "Focus on AAPL and NVDA — avoid forex.",
    "Max 2 trades, stop at -1R for the day.",
    "Let winners run past 1.5R, no early exits.",
    "Paper-trade only, no live entries today.",
    "Scalp 15m only if volume confirms.",
]
REVIEWS = [
    "Followed plan, banked one clean winner.",
    "Overtraded after early loss, need to stop.",
    "Missed the primary setup, chased a B-grade.",
    "Clean execution, trailing stop worked well.",
    "Cut winner too early, left money on table.",
    "Avoided FOMO entry, proud of the discipline.",
]
LESSONS = [
    "Volume confirmation is non-negotiable for breakouts.",
    "Sitting out is a position — no shame in flat.",
    "Revenge trades always cost double.",
    "First hour setup > mid-session chop.",
    "Stick to the checklist, every time.",
    "Journal before noon next day, not same evening.",
]


def gen_journal() -> list[dict]:
    rows: list[dict] = []
    cur = JOURNAL_START
    while cur <= TODAY:
        # 5 entries / week — skip weekends mostly
        if cur.weekday() < 5 or RNG.random() < 0.15:
            rows.append({
                "date": cur.isoformat(),
                "market_outlook": RNG.choice(OUTLOOKS),
                "plan": RNG.choice(PLANS),
                "review": RNG.choice(REVIEWS),
                "mood": RNG.choices([1, 2, 3, 4, 5], weights=[5, 10, 25, 35, 25])[0],
                "lessons": RNG.choice(LESSONS),
            })
        cur += timedelta(days=1)
    return rows


# ---------------------------------------------------------------------------
# Top-level assembly
# ---------------------------------------------------------------------------

TX_COLS = ["monzo_id", "date", "type", "name", "emoji", "category",
           "amount", "currency", "is_income"]

TRADE_COLS = [
    "account_id", "symbol", "asset_class", "direction",
    "entry_date", "entry_price", "position_size", "entry_fee",
    "exit_date", "exit_price", "exit_fee",
    "stop_loss", "take_profit", "risk_amount",
    "pnl", "pnl_net", "pnl_percentage", "r_multiple",
    "mae", "mfe", "mae_percentage", "mfe_percentage",
    "duration_minutes",
    "strategy_id", "timeframe", "setup_type", "market_condition",
    "entry_reason", "exit_reason", "confidence",
    "emotion_before", "emotion_during", "emotion_after",
    "rules_followed_pct", "psychology_notes", "post_trade_review",
    "option_type", "strike_price", "expiry_date", "implied_volatility",
    "trade_type", "notes", "screenshot_path", "is_open",
]


def main() -> None:
    txs = gen_transactions()
    trades = gen_trades()

    tag_rows = [
        (1, "earnings", "setup"),
        (2, "news-driven", "setup"),
        (3, "A+ setup", "setup"),
        (4, "overtraded", "mistakes"),
        (5, "revenge-trade", "mistakes"),
    ]
    trade_tag_pairs: list[tuple[int, int]] = []
    for i, t in enumerate(trades, start=1):
        if RNG.random() < 0.40:
            # Bias tags toward outcome
            if t["is_open"] == 0 and t.get("_is_win"):
                choice_pool = [1, 2, 3, 3]   # A+ setup biased toward wins
            elif t["is_open"] == 0 and t.get("_is_win") is False:
                choice_pool = [2, 4, 5, 5]   # revenge/overtraded biased toward losses
            else:
                choice_pool = [1, 2, 3]
            n_tags = RNG.choice([1, 2])
            tags_for_trade = RNG.sample(choice_pool, min(n_tags, len(set(choice_pool))))
            for tag_id in set(tags_for_trade):
                trade_tag_pairs.append((i, tag_id))

    initial_balance = 1_000_000  # £10,000
    snapshots = gen_snapshots(trades, initial_balance)
    journal = gen_journal()

    # Achieved metrics for the log
    closed = [t for t in trades if t["is_open"] == 0]
    wins = [t for t in closed if t["pnl_net"] > 0]
    losses = [t for t in closed if t["pnl_net"] <= 0]
    win_rate = (len(wins) / len(closed) * 100) if closed else 0
    sum_wins = sum(t["pnl_net"] for t in wins)
    sum_losses = abs(sum(t["pnl_net"] for t in losses))
    pf = (sum_wins / sum_losses) if sum_losses else float("inf")

    parts: list[str] = []
    parts.append("-- demo-data/seed.sql\n")
    parts.append("-- Generated by demo-data/generate_seed.py — do not edit by hand.\n")
    parts.append(f"-- Run: python demo-data/generate_seed.py\n")
    parts.append(f"-- Anchor date: {TODAY.isoformat()}\n\n")
    parts.append("BEGIN TRANSACTION;\n\n")

    parts.append("-- Clear domain tables (safe no-ops on a fresh DB)\n")
    parts.append("DELETE FROM trade_tags;\n")
    parts.append("DELETE FROM trades;\n")
    parts.append("DELETE FROM account_snapshots;\n")
    parts.append("DELETE FROM strategies;\n")
    parts.append("DELETE FROM tags;\n")
    parts.append("DELETE FROM trading_accounts;\n")
    parts.append("DELETE FROM daily_journal;\n")
    parts.append("DELETE FROM budgets;\n")
    parts.append("DELETE FROM transactions;\n")
    parts.append("DELETE FROM sqlite_sequence WHERE name IN\n"
                 "    ('transactions','budgets','trading_accounts','strategies',\n"
                 "     'tags','trades','account_snapshots','daily_journal');\n\n")

    # Transactions
    parts.append(f"-- {len(txs)} transactions\n")
    tx_rows = [tuple(t[c] for c in TX_COLS) for t in txs]
    parts.append(insert_batch("transactions", TX_COLS, tx_rows))
    parts.append("\n")

    # Budgets
    budget_rows = [
        ("eating_out", 25000, "monthly", None, 1),
        ("groceries", 40000, "monthly", None, 1),
        ("transport", 15000, "monthly", None, 1),
        ("entertainment", 10000, "monthly", None, 1),
        ("shopping", 20000, "monthly", None, 1),
        ("bills", 150000, "monthly", None, 1),
    ]
    parts.append(f"-- {len(budget_rows)} budgets\n")
    parts.append(insert_batch(
        "budgets",
        ["category", "amount", "period", "start_date", "is_active"],
        budget_rows,
    ))
    parts.append("\n")

    # Trading account
    parts.append("-- 1 trading account\n")
    parts.append(insert_batch(
        "trading_accounts",
        ["id", "name", "broker", "asset_class", "currency", "initial_balance", "is_active"],
        [(1, "Demo Trading Account", "Interactive Brokers", "multi", "GBP", initial_balance, 1)],
    ))
    parts.append("\n")

    # Strategies
    strategies = [
        (1, "Breakout v1.0", "Intraday breakouts above consolidation with volume confirmation.",
         "1. Price breaks structure high\n2. Volume > 1.5x average\n3. Risk fixed to 1R on prior swing",
         "1.0", 1),
        (2, "Mean Reversion", "Fade extremes back to 20-EMA in ranging markets.",
         "1. RSI < 30 or > 70\n2. Price outside 2-ATR band\n3. Exit on 20-EMA tag",
         "1.0", 1),
        (3, "Trend Following", "Pullback entries in established trends on the daily timeframe.",
         "1. Higher highs and higher lows\n2. Enter on 20-EMA retest\n3. Trail stop under recent swing",
         "1.0", 1),
    ]
    parts.append("-- 3 strategies\n")
    parts.append(insert_batch(
        "strategies",
        ["id", "name", "description", "rules", "version", "is_active"],
        strategies,
    ))
    parts.append("\n")

    # Tags
    parts.append(f"-- {len(tag_rows)} tags\n")
    parts.append(insert_batch("tags", ["id", "name", "group_name"], tag_rows))
    parts.append("\n")

    # Trades
    parts.append(f"-- {len(trades)} trades ({len(closed)} closed, {len(trades) - len(closed)} open)\n")
    trade_sql_rows = [tuple(t[c] for c in TRADE_COLS) for t in trades]
    parts.append(insert_batch("trades", TRADE_COLS, trade_sql_rows))
    parts.append("\n")

    # Trade tags
    if trade_tag_pairs:
        parts.append(f"-- {len(trade_tag_pairs)} trade/tag associations\n")
        parts.append(insert_batch(
            "trade_tags",
            ["trade_id", "tag_id"],
            trade_tag_pairs,
        ))
        parts.append("\n")

    # Account snapshots
    parts.append(f"-- {len(snapshots)} account snapshots\n")
    snap_rows = [(s["account_id"], s["date"], s["balance"], s["equity"], s["note"])
                 for s in snapshots]
    parts.append(insert_batch(
        "account_snapshots",
        ["account_id", "date", "balance", "equity", "note"],
        snap_rows,
    ))
    parts.append("\n")

    # Daily journal
    parts.append(f"-- {len(journal)} daily journal entries\n")
    journal_rows = [(j["date"], j["market_outlook"], j["plan"], j["review"],
                     j["mood"], j["lessons"]) for j in journal]
    parts.append(insert_batch(
        "daily_journal",
        ["date", "market_outlook", "plan", "review", "mood", "lessons"],
        journal_rows,
    ))
    parts.append("\n")

    parts.append("COMMIT;\n")

    OUTPUT_PATH.write_text("".join(parts), encoding="utf-8", newline="\n")

    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)}")
    print(f"  transactions: {len(txs)}")
    print(f"  budgets: {len(budget_rows)}")
    print(f"  trading_accounts: 1")
    print(f"  strategies: {len(strategies)}")
    print(f"  tags: {len(tag_rows)}")
    print(f"  trades: {len(trades)} ({len(closed)} closed, {len(trades) - len(closed)} open)")
    print(f"  trade_tags: {len(trade_tag_pairs)}")
    print(f"  account_snapshots: {len(snapshots)}")
    print(f"  daily_journal: {len(journal)}")
    print(f"  achieved win rate: {win_rate:.1f}%")
    print(f"  achieved profit factor: {pf:.2f}")
    if closed:
        print(f"  sum net P&L (closed): £{sum(t['pnl_net'] for t in closed) / 100:,.2f}")


if __name__ == "__main__":
    main()
