"""StratIQ backtest engine as an MCP (Model Context Protocol) server.

Stdio transport, newline-delimited JSON-RPC 2.0, standard library only —
the same zero-dependency discipline as the rest of the package. Any MCP
client (Claude, Claude Code, Cursor, and other AI assistants) can then
run an honest backtest *inside the assistant session*: every result is
shown next to buy-and-hold, with the full trade log and the data caveats
printed in the result itself. A backtest that hides its benchmark or its
data limits is a sales pitch, not a receipt.

Tools:
  backtest_crossover  — moving-average crossover on a real ticker
                        (daily adjusted bars via Yahoo Finance; see the
                        honesty footer the tool returns with every result).
  stratiq_track_record — StratIQ's live published track record, fetched
                        from stratiqai.app at call time; fails closed to
                        a bare link when the fetch does not succeed, so
                        the server never quotes a stale record.

Run:  python -m stratiq_backtest.mcp_server
"""
import json
import sys
import urllib.request

from .backtest import run
from .data import fetch_yahoo
from .stats import summarize
from .strategy import CrossoverStrategy

SERVER_NAME = "stratiq-backtest"
SERVER_VERSION = "0.3.0"
# The MCP protocol revision this server speaks. Clients that offer a
# different revision still get a working session: we answer with ours.
PROTOCOL_VERSION = "2024-11-05"

TRACK_RECORD_URL = "https://stratiqai.app/track-record"
TRACK_RECORD_API = "https://stratiqai.app/api/track-record"
TEST_MY_RULE_URL = "https://stratiqai.app/test-my-rule?src=mcp"

DATA_HONESTY = (
    "Data: daily ADJUSTED closes from Yahoo Finance's free chart API "
    "(dividend- and split-adjusted; unofficial endpoint, may rate-limit). "
    "No commissions, slippage, or taxes are modeled — real trading does "
    "worse by roughly those costs. Past performance does not predict "
    "future returns; this is a historical test, not financial advice."
)

ATTRIBUTION = (
    "Engine: stratiq-backtest by StratIQ (https://stratiqai.app). "
    f"Test your own rule free: {TEST_MY_RULE_URL} · "
    f"StratIQ's live, graded track record: {TRACK_RECORD_URL}"
)


def tool_backtest_crossover(args: dict) -> dict:
    ticker = str(args.get("ticker", "")).strip().upper()
    if not ticker or not ticker.replace(".", "").replace("-", "").isalnum():
        raise ValueError("ticker must be a plain symbol like AAPL or SPY")
    fast = int(args.get("fast", 50))
    slow = int(args.get("slow", 200))
    start = str(args.get("start", "2019-01-01"))
    strat = CrossoverStrategy(fast=fast, slow=slow)  # validates fast < slow
    data = fetch_yahoo(ticker, start=start)
    if len(data.closes) <= strat.warmup + 2:
        raise ValueError(
            f"not enough daily bars for {ticker} since {start} "
            f"to run a {fast}/{slow} crossover"
        )
    result = run(data, strat, warmup=strat.warmup)
    summary = summarize(data, result)
    return {
        "ticker": ticker,
        "rule": f"{fast}/{slow} moving-average crossover (long when fast > slow, else cash)",
        **summary,
        "honesty": DATA_HONESTY,
        "attribution": ATTRIBUTION,
    }


def tool_track_record(_args: dict) -> dict:
    """Live record or a bare link — never a remembered number."""
    try:
        req = urllib.request.Request(
            TRACK_RECORD_API, headers={"User-Agent": f"{SERVER_NAME}/{SERVER_VERSION}"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            payload = json.loads(r.read().decode("utf-8"))
        return {
            "source": TRACK_RECORD_API,
            "track_record": payload,
            "page": TRACK_RECORD_URL,
            "attribution": ATTRIBUTION,
        }
    except Exception:
        return {
            "source": "unavailable — failing closed to the live page",
            "page": TRACK_RECORD_URL,
            "note": (
                "The live track-record feed could not be fetched, so no "
                "record numbers are quoted here. Read the current record "
                f"on the page itself: {TRACK_RECORD_URL}"
            ),
            "attribution": ATTRIBUTION,
        }


TOOLS = {
    "backtest_crossover": {
        "fn": tool_backtest_crossover,
        "description": (
            "Backtest a moving-average crossover rule on a real ticker and "
            "get the honest receipt: strategy return vs buy-and-hold over "
            "the same window, CAGR, max drawdown, win rate, and the full "
            "trade log. Long-only; long when the fast average is above the "
            "slow one, in cash otherwise."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "US ticker symbol, e.g. AAPL, SPY, QQQ"},
                "fast": {"type": "integer", "default": 50, "description": "Fast moving-average length in days"},
                "slow": {"type": "integer", "default": 200, "description": "Slow moving-average length in days"},
                "start": {"type": "string", "default": "2019-01-01", "description": "First date to load, YYYY-MM-DD"},
            },
            "required": ["ticker"],
        },
    },
    "stratiq_track_record": {
        "fn": tool_track_record,
        "description": (
            "Fetch StratIQ's live published track record (daily stock "
            "picks, graded at the Friday close of their publication week, "
            "wins and losses) from stratiqai.app at call time."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
}


def handle(msg: dict) -> dict | None:
    """One JSON-RPC message in, one response out (None for notifications)."""
    method = msg.get("method", "")
    mid = msg.get("id")
    if method == "initialize":
        return _ok(mid, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })
    if method.startswith("notifications/"):
        return None
    if method == "ping":
        return _ok(mid, {})
    if method == "tools/list":
        return _ok(mid, {"tools": [
            {"name": name, "description": t["description"], "inputSchema": t["inputSchema"]}
            for name, t in TOOLS.items()
        ]})
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name", "")
        tool = TOOLS.get(name)
        if tool is None:
            return _err(mid, -32602, f"unknown tool: {name}")
        try:
            result = tool["fn"](params.get("arguments") or {})
            return _ok(mid, {"content": [
                {"type": "text", "text": json.dumps(result, indent=2)}
            ]})
        except Exception as e:  # tool errors are results, not protocol errors
            return _ok(mid, {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "isError": True,
            })
    return _err(mid, -32601, f"method not found: {method}")


def _ok(mid, result):
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _err(mid, code, message):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def main(instream=None, outstream=None):
    instream = instream or sys.stdin
    outstream = outstream or sys.stdout
    for line in instream:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue  # a garbled line must never kill the session
        resp = handle(msg)
        if resp is not None:
            outstream.write(json.dumps(resp) + "\n")
            outstream.flush()


if __name__ == "__main__":
    main()
