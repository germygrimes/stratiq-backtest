"""Tests for stratiq_backtest. Run: python3 -m pytest tests/

Execution-semantics contract under test (v0.2.0):
- A trade prints AT the close of the bar that generates the signal.
- A position entered on bar i does NOT earn bar i's return (no look-ahead).
- A position exited on bar i DOES earn bar i's return.
"""
import csv
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stratiq_backtest import (
    BarData,
    CrossoverStrategy,
    Strategy,
    fetch_stooq,  # noqa: F401  (importable; never called in tests)
    load_csv,
    load_json,
    max_drawdown,
    run,
    sma,
    summarize,
    synthetic_bars,
)


def make_data(closes, start="2020-01-01"):
    from datetime import date, timedelta

    d0 = date.fromisoformat(start)
    dates = [(d0 + timedelta(days=i)).isoformat() for i in range(len(closes))]
    return BarData(dates=dates, closes=[float(c) for c in closes])


# ---------- indicators / stats ----------


def test_sma():
    assert sma([1, 2, 3, 4, 5], 3, 4) == 4.0
    assert sma([1, 2, 3, 4, 5], 5, 4) == 3.0
    with pytest.raises(ValueError):
        sma([1, 2], 3, 1)


def test_max_drawdown():
    assert max_drawdown([1.0, 1.5, 1.2, 1.8, 1.0]) == abs(1.0 / 1.8 - 1) * -1
    assert max_drawdown([1.0, 2.0, 3.0]) == 0.0


# ---------- strategy happy paths ----------


def test_crossover_one_round_trip():
    # Flat, then a steady rise (fast crosses above slow), then a steady
    # fall (crosses back down). Exactly one round trip expected.
    closes = [100.0] * 30 + [100 + i for i in range(1, 31)] + [130 - i for i in range(1, 31)]
    data = make_data(closes)
    strat = CrossoverStrategy(fast=5, slow=20)
    result = run(data, strat, warmup=strat.warmup)
    assert result.warmup == 19
    assert len(result.trades) == 1
    t = result.trades[0]
    assert t.return_pct > 0  # bought the rise, sold the fall
    assert len(result.equity) == len(closes) + 1
    assert result.equity[0] == 1.0


def test_no_trades_without_cross():
    closes = [100.0] * 60  # flat: averages never cross
    data = make_data(closes)
    strat = CrossoverStrategy(fast=5, slow=20)
    result = run(data, strat, warmup=strat.warmup)
    assert result.trades == []
    assert result.equity[-1] == 1.0
    assert result.in_market_bars == 0


# ---------- no-look-ahead contract (regression tests) ----------


class LongFrom1(Strategy):
    """Go long at bar 1's close, hold forever."""

    def on_bar(self, i, data, position):
        return 1 if i >= 1 else position


def test_entry_does_not_capture_signal_bar_return():
    # Bar 1 jumps +10% and generates the entry signal. The trade prints
    # at bar 1's close (110) but must NOT capture bar 1's own +10% move.
    data = make_data([100.0, 110.0, 121.0])
    result = run(data, LongFrom1(), warmup=1)
    assert result.equity == [1.0, 1.0, 1.0, pytest.approx(1.1)]
    assert result.equity[2] == 1.0  # signal bar earned nothing
    assert len(result.trades) == 1
    t = result.trades[0]
    assert t.entry_date == "2020-01-02"
    assert t.entry == 110.0
    assert t.exit == 121.0
    assert t.return_pct == 10.0
    assert t.open_at_end is True


def test_exit_keeps_exit_bar_return():
    # Enter at bar 1's close, exit at bar 2's close. The position WAS
    # exposed during bar 2, so its +10% move belongs to the trade.
    class InOut(Strategy):
        def on_bar(self, i, data, position):
            if i == 1:
                return 1
            if i >= 2:
                return 0
            return position

    data = make_data([100.0, 110.0, 121.0])
    result = run(data, InOut(), warmup=1)
    assert result.equity == [1.0, 1.0, 1.0, pytest.approx(1.1)]
    assert len(result.trades) == 1
    t = result.trades[0]
    assert t.entry == 110.0
    assert t.exit == 121.0
    assert t.return_pct == 10.0
    assert t.open_at_end is False


def test_signal_on_final_bar():
    # Entry signal on the last bar: trade prints at the final close,
    # earns nothing, stays open at end with a 0% return.
    data = make_data([100.0, 110.0])
    result = run(data, LongFrom1(), warmup=1)
    assert result.equity == [1.0, 1.0, 1.0]
    assert len(result.trades) == 1
    t = result.trades[0]
    assert t.entry == 110.0
    assert t.exit == 110.0
    assert t.return_pct == 0.0
    assert t.open_at_end is True


