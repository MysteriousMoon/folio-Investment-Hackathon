import pytest
from conversation import resolve, clean_hint


def test_explicit_stock_is_replaced_not_accumulated():
    first = resolve("analyze NVIDIA")
    assert first["kind"] == "security" and first["symbols"] == ["NVDA"]
    second = resolve("review Apple", first)
    assert second["symbols"] == ["AAPL"]
    assert resolve("how is its valuation", second)["symbols"] == ["AAPL"]


def test_comparison_and_options_keep_the_right_underlying():
    c = resolve("compare NVDA and AMD")
    assert c["kind"] == "comparison" and c["symbols"] == ["NVDA", "AMD"]
    c = resolve("review Tesla options", c)
    assert c["kind"] == "options" and c["symbols"] == ["TSLA"]
    assert resolve("available expiries", c)["symbols"] == ["TSLA"]


@pytest.mark.parametrize(
    "text,symbol",
    [
        ("nvda", "NVDA"),
        ("Tencent", "0700.HK"),
        ("600519.SS", "600519.SS"),
        ("ES=F", "ES=F"),
    ],
)
def test_symbol_resolution(text, symbol):
    assert resolve(text)["symbols"] == [symbol]


def test_theme_and_macro_are_not_arbitrary_stocks():
    assert resolve("bullish on AI")["symbols"] == []
    assert resolve("discuss FRED and CPI")["kind"] == "macro"
    assert resolve("return to overall allocation", resolve("research NVDA"))["kind"] == "allocation"


def test_invalid_model_symbols_and_modules_are_rejected():
    h = clean_hint(
        {
            "kind": "<script>",
            "symbols": ["NVDA", "https://evil.invalid", "NVDA"],
            "modules": ["price", "<script>"],
            "title": "x" * 100,
        }
    )
    assert (
        h["symbols"] == ["NVDA"] and h["modules"] == ["price"] and len(h["title"]) == 70
    )
    assert resolve("research Apple", hint={"kind": "security", "symbols": ["TSLA"]})[
        "symbols"
    ] == ["AAPL"]


def test_followup_comparison_adds_new_stock_to_previous_subject():
    c = resolve("review NVIDIA")
    result = resolve("compare with Apple", c)
    assert result["kind"] == "comparison" and result["symbols"] == ["NVDA", "AAPL"]
    assert resolve("switch to Apple", c)["symbols"] == ["AAPL"]
