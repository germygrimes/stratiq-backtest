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


def fetch_yahoo(symbol: str, start: str = "2019-01-01", end: str | None = None) -> BarData:
    """Free daily bars from Yahoo Finance's chart API (no API key), using
    the ADJUSTED close series — dividend- and split-adjusted, the only
    honest basis for a long-window backtest. Unofficial endpoint: it can
    rate-limit or change without notice, so callers must fail loudly."""
    if end is None:
        end = datetime.date.today().isoformat()
    p1 = int(datetime.datetime.fromisoformat(start).replace(tzinfo=datetime.UTC).timestamp())
    p2 = int(datetime.datetime.fromisoformat(end).replace(tzinfo=datetime.UTC).timestamp()) + 86400
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{symbol.upper()}?period1={p1}&period2={p2}&interval=1d&events=div,split"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 stratiq-backtest/0.3"})
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.loads(r.read().decode("utf-8"))
    result = (payload.get("chart") or {}).get("result") or []
    if not result:
        raise ValueError(f"no data returned for {symbol}")
    result = result[0]
    stamps = result.get("timestamp") or []
    adj = ((result.get("indicators") or {}).get("adjclose") or [{}])[0].get("adjclose")
    if adj is None:  # fall back to raw closes rather than nothing
        adj = ((result.get("indicators") or {}).get("quote") or [{}])[0].get("close")
    if not stamps or not adj:
        raise ValueError(f"no price series returned for {symbol}")
    dates, closes = [], []
    for t, px in zip(stamps, adj):
        if px is None:
            continue
        dates.append(datetime.datetime.fromtimestamp(t, datetime.UTC).date().isoformat())
        closes.append(float(px))
    if not dates:
        raise ValueError(f"no usable bars returned for {symbol}")
    return BarData(dates=dates, closes=closes)


def fetch_stooq(symbol: str, start: str = "2019-01-01", end: str | None = None) -> BarData:
    """Free daily bars from Stooq (no API key). NOTE: Stooq's free CSV is
    split-adjusted but NOT dividend-adjusted — fine for experimenting,
    not for publishing numbers. NOTE 2: as of 2026-11 Stooq serves a
    JavaScript browser-verification challenge to plain HTTP clients, so
    this fetch currently fails against the live site; fetch_yahoo is the
    working free path."""
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
