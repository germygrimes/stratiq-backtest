"""Deterministic SYNTHETIC price series for examples and tests.

These are NOT real market data: a seeded geometric Brownian motion
with a mild upward drift. They exist so the bundled example is
reproducible forever without redistributing anyone's price data.

Never publish performance numbers computed on this data as if they
were real. For real data, use fetch_stooq() (split-adjusted only —
fine for experimenting, not for publishing) or load your own
dividend/split-adjusted closes.
"""
import datetime
import math
import random

from .backtest import BarData


def synthetic_bars(
    n: int = 1500,
    seed: int = 42,
    start: str = "2020-01-01",
    start_px: float = 100.0,
    drift: float = 0.0004,
    vol: float = 0.012,
) -> BarData:
    """Generate n daily bars of synthetic closes from a seeded PRNG.

    Same seed -> identical series, forever. Weekends are skipped so
    the dates look like market data.
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    rng = random.Random(seed)
    closes = []
    px = start_px
    for _ in range(n):
        px *= math.exp(drift - 0.5 * vol * vol + vol * rng.gauss(0, 1))
        closes.append(round(px, 2))
    d0 = datetime.date.fromisoformat(start)
    dates = []
    d = d0
    while len(dates) < n:
        if d.weekday() < 5:  # Mon-Fri only
            dates.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return BarData(dates=dates, closes=closes)
