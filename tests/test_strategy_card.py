from strategy_card import split_output, MARKER
from conversation import resolve


def test_split_all_marker_boundaries():
    text = "Left explanation\n\n" + MARKER + "\n### Long straddle\n|Call|Put|"
    for index in range(len(text) + 1):
        left, card = split_output(text[:index])
        assert "<!--" not in left
        if card:
            assert "### Long straddle\n|Call|Put|".startswith(card)
    assert split_output(text, final=True) == ("Left explanation", "### Long straddle\n|Call|Put|")


def test_no_marker_and_final_partial():
    assert split_output("Normal response") == ("Normal response", "")
    assert split_output("Test<", final=True) == ("Test<", "")


def test_volatility_routes_to_options():
    assert resolve("I expect huge moves in NVIDIA")["kind"] == "options"
    assert resolve("I expect huge moves in it", {"symbols": ["NVDA"]})["symbols"] == ["NVDA"]


def test_fallback_uses_actual_contracts():
    from strategy_card import fallback_card

    chain = dict(
        spot=100,
        expiry="2027-01-15",
        contracts=[
            dict(type="call", strike=100, symbol="CALL100", ask=5),
            dict(type="put", strike=100, symbol="PUT100", ask=4),
        ],
    )
    card = fallback_card(dict(symbols=["NVDA"], query="NVIDIA huge moves"), chain)
    assert "CALL100" in card and "PUT100" in card
    assert "$900.00" in card and "$91.00 / $109.00" in card
    assert "Local strategy example" in card


def test_futures_context():
    c = resolve("analyze Nasdaq futures")
    assert c["kind"] == "futures"
    assert c["symbols"] == ["NQ=F"]
    c = resolve("NVDA stock plus protective put portfolio")
    assert c["kind"] == "options"
    assert c["symbols"] == ["NVDA"]


def test_futures_negated_options():
    assert resolve("Nasdaq futures NQ=F, futures only, do not want options")["kind"] == "futures"


def test_comparison_risk_followup_keeps_all_symbols():
    c = resolve("compare MSFT  and  NVDA, focus on risk and forecast returns")
    assert c["kind"] == "comparison"
    c = resolve("review their risk", {"kind": "comparison", "symbols": ["MSFT", "NVDA"]})
    assert c["kind"] == "comparison" and len(c["symbols"]) == 2
