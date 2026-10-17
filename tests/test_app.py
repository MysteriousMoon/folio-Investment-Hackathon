import json
import os
import tempfile

os.environ["FOLIO_DATA_DIR"] = tempfile.mkdtemp(prefix="folio-test-")
os.environ["GEMINI_API_KEY"] = ""
os.environ["GEMINI_API_FORMAT"] = "google"
os.environ["FRED_API_KEY"] = ""
import pytest
import app as module
from engine import extract, build


@pytest.fixture
def client():
    module.app.config["TESTING"] = True
    with module.app.test_client() as c:
        yield c


def send(c, text):
    token = c.get("/api/state").json["csrf"]
    res = c.post("/api/chat", json={"message": text}, headers={"X-CSRF-Token": token})
    assert res.status_code == 200
    return res.get_data(as_text=True)


def test_full_interview_persistence_and_isolation(client):
    text = send(client, "risk level is 3 level, bullish on AI")
    assert "event: portfolio" in text and "event: done" in text
    send(client, "invest 200k USD, 5 years, US stocks, no holdings and no near-term liquidity needs")
    state = client.get("/api/state").json
    assert state["profile"]["amount"] == 200000
    assert state["profile"]["currency"] == "USD"
    assert state["portfolio"]["missing"] == []
    assert sum(r["weight"] for r in state["portfolio"]["rows"]) == 100
    assert sum(r["amount"] for r in state["portfolio"]["rows"]) == 200000
    with module.app.test_client() as other:
        assert other.get("/api/state").json["messages"] == []
    assert json.loads(client.get("/api/export").data)["profile"] == state["profile"]
    token = state["csrf"]
    assert (
        client.delete("/api/state", headers={"X-CSRF-Token": token}).status_code == 200
    )
    assert client.get("/api/state").json["portfolio"] is None


@pytest.mark.parametrize("risk", ["conservative", "balanced", "aggressive"])
def test_weights_short_horizon_and_stress(risk):
    p = build({"risk": risk, "amount": 100000, "horizon": 0.5}, 1)
    assert sum(r["weight"] for r in p["rows"]) == 100
    assert sum(r["weight"] for r in p["rows"][:2]) <= 20
    for s in p["stress"]:
        assert s["impact"] == round(
            sum(r["weight"] * x / 100 for r, x in zip(p["rows"], s["shocks"])), 2
        )


def test_csrf_and_input(client):
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 403
    token = client.get("/api/state").json["csrf"]
    for text in ["", 123, "x" * 4001]:
        assert (
            client.post(
                "/api/chat", json={"message": text}, headers={"X-CSRF-Token": token}
            ).status_code
            == 400
        )
    assert client.get("/").status_code == 200
    assert client.get("/static/js/app.js").status_code == 200


