"""Golden cross on QQQ (2019-2026) — the same backtest StratIQ publishes.

Buy when the 50-day SMA crosses above the 200-day SMA, sell (to cash)
when it crosses back below. Long-only, fully invested, trades at the
close, dividend/split-adjusted data.

This engine is verified trade-for-trade against StratIQ's internal
backtest script on the same data. (Published track-record figures
reflect the data vintage at publication time — re-running any backtest
on refreshed data can shift knife-edge signals, which is itself an
honest lesson about backtests.)
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stratiq_backtest import (  # noqa: E402
    CrossoverStrategy,
    load_json,
    run,
    summarize,
)

DATA = os.path.join(os.path.dirname(__file__), "..", "data", "qqq_2019_2026.json")


def main():
    data = load_json(DATA)
    strat = CrossoverStrategy(fast=50, slow=200)
    result = run(data, strat, warmup=strat.warmup)
    out = summarize(data, result)
    print(json.dumps({k: v for k, v in out.items() if k != "trades"}, indent=1))
    print(f"trades: {out['n_trades']}")


if __name__ == "__main__":
    main()
