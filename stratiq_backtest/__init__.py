"""stratiq_backtest — a tiny, honest backtesting engine.

Long-only signal backtests with full trade logs and a buy-and-hold
comparison. No hidden assumptions: the methodology is documented in
the README and every number the engine prints can be traced to a trade.
"""

from .backtest import BarData, BacktestResult, Strategy, Trade, run
from .data import fetch_stooq, load_csv, load_json
from .indicators import atr_series, ema_series, rsi_series, sma
from .stats import max_drawdown, summarize
from .strategy import CrossoverStrategy

__all__ = [
    "BarData",
    "BacktestResult",
    "CrossoverStrategy",
    "Strategy",
    "Trade",
    "atr_series",
    "ema_series",
    "fetch_stooq",
    "load_csv",
    "load_json",
    "max_drawdown",
    "rsi_series",
    "run",
    "sma",
    "summarize",
]

__version__ = "0.1.0"
