"""Performance statistics, always shown next to buy-and-hold.

A strategy that beats nothing is a hobby. Every summary includes the
do-nothing alternative over the same period so the numbers mean something.
"""
from dataclasses import asdict

TRADING_DAYS = 252


def max_drawdown(equity) -> float:
    """Largest peak-to-trough decline, as a fraction (negative or zero)."""
    peak = equity[0]
    mdd = 0.0
    for v in equity:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    return mdd


def summarize(data, result) -> dict:
    """Full honest summary: strategy stats + buy-and-hold over the same window."""
    n = len(data)
    warmup = result.warmup
    closes = data.closes
    # Bars [warmup, n-1] are the strategy's active window.
    span_bars = n - warmup
    if span_bars < 2:
        raise ValueError("not enough bars after warmup")

    strat_ret = result.equity[-1] - 1
    years = span_bars / TRADING_DAYS
    cagr = result.equity[-1] ** (1 / years) - 1

    bh_ret = closes[-1] / closes[warmup] - 1
    bh_cagr = (1 + bh_ret) ** (1 / years) - 1
    bh_eq = [c / closes[warmup] for c in closes[warmup:]]

    trades = result.trades
    wins = [t for t in trades if t.return_pct > 0]
    losses = [t for t in trades if t.return_pct <= 0]

    def trade_dict(t):
        return asdict(t) if t is not None else None

    return {
        "data_range": [data.dates[0], data.dates[-1]],
        "strategy_period": [data.dates[warmup], data.dates[-1]],
        "n_trades": len(trades),
        "win_rate_pct": round(100 * len(wins) / len(trades), 1) if trades else 0.0,
        "avg_win_pct": round(sum(t.return_pct for t in wins) / len(wins), 2) if wins else 0.0,
        "avg_loss_pct": round(sum(t.return_pct for t in losses) / len(losses), 2)
        if losses
        else 0.0,
        "strategy_total_return_pct": round(strat_ret * 100, 1),
        "strategy_cagr_pct": round(cagr * 100, 1),
        "strategy_max_dd_pct": round(max_drawdown(result.equity) * 100, 1),
        "buyhold_total_return_pct": round(bh_ret * 100, 1),
        "buyhold_cagr_pct": round(bh_cagr * 100, 1),
        "buyhold_max_dd_pct": round(max_drawdown(bh_eq) * 100, 1),
        "time_in_market_pct": round(100 * result.in_market_bars / span_bars, 1),
        "best_trade": trade_dict(max(trades, key=lambda t: t.return_pct)) if trades else None,
        "worst_trade": trade_dict(min(trades, key=lambda t: t.return_pct)) if trades else None,
        "trades": [asdict(t) for t in trades],
    }
