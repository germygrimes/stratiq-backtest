"""Golden cross on DIA — the README's real worked example, runnable.

50/200 SMA crossover on Yahoo Finance dividend/split-adjusted daily
closes, 2019-01-02 -> 2026-11-06 (the test window starts 2019-10-16,
after the 200-day warmup). Prints the strategy next to buy-and-hold
over the same window, because a strategy that beats nothing is a
hobby.

Data: real market data via fetch_yahoo() (unofficial endpoint; fails
loudly). No commissions, slippage, or taxes are modeled — real trading
would do worse by roughly those costs.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stratiq_backtest import CrossoverStrategy, run, summarize, fetch_yahoo  # noqa: E402


def main():
    data = fetch_yahoo("DIA", end="2026-11-06")
    strat = CrossoverStrategy(fast=50, slow=200)
    stats = summarize(data, run(data, strat, warmup=strat.warmup))

    start, end = stats["strategy_period"]
    print(f"DIA golden cross (50/200 SMA), {start} -> {end}")
    print()

    def row(label, strat_val, bh_val):
        print(f"{label:16}{strat_val:>14}{bh_val:>14}")

    row("", "Golden cross", "Buy-and-hold")
    row("Total return",
        f"{stats['strategy_total_return_pct']:+.1f}%",
        f"{stats['buyhold_total_return_pct']:+.1f}%")
    row("CAGR",
        f"{stats['strategy_cagr_pct']:.1f}%",
        f"{stats['buyhold_cagr_pct']:.1f}%")
    row("Max drawdown",
        f"{stats['strategy_max_dd_pct']:.1f}%",
        f"{stats['buyhold_max_dd_pct']:.1f}%")
    print()
    print(f"{stats['n_trades']} trades, win rate {stats['win_rate_pct']:.1f}%, "
          f"{stats['time_in_market_pct']:.1f}% of the time in the market")
    for i, t in enumerate(stats["trades"], 1):
        print(f"  {i}. {t['entry_date']} @ {t['entry']:.2f} -> "
              f"{t['exit_date']} @ {t['exit']:.2f}  {t['return_pct']:+.2f}%")
    print()
    strat_final = 10_000 * (1 + stats["strategy_total_return_pct"] / 100)
    bh_final = 10_000 * (1 + stats["buyhold_total_return_pct"] / 100)
    gap = stats["buyhold_total_return_pct"] - stats["strategy_total_return_pct"]
    print(f"$10,000 -> ${strat_final:,.0f} following the rule vs ${bh_final:,.0f} holding.")
    if stats["win_rate_pct"] == 100.0:
        print("The rule never lost a trade in seven years — and still trailed")
    print(f"buy-and-hold by {gap:.0f} points. Every result ships with the")
    print("do-nothing alternative next to it.")


if __name__ == "__main__":
    main()
