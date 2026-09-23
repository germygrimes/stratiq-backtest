"""Classic technical indicators. All functions use only data available
at or before the bar they are evaluated on — no lookahead."""


def sma(values, n, i):
    """Simple moving average of the n values ending at index i (inclusive)."""
    if n < 1:
        raise ValueError("n must be >= 1")
    if i - n + 1 < 0:
        raise ValueError(f"not enough data: need {n} values ending at {i}")
    return sum(values[i - n + 1 : i + 1]) / n


def ema_series(values, n):
    """Exponential moving average over the whole series (seeded with SMA)."""
    if n < 1:
        raise ValueError("n must be >= 1")
    k = 2 / (n + 1)
    out = []
    ema = None
    for i, v in enumerate(values):
        if i < n - 1:
            out.append(None)
        elif i == n - 1:
            ema = sum(values[:n]) / n
            out.append(ema)
        else:
            ema = v * k + ema * (1 - k)
            out.append(ema)
    return out


def rsi_series(values, n=14):
    """Relative Strength Index (Wilder's smoothing). None for the first n bars."""
    if n < 1:
        raise ValueError("n must be >= 1")
    out = [None] * len(values)
    if len(values) <= n:
        return out
    gains, losses = [], []
    for i in range(1, n + 1):
        chg = values[i] - values[i - 1]
        gains.append(max(chg, 0))
        losses.append(max(-chg, 0))
    avg_gain = sum(gains) / n
    avg_loss = sum(losses) / n
    for i in range(n, len(values)):
        if i > n:
            chg = values[i] - values[i - 1]
            avg_gain = (avg_gain * (n - 1) + max(chg, 0)) / n
            avg_loss = (avg_loss * (n - 1) + max(-chg, 0)) / n
        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100 - 100 / (1 + rs)
    return out


def atr_series(highs, lows, closes, n=14):
    """Average True Range (Wilder's smoothing). None for the first n bars."""
    if n < 1:
        raise ValueError("n must be >= 1")
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("highs, lows, closes must be the same length")
    out = [None] * len(closes)
    if len(closes) <= n:
        return out
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    atr = sum(trs[:n]) / n
    out[n] = atr
    for i in range(n + 1, len(closes)):
        atr = (atr * (n - 1) + trs[i - 1]) / n
        out[i] = atr
    return out
