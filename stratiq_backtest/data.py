"""Data loading. Prefer dividend/split-adjusted closes — unadjusted
data makes every backtest a lie about the past (dividends vanish)."""
import csv
import datetime
import json
import urllib.request

from .backtest import BarData


def load_json(path) -> BarData:
    """Load {"dates": [...], "closes": [...]} or the compact
    {"ts": [unix timestamps], "adj": [adjusted closes]} format."""
    with open(path) as f:
        d = json.load(f)
    if "ts" in d and "adj" in d:
        dates = [
            datetime.datetime.fromtimestamp(t, datetime.UTC).date().isoformat()
            for t in d["ts"]
        ]
        closes = [float(x) for x in d["adj"]]
    elif "dates" in d and "closes" in d:
        dates = list(d["dates"])
        closes = [float(x) for x in d["closes"]]
    else:
        raise ValueError("JSON must have {dates, closes} or {ts, adj}")
    return BarData(dates=dates, closes=closes)


def load_csv(path, date_col="date", close_col="close") -> BarData:
    """Load a CSV with a date column and a close column."""
    dates, closes = [], []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if not row.get(date_col) or not row.get(close_col):
                continue
            try:
                px = float(row[close_col])
            except ValueError:
                continue  # e.g. Stooq "N/D" rows
            dates.append(row[date_col][:10])
            closes.append(px)
    if not dates:
        raise ValueError(f"no usable rows in {path}")
    return BarData(dates=dates, closes=closes)


def fetch_stooq(symbol: str, start: str = "2019-01-01", end: str | None = None) -> BarData:
    """Free daily bars from Stooq (no API key). NOTE: Stooq's free CSV is
    split-adjusted but NOT dividend-adjusted — fine for experimenting,
    not for publishing numbers."""
    if end is None:
        end = datetime.date.today().isoformat()
    url = (
        "https://stooq.com/q/d/l/?s="
        f"{symbol.lower()}.us&d1={start.replace('-', '')}"
        f"&d2={end.replace('-', '')}&i=d"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "stratiq-backtest/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode("utf-8")
    dates, closes = [], []
    for line in text.strip().splitlines()[1:]:  # skip header
        parts = line.split(",")
        if len(parts) < 5 or parts[4] in ("", "N/D"):
            continue
        dates.append(parts[0])
        closes.append(float(parts[4]))
    if not dates:
        raise ValueError(f"no data returned for {symbol}")
    return BarData(dates=dates, closes=closes)
