"""Golden cross on synthetic data — a reproducible demo of the engine.

Buy when the 50-day SMA crosses above the 200-day SMA, sell (to cash)
when it crosses back below. Long-only, fully invested, trades at the
close.

The data is SYNTHETIC (a seeded random walk): the numbers below show
the engine's mechanics, not a claim about any real market. For real
data, use fetch_stooq() for quick experiments or load your own
dividend/split-adjusted closes before publishing anything.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stratiq_backtest import (  # noqa: E402
    CrossoverStrategy,
    run,
    summarize,
    synthetic_bars,
)


def main():
    data = synthetic_bars(n=1500, seed=42)
    print("data: SYNTHETIC (seeded random walk) — demo only, not real market data")
    strat = CrossoverStrategy(fast=50, slow=200)
    result = run(data, strat, warmup=strat.warmup)
    out = summarize(data, result)
    print(json.dumps({k: v for k, v in out.items() if k != "trades"}, indent=1))
    print(f"trades: {out['n_trades']}")


if __name__ == "__main__":
    main()
