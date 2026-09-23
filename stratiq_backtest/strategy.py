"""Ready-made strategies. Subclass Strategy (see backtest.py) for your own."""
from .backtest import BarData, Strategy
from .indicators import sma


class CrossoverStrategy(Strategy):
    """Go long when the fast SMA crosses above the slow SMA; exit (to cash)
    when it crosses back below. Hysteretic: no signal, no change.

    Pass warmup=strategy.warmup to run(). warmup = slow - 1, the first bar
    on which both averages are defined.
    """

    def __init__(self, fast: int = 50, slow: int = 200):
        if not 1 < fast < slow:
            raise ValueError("need 1 < fast < slow")
        self.fast = fast
        self.slow = slow

    @property
    def warmup(self) -> int:
        return self.slow - 1

    def on_bar(self, i: int, data: BarData, position: int) -> int:
        # No signal until both the current AND previous averages are
        # defined — comparing against a half-formed average would be
        # peeking at a signal that doesn't exist yet.
        if i - 1 < self.slow - 1:
            return position
        c = data.closes
        f, s = sma(c, self.fast, i), sma(c, self.slow, i)
        fp, sp = sma(c, self.fast, i - 1), sma(c, self.slow, i - 1)
        if position == 0 and fp <= sp and f > s:
            return 1
        if position == 1 and fp >= sp and f < s:
            return 0
        return position