def test_gemini_failure_fallback(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")

    def fail(*args):
        raise RuntimeError("private secret")

    monkeypatch.setattr(module, "gemini_plan", fail)
    monkeypatch.setattr(module, "gemini_stream", fail)
    data = send(client, "bullish on AI, risk conservative")
    assert "event: replace" in data and "private secret" not in data
    assert client.get("/api/state").json["messages"][-1]["provider"] == "Local allocation engine"


def test_streamed_gemini_and_profile(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setattr(
        module,
        "gemini_plan",
        lambda m, p: ({**p, "risk": "aggressive", "amount": 300000}, [30, 45, 10, 10, 5]),
    )
    monkeypatch.setattr(
        module, "gemini_stream", lambda m, p: iter(["Hello", ", the portfolio has been updated"])
    )
    data = send(client, "try my allocation")
    assert data.count("event: delta") == 2
    state = client.get("/api/state").json
    assert state["portfolio"]["rows"][0]["weight"] == 30
    assert state["messages"][-1]["text"] == "Hello, the portfolio has been updated"


def test_same_session_overlap(client):
    state = client.get("/api/state").json
    with client.session_transaction() as s:
        cid = s["id"]
    lock = module.lock_for(cid)
    lock.acquire()
    try:
        assert (
            client.post(
                "/api/chat",
                json={"message": "Hello"},
                headers={"X-CSRF-Token": state["csrf"]},
            ).status_code
            == 409
        )
    finally:
        lock.release()


def test_invalid_json_shape(client):
    token = client.get("/api/state").json["csrf"]
    assert (
        client.post(
            "/api/chat", json=["bad"], headers={"X-CSRF-Token": token}
        ).status_code
        == 400
    )


def test_macro_unconfigured(client, monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    assert client.get("/api/macro").json == {"configured": False, "series": []}


def test_saved_investment_lifecycle_and_new_chat_preserves_it(client):
    state = client.get("/api/state").json
    with client.session_transaction() as session_state:
        cid = session_state["id"]
    stored = module.read(cid)
    stored.update(
        version=3,
        workspace={
            "kind": "security",
            "symbols": ["NVDA"],
            "title": "NVDA research",
            "query": "research NVIDIA",
            "version": 3,
        },
        right_card={
            "markdown": "### NVIDIA Long Stock Position\n\nBuy NVDA.",
            "symbols": ["NVDA"],
            "version": 3,
            "trade": {
                "legs": [
                    {
                        "instrument": "stock",
                        "symbol": "NVDA",
                        "contract": "NVDA",
                        "side": "buy",
                        "quantity": 100,
                    }
                ],
                "curves": [],
            },
        },
    )
    module.save(cid, stored)
    saved = client.post(
        "/api/saved-investments",
        json={},
        headers={"X-CSRF-Token": state["csrf"]},
    )
    assert saved.status_code == 200
    item = saved.json["investment"]
    assert item["title"] == "NVIDIA Long Stock Position"
    assert item["symbols"] == ["NVDA"]

    reset = client.delete(
        "/api/state", headers={"X-CSRF-Token": state["csrf"]}
    )
    assert reset.status_code == 200
    after_reset = client.get("/api/state").json
    assert after_reset["messages"] == []
    assert after_reset["saved_investments"][0]["id"] == item["id"]

    deleted = client.delete(
        "/api/saved-investments/" + item["id"],
        headers={"X-CSRF-Token": after_reset["csrf"]},
    )
    assert deleted.status_code == 200
    assert deleted.json["saved_investments"] == []


def test_yahoo_input():
    from market import quotes

    assert quotes("bad/symbol")["quotes"] == []
    assert quotes(",".join(["V" + str(i) for i in range(9)]))["quotes"] == []


def test_planner_rejects_unbalanced_and_unsafe_weights(monkeypatch):
    import providers

    monkeypatch.setenv("GEMINI_API_KEY", "test")

    class Result:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "profile": {
                                                "risk": "conservative",
                                                "amount": -1,
                                                "horizon": 1e300,
                                            },
                                            "weights": [90, 0, 0, 0, 10],
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            }

    monkeypatch.setattr(providers.requests, "post", lambda *a, **k: Result())
    profile, weights = providers.gemini_plan([], {"amount": 100000})
    assert weights is None and profile["amount"] == 100000 and "horizon" not in profile


def test_money_rounding():
    p = build({"risk": "balanced", "amount": 1000.03}, 1)
    assert round(sum(r["amount"] for r in p["rows"]), 2) == 1000.03


def test_analytics_endpoint_and_export(client):
    send(client, "bullish on AI, add futures hedge")
    res = client.get("/api/analytics?calibration=scenario&months=3")
    assert res.status_code == 200
    assert res.json["positions"][0]["key"] == "futures_hedge"
    assert client.get("/api/export").json["analytics"]["scenarios"] == 20000
    assert client.get("/api/analytics?months=999").status_code == 400


def test_workspace_stream_and_restore_follow_latest_stock(client):
    data = send(client, "research NVIDIA")
    assert "event: workspace" in data
    assert client.get("/api/state").json["workspace"]["symbols"] == ["NVDA"]
    send(client, "review Apple financials")
    workspace = client.get("/api/state").json["workspace"]
    assert workspace["symbols"] == ["AAPL"] and workspace["kind"] == "security"


def test_research_endpoint_requests_the_actual_symbols(client, monkeypatch):
    import market

    calls = []

    def research(symbol):
        calls.append(symbol)
        return {"symbol": symbol, "price": 123, "history": []}

    monkeypatch.setattr(market, "security_research", research)
    data = client.get("/api/research?symbols=NVDA,AAPL").json
    assert set(calls) == {"NVDA", "AAPL"}
    assert [s["symbol"] for s in data["securities"]] == ["NVDA", "AAPL"]
    assert client.get("/api/research?symbols=bad/path").status_code == 400


def test_stock_research_does_not_change_account_amount_or_weights(client):
    send(client, "risk balanced, investment amount 200k USD, 5 years, US stocks, no holdings")
    before = client.get("/api/state").json
    send(client, "review NVDA stock price 200 USD valuation")
    after = client.get("/api/state").json
    assert after["profile"]["amount"] == before["profile"]["amount"] == 200000
    assert after["portfolio"]["rows"] == before["portfolio"]["rows"]
    assert after["workspace"]["symbols"] == ["NVDA"]


def test_strategy_card_channel_persisted_separately(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setattr(module, "gemini_plan", lambda m, p: (p, None))
    monkeypatch.setattr(
        module,
        "gemini_stream",
        lambda m, p: iter(
            ["Left explanation", "<!--FOL", "IO_CARD-->", "### Strategy\nbuy Call + Put"]
        ),
    )
    data = send(client, "help me plan")
    assert "event: strategy_card" in data
    saved = client.get("/api/state").json
    assert saved["messages"][-1]["text"] == "Left explanation"
    assert saved["right_card"]["markdown"] == "### Strategy\nbuy Call + Put"
    assert saved["right_card"]["version"] == saved["version"]
