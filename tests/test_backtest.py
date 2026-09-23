"""Tests for stratiq_backtest. Run: python3 -m pytest tests/"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stratiq_backtest import (
    BarData,
    CrossoverStrategy,
    Strategy,
    load_json,
    max_drawdown,
    run,
    sma,
    summarize,
)


def make_data(closes, start="2020-01-01"):
    from datetime import date, timedelta

    d0 = date.fromisoformat(start)
    dates = [(d0 + timedelta(days=i)).isoformat() for i in range(len(closes))]
    return BarData(dates=dates, closes=[float(c) for c in closes])


def test_sma():
    assert sma([1, 2, 3, 4, 5], 3, 4) == 4.0
    assert sma([1, 2, 3, 4, 5], 5, 4) == 3.0
    try:
        sma([1, 2], 3, 1)
        raise AssertionError("should have raised")
    except ValueError:
        pass


def test_max_drawdown():
    assert max_drawdown([1.0, 1.5, 1.2, 1.8, 1.0]) == abs(1.0 / 1.8 - 1) * -1
    assert max_drawdown([1.0, 2.0, 3.0]) == 0.0


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


def test_strategy_must_return_0_or_1():
    class Bad(Strategy):
        def on_bar(self, i, data, position):
            return 2

    data = make_data([100.0] * 10)
    try:
        run(data, Bad(), warmup=5)
        raise AssertionError("should have raised")
    except ValueError:
        pass


def test_summarize_math():
    # Straight line up, always invested from bar 5.
    closes = [100 + i for i in range(30)]
    data = make_data(closes)

    class AlwaysLong(Strategy):
        def on_bar(self, i, data, position):
            return 1

    result = run(data, AlwaysLong(), warmup=5)
    s = summarize(data, result)
    assert s["n_trades"] == 1
    assert s["trades"][0]["open_at_end"] is True
    assert s["time_in_market_pct"] == 100.0
    # Engine convention: a position taken at bar i's close earns bar i's
    # move, so AlwaysLong from bar 5 matches buy-and-hold from bar 4.
    assert s["strategy_total_return_pct"] == round((closes[-1] / closes[4] - 1) * 100, 1)
    assert s["buyhold_total_return_pct"] == round((closes[-1] / closes[5] - 1) * 100, 1)
    assert s["strategy_max_dd_pct"] == 0.0


def test_golden_cross_qqq_matches_reference_script():
    """Regression test: the example must keep agreeing, trade-for-trade,
    with StratIQ's internal backtest script on the same bundled data."""
    path = os.path.join(os.path.dirname(__file__), "..", "data", "qqq_2019_2026.json")
    data = load_json(path)
    strat = CrossoverStrategy(fast=50, slow=200)
    s = summarize(data, run(data, strat, warmup=strat.warmup))
    assert s["n_trades"] == 3
    assert s["strategy_total_return_pct"] == 228.5
    assert s["buyhold_total_return_pct"] == 289.1
    assert s["strategy_cagr_pct"] == 18.8
    assert s["buyhold_cagr_pct"] == 21.7
    assert s["strategy_max_dd_pct"] == -22.8
    assert s["buyhold_max_dd_pct"] == -35.1
    assert s["time_in_market_pct"] == 74.0
    assert s["win_rate_pct"] == 100.0
    entries = [t["entry_date"] for t in s["trades"]]
    assert entries == ["2020-05-19", "2023-03-10", "2025-06-23"]
