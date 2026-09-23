# stratiq-backtest

A tiny, honest backtesting engine. Long-only signal backtests with full trade logs — and every result shown next to the do-nothing alternative, because a strategy that beats nothing is a hobby.

This is the engine behind [StratIQ's public track record](https://stratiqai.app/track-record), where every backtest is published with wins and losses.

## Install

```bash
pip install stratiq-backtest
```

Or from source: `pip install .` — zero dependencies, stdlib only.

## Quickstart

```python
from stratiq_backtest import CrossoverStrategy, run, summarize, synthetic_bars

data = synthetic_bars(n=1500, seed=42)   # reproducible demo data (NOT real market data)
strat = CrossoverStrategy(fast=50, slow=200)   # golden cross
result = run(data, strat, warmup=strat.warmup)
stats = summarize(data, result)

print(stats["strategy_total_return_pct"], "vs buy-and-hold",
      stats["buyhold_total_return_pct"])
for t in stats["trades"]:
    print(t)
```

Run the bundled example (golden cross on synthetic data):

```bash
python3 examples/golden_cross_synthetic.py
```

## Execution semantics (read this before trusting a number)

- **Trades print at the close of the bar that generates the signal.** The strategy sees bar *i*'s close; the trade executes at bar *i*'s close.
- **No look-ahead, ever.** A position entered on bar *i* does **not** earn bar *i*'s return — that move already happened before the trade printed. It starts earning on bar *i+1*. A position exited on bar *i* **does** earn bar *i*'s return (it was exposed during the bar, sold at its close).
- Long-only, fully invested-or-cash. No leverage, no shorting. No commissions, no slippage, no taxes — real trading will do worse by roughly those costs.
- Use dividend/split-adjusted closes or your returns will be wrong.

> **Correction note (v0.2.0):** v0.1.0 credited each new position with the signal bar's own price move. That is look-ahead bias — the signal only exists after the bar closes — so v0.1.0 results were overstated. v0.2.0 fixes the execution timing and adds regression tests pinning the corrected behavior. If you published numbers computed with v0.1.0, re-run them.

## Data

The repo ships **no real market data**. `synthetic_bars()` generates a deterministic seeded random walk for examples and tests — reproducible forever, and clearly labeled synthetic. Never publish performance numbers computed on it as if they were real.

For real data:
- `fetch_stooq(symbol)` — free daily bars from Stooq, no API key. **Split-adjusted but NOT dividend-adjusted**: fine for experimenting, not for publishing numbers.
- `load_json()` / `load_csv()` — bring your own dividend/split-adjusted closes.

## Write your own strategy

```python
from stratiq_backtest import Strategy

class MyStrategy(Strategy):
    def on_bar(self, i, data, position):
        # i: current bar index, data.closes / data.dates available.
        # Return 1 to be long, 0 for cash. The new position takes
        # effect AFTER bar i's close (see execution semantics above).
        ...
```

Warm up indicators with `warmup=` so signals only fire on fully-formed values.

## Tests

```bash
python3 -m pytest tests/
```

Happy paths, failure modes, edge cases — including regression tests that pin the no-look-ahead contract above.
