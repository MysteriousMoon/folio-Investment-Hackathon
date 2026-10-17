from trade_plan import build_plan, payoff, parse_plan
from strategy_card import split_output


def leg(kind, side="buy", qty=1, strike=100, entry=5):
    return dict(
        symbol="NVDA",
        instrument=kind,
        side=side,
        quantity=qty,
        strike=strike,
        entry=entry,
        multiplier=1 if kind == "stock" else 100,
    )


def test_long_straddle_payoff():
    c = payoff([leg("call"), leg("put")], 100, "2027-01-15", "USD")
    assert c["max_loss"] == 1000
    assert c["max_gain"] is None
    assert c["break_even"] == [90, 110]
    assert c["scenario"][2]["pnl"] == -1000


def test_covered_call_and_protective_put():
    c = payoff(
        [leg("stock", qty=100, entry=100), leg("call", side="sell", strike=110)],
        100,
        "2027-01-15",
        "USD",
    )
    assert c["max_loss"] == 9500
    assert c["max_gain"] == 1500
    assert c["break_even"] == [95]
    p = payoff(
        [leg("stock", qty=100, entry=100), leg("put", strike=95)],
        100,
        "2027-01-15",
        "USD",
    )
    assert p["max_loss"] == 1000
    assert p["break_even"] == [105]


def test_spread():
    c = payoff(
        [
            leg("call", strike=100, entry=6),
            leg("call", side="sell", strike=110, entry=2),
        ],
        100,
        "2027-01-15",
        "USD",
    )
    assert c["max_loss"] == 400
    assert c["max_gain"] == 600
    assert c["break_even"] == [104]


def test_missing_hedge_never_graphed():
    raw = {
        "legs": [
            dict(symbol="NVDA", instrument="stock", side="buy", quantity=100),
            dict(
                symbol="NVDA",
                instrument="put",
                contract="UNKNOWN",
                side="buy",
                quantity=1,
            ),
        ]
    }
    result = build_plan(raw, [dict(symbol="NVDA", price=100, currency="USD")], {})
    assert result["complete"] is False
    assert not result["curves"]


def test_futures_multiplier_and_bounds():
    raw = {
        "legs": [
            dict(
                symbol="ES=F",
                instrument="future",
                side="buy",
                quantity=1,
                allocation_pct=10,
            )
        ]
    }
    result = build_plan(raw, [dict(symbol="ES=F", price=5000, currency="USD")], {})
    assert result["legs"][0]["multiplier"] == 50
    assert result["curves"][0]["max_loss"] == 250000
    assert result["curves"][0]["scenario"][-1]["pnl"] == 50000


def test_plan_channel_not_in_markdown():
    text = 'Chat<!--FOLIO_CARD-->Recommendation<!--FOLIO_PLAN-->{"legs":[]}'
    assert split_output(text) == ("Chat", "Recommendation")
    assert parse_plan(text) == {"legs": []}
    for i in range(len("<!--FOLIO_PLAN-->")):
        assert (
            split_output("Chat<!--FOLIO_CARD-->Recommendation" + "<!--FOLIO_PLAN-->"[:i])[1]
            == "Recommendation"
        )


def test_same_underlying_option_quote_validated():
    raw = {
        "legs": [
            dict(
                symbol="NVDA",
                instrument="call",
                contract="C100",
                side="buy",
                quantity=1,
                allocation_pct=2,
            )
        ]
    }
    quotes = [dict(symbol="NVDA", price=100, currency="USD")]
    chains = {
        "NVDA": dict(
            expiry="2027-01-15",
            contracts=[
                dict(
                    symbol="C100", type="call", strike=100, ask=4, bid=3, multiplier=100
                )
            ],
        )
    }
    r = build_plan(raw, quotes, chains)
    assert r["complete"]
    assert r["legs"][0]["entry"] == 4
    assert r["curves"][0]["max_loss"] == 400


def test_multi_expiry_and_multi_symbol_not_merged():
    securities = [
        dict(symbol="AAPL", price=100, currency="USD"),
        dict(symbol="NVDA", price=200, currency="USD"),
    ]
    raw = {
        "legs": [
            dict(symbol=s, instrument="stock", side="buy", quantity=100)
            for s in ["AAPL", "NVDA"]
        ]
    }
    r = build_plan(raw, securities, {})
    assert len(r["curves"]) == 0
    assert len(r["legs"]) == 2


def test_non_list_legs():
    assert not build_plan({"legs": {"bad": 1}}, [], {})["complete"]


def test_cross_underlying_stock_option_combination():
    quotes = [
        dict(symbol="AAPL", price=100, currency="USD"),
        dict(symbol="QQQ", price=200, currency="USD"),
    ]
    raw = {
        "legs": [
            dict(symbol="AAPL", instrument="stock", side="buy", quantity=100),
            dict(
                symbol="QQQ", instrument="put", contract="P200", side="buy", quantity=1
            ),
        ]
    }
    chains = {
        "QQQ": dict(
            expiry="2027-01-15",
            contracts=[
                dict(symbol="P200", type="put", strike=200, ask=5, multiplier=100)
            ],
        )
    }
    result = build_plan(raw, quotes, chains)
    assert result["complete"]
    assert len(result["curves"]) == 1
    c = result["curves"][0]
    assert c["combined"] and c["spot"] == 0
    assert c["scenario"][2]["pnl"] == -500
    assert c["scenario"][0]["pnl"] == 1500
    assert c["scenario"][-1]["pnl"] == 1500


def test_mixed_same_symbol_build_includes_stock_and_put():
    raw = {
        "legs": [
            dict(symbol="NVDA", instrument="stock", side="buy", quantity=100),
            dict(
                symbol="NVDA", instrument="put", contract="P100", side="buy", quantity=1
            ),
        ]
    }
    chains = {
        "NVDA": dict(
            expiry="2027-01-15",
            contracts=[
                dict(symbol="P100", type="put", strike=100, ask=4, multiplier=100)
            ],
        )
    }
    result = build_plan(raw, [dict(symbol="NVDA", price=100, currency="USD")], chains)
    assert len(result["legs"]) == 2 and len(result["curves"]) == 1
    assert result["curves"][0]["max_loss"] == 400
