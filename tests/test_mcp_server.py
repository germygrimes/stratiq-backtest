"""Tests for the MCP server (stratiq_backtest.mcp_server).

No network: the Yahoo fetch is monkeypatched to synthetic bars, and the
track-record tool is exercised on its fail-closed path. The live paths
(real Yahoo fetch, live track-record API) are smoke-tested separately
against the real services, never in the unit suite.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stratiq_backtest import mcp_server
from stratiq_backtest.synthetic import synthetic_bars


def call(msg):
    return mcp_server.handle(msg)


def test_initialize_handshake():
    resp = call({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "stratiq-backtest"
    assert resp["result"]["capabilities"]["tools"] == {}


def test_notifications_get_no_response():
    assert call({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_tools_list_names_both_tools():
    resp = call({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {t["name"] for t in resp["result"]["tools"]}
    assert names == {"backtest_crossover", "stratiq_track_record"}
    for t in resp["result"]["tools"]:
        assert t["inputSchema"]["type"] == "object"
        assert t["description"]


def test_unknown_method_is_protocol_error():
    resp = call({"jsonrpc": "2.0", "id": 3, "method": "nope/nope"})
    assert resp["error"]["code"] == -32601


def test_unknown_tool_is_params_error():
    resp = call({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                 "params": {"name": "nope", "arguments": {}}})
    assert resp["error"]["code"] == -32602


@pytest.fixture
def fake_stooq(monkeypatch):
    data = synthetic_bars(n=900, seed=7)
    monkeypatch.setattr(mcp_server, "fetch_yahoo", lambda symbol, start="2019-01-01": data)
    return data


def test_backtest_crossover_returns_honest_receipt(fake_stooq):
    resp = call({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                 "params": {"name": "backtest_crossover",
                            "arguments": {"ticker": "test", "fast": 10, "slow": 40}}})
    assert "error" not in resp
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["ticker"] == "TEST"
    # The receipt always carries the benchmark next to the strategy.
    assert "strategy_total_return_pct" in payload
    assert "buyhold_total_return_pct" in payload
    assert "trades" in payload
    # Honesty + attribution ride along in every result.
    assert "dividend" in payload["honesty"] and "not financial advice" in payload["honesty"]
    assert "test-my-rule?src=mcp" in payload["attribution"]


def test_backtest_crossover_rejects_bad_params(fake_stooq):
    resp = call({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                 "params": {"name": "backtest_crossover",
                            "arguments": {"ticker": "TEST", "fast": 200, "slow": 50}}})
    assert resp["result"]["isError"] is True
    resp = call({"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                 "params": {"name": "backtest_crossover",
                            "arguments": {"ticker": "../etc/passwd"}}})
    assert resp["result"]["isError"] is True


def test_track_record_fails_closed_without_numbers(monkeypatch):
    def boom(*a, **k):
        raise OSError("network down")

    monkeypatch.setattr(mcp_server.urllib.request, "urlopen", boom)
    resp = call({"jsonrpc": "2.0", "id": 8, "method": "tools/call",
                 "params": {"name": "stratiq_track_record", "arguments": {}}})
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["page"] == "https://stratiqai.app/track-record"
    assert "track_record" not in payload  # no numbers when the feed is down


def test_stdio_roundtrip(fake_stooq):
    import io

    lines = "\n".join([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        "this is not json",
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
    ]) + "\n"
    out = io.StringIO()
    mcp_server.main(instream=io.StringIO(lines), outstream=out)
    responses = [json.loads(x) for x in out.getvalue().splitlines()]
    assert [r["id"] for r in responses] == [1, 2]  # notification + garbage skipped
