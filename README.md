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
from stratiq_backtest import CrossoverStrategy, fetch_stooq, run, summarize

data = fetch_stooq("QQQ", start="2019-01-01")
strat = CrossoverStrategy(fast=50, slow=200)   # golden cross
result = run(data, strat, warmup=strat.warmup)
stats = summarize(data, result)

print(stats["strategy_total_return_pct"], "vs buy-and-hold",
      stats["buyhold_total_return_pct"])
for t in stats["trades"]:
    print(t)
```

Run the bundled example (golden cross on QQQ, 2019–2026, dividend-adjusted sample data included):

```bash
python3 examples/golden_cross_qqq.py
```

The engine is verified trade-for-trade against StratIQ's internal backtest
script on the same data. One honest caveat you'll notice across the industry:
re-running a backtest on refreshed data can shift knife-edge signals (a single
cross appearing or vanishing changes the whole result). We pin the sample data
in this repo so the example is reproducible forever.

## Write your own strategy

```python
from stratiq_backtest import Strategy

class MyStrategy(Strategy):
    def on_bar(self, i, data, position):
        # i: current bar index, data.closes / data.dates available.
        # Return 1 for long, 0 for cash. Only past and present bars
        # are visible — peeking at the future is impossible by design.
        ...
```

## Methodology (read this before quoting numbers)

- **Long-only, fully invested or in cash.** No leverage, no shorting.
- **Signals trade at the closing price of the signal bar**, and the new position earns that bar's move. A stricter convention (enter next bar) would show slightly lower returns; we document our choice instead of hiding it.
- **No commissions, no slippage, no taxes modeled.** Real trading does worse by roughly those costs.
- **Use dividend/split-adjusted closes.** Unadjusted data silently deletes dividend returns and makes the past look worse than it was. The bundled QQQ sample is dividend-adjusted.
- **Few trades = thin evidence.** Our headline example makes 4 trades in 7 years. That's honest, and it's thin — treat it accordingly.

## What's in the box

- `backtest.run` — the event loop
- `strategy.CrossoverStrategy` — fast/slow moving-average crossover
- `indicators` — SMA, EMA, RSI, ATR
- `data` — JSON/CSV loaders + free Stooq downloader (no API key)
- `stats.summarize` — returns, CAGR, max drawdown, win rate, time in market, buy-and-hold comparison, full trade list

## License

MIT — use it, fork it, tell us when it proves you wrong.