def test_immediate_reentry():
    # Enter bar 1, exit bar 2, re-enter bar 3. Each leg is priced
    # independently at its own signal bar's close.
    class Flip(Strategy):
        def on_bar(self, i, data, position):
            if i == 1:
                return 1
            if i == 2:
                return 0
            if i >= 3:
                return 1
            return position

    data = make_data([100.0, 110.0, 121.0, 115.0, 126.0])
    result = run(data, Flip(), warmup=1)
    assert len(result.trades) == 2
    assert result.trades[0].return_pct == 10.0
    assert result.trades[1].return_pct == round((126 / 115 - 1) * 100, 2) == 9.57
    assert result.equity[-1] == pytest.approx(1.1 * 126 / 115)


def test_always_long_matches_buyhold():
    # A strategy that enters at the warmup bar's close and never exits
    # must match buy-and-hold from that bar exactly.
    closes = [100 + i for i in range(30)]

    class AlwaysLong(Strategy):
        def on_bar(self, i, data, position):
            return 1

    data = make_data(closes)
    result = run(data, AlwaysLong(), warmup=5)
    s = summarize(data, result)
    assert s["n_trades"] == 1
    assert s["trades"][0]["open_at_end"] is True
    expected = round((closes[-1] / closes[5] - 1) * 100, 1)
    assert s["strategy_total_return_pct"] == expected
    assert s["buyhold_total_return_pct"] == expected
    # Entered after bar 5's close: in market during bars 6..29 (24 of 25).
    assert s["time_in_market_pct"] == 96.0
    assert s["strategy_max_dd_pct"] == 0.0


def test_trade_prices_rounded():
    data = make_data([100.456, 110.789])
    result = run(data, LongFrom1(), warmup=1)
    t = result.trades[0]
    assert t.entry == 110.79
    assert t.exit == 110.79


# ---------- failure / edge cases ----------


def test_strategy_must_return_0_or_1():
    class Bad(Strategy):
        def on_bar(self, i, data, position):
            return 2

    with pytest.raises(ValueError):
        run(make_data([100.0] * 10), Bad(), warmup=5)


def test_warmup_validation():
    data = make_data([100.0] * 10)
    with pytest.raises(ValueError):
        run(data, LongFrom1(), warmup=0)
    with pytest.raises(ValueError):
        run(data, LongFrom1(), warmup=-3)
    with pytest.raises(ValueError):
        run(data, LongFrom1(), warmup=10)  # must be < len(data)


def test_bardata_length_mismatch():
    with pytest.raises(ValueError):
        len(BarData(dates=["2020-01-01"], closes=[1.0, 2.0]))


def test_summarize_not_enough_bars():
    data = make_data([100.0, 101.0, 102.0])
    result = run(data, LongFrom1(), warmup=2)
    with pytest.raises(ValueError):
        summarize(data, result)


def test_crossover_invalid_params():
    with pytest.raises(ValueError):
        CrossoverStrategy(fast=200, slow=50)
    with pytest.raises(ValueError):
        CrossoverStrategy(fast=1, slow=50)
    with pytest.raises(ValueError):
        CrossoverStrategy(fast=50, slow=50)


def test_load_json_formats(tmp_path):
    p1 = tmp_path / "a.json"
    p1.write_text(json.dumps({"dates": ["2020-01-01"], "closes": [300.5]}))
    d1 = load_json(p1)
    assert d1.dates == ["2020-01-01"] and d1.closes == [300.5]

    p2 = tmp_path / "b.json"
    p2.write_text(json.dumps({"ts": [1577836800], "adj": [250.25]}))
    d2 = load_json(p2)
    assert d2.dates == ["2020-01-01"] and d2.closes == [250.25]


def test_load_json_invalid(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"foo": 1}))
    with pytest.raises(ValueError):
        load_json(p)


def test_load_csv(tmp_path):
    p = tmp_path / "d.csv"
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "close"])
        w.writerow(["2020-01-01", "100.5"])
        w.writerow(["2020-01-02", "N/D"])  # skipped
        w.writerow(["2020-01-03", "102.0"])
    d = load_csv(p)
    assert d.dates == ["2020-01-01", "2020-01-03"]
    assert d.closes == [100.5, 102.0]


def test_load_csv_empty(tmp_path):
    p = tmp_path / "e.csv"
    p.write_text("date,close\n")
    with pytest.raises(ValueError):
        load_csv(p)


# ---------- synthetic data ----------


def test_synthetic_deterministic():
    a = synthetic_bars(100, seed=7)
    b = synthetic_bars(100, seed=7)
    assert a.closes == b.closes
    assert a.dates == b.dates
    c = synthetic_bars(100, seed=8)
    assert c.closes != a.closes
    assert len(a.closes) == 100
    assert all(px > 0 for px in a.closes)
    assert a.dates == sorted(a.dates)
    assert a.dates[0] == "2020-01-01"


def test_synthetic_invalid_n():
    with pytest.raises(ValueError):
        synthetic_bars(0)
