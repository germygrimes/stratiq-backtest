"""Core backtest loop.

Methodology (documented so every number is auditable):
- Long-only, fully invested-or-cash. No leverage, no shorting.
- Trades execute AT the close of the bar that generates the signal:
  the strategy sees bar i's close, the trade prints at bar i's close.
- NO look-ahead: a position entered on bar i does NOT earn bar i's
  return (that move already happened before the trade printed). It
  starts earning on bar i+1. A position exited on bar i DOES earn
  bar i's return (it was exposed during the bar, sold at its close).
  NOTE: v0.1.0 credited the signal bar's own return to the new
  position — that was a look-ahead error, fixed in v0.2.0.
- No commissions, no slippage, no taxes are modeled. Real trading
  will do worse than these numbers by roughly those costs.
- Use dividend/split-adjusted closes or your returns will be wrong.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BarData:
    dates: list  # ISO date strings, one per bar
    closes: list  # floats, preferably dividend/split-adjusted

    def __len__(self):
        if len(self.dates) != len(self.closes):
            raise ValueError("dates and closes must be the same length")
        return len(self.dates)


@dataclass
class Trade:
    entry_date: str
    entry: float
    exit_date: str
    exit: float
    return_pct: float
    open_at_end: bool = False


@dataclass
class BacktestResult:
    trades: list = field(default_factory=list)
    equity: list = field(default_factory=list)  # starts at 1.0, one entry per bar + 1
    in_market_bars: int = 0
    warmup: int = 0


class Strategy:
    """Decide the position after seeing bar i's close.

    on_bar(i, data, position) -> new position (0 = cash, 1 = long).
    The returned position takes effect after bar i's close (see the
    no-look-ahead rule above). Strategies may keep state between bars;
    reset() is called before each run.
    """

    def reset(self):
        pass

    def on_bar(self, i: int, data: BarData, position: int) -> int:
        raise NotImplementedError


def run(data: BarData, strategy: Strategy, warmup: int) -> BacktestResult:
    """Run a backtest. Signals are evaluated from bar `warmup` onward."""
    n = len(data)
    if warmup < 1 or warmup >= n:
        raise ValueError("warmup must be >= 1 and < len(data)")
    strategy.reset()
    closes, dates = data.closes, data.dates
    position = 0
    entry_px = entry_date = None
    trades: list[Trade] = []
    equity = [1.0]
    in_market = 0

    for i in range(n):
        # 1) The position held DURING bar i earns bar i's return.
        if position == 1:
            in_market += 1
            equity.append(equity[-1] * (closes[i] / closes[i - 1] if i > 0 else 1.0))
        else:
            equity.append(equity[-1])
        # 2) Then the strategy reacts to bar i's close. A change takes
        # effect after the close: an entry printed at closes[i] starts
        # earning on bar i+1 (no look-ahead); an exit printed at
        # closes[i] keeps the return already earned during bar i.
        if i >= warmup:
            want = strategy.on_bar(i, data, position)
            if want not in (0, 1):
                raise ValueError("strategy must return 0 (cash) or 1 (long)")
            if want != position:
                if want == 1:
                    position = 1
                    entry_px = closes[i]
                    entry_date = dates[i]
                else:
                    ret = closes[i] / entry_px - 1
                    trades.append(
                        Trade(
                            entry_date=entry_date,
                            entry=round(entry_px, 2),
                            exit_date=dates[i],
                            exit=round(closes[i], 2),
                            return_pct=round(ret * 100, 2),
                        )
                    )
                    position = 0
                    entry_px = entry_date = None

    # Close any open position at the final close so equity is comparable.
    if position == 1:
        ret = closes[-1] / entry_px - 1
        trades.append(
            Trade(
                entry_date=entry_date,
                entry=round(entry_px, 2),
                exit_date=dates[-1],
                exit=round(closes[-1], 2),
                return_pct=round(ret * 100, 2),
                open_at_end=True,
            )
        )

    return BacktestResult(
        trades=trades, equity=equity, in_market_bars=in_market, warmup=warmup
    )
