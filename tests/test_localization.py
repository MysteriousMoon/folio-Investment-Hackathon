from engine import build
from localization import normalize_profile


def test_saved_profile_enum_compatibility_preserves_financial_results():
    legacy = {
        "risk": "\u7a33\u5065",
        "currency": "\u7f8e\u5143",
        "market": "\u7f8e\u80a1",
        "amount": 100000,
        "horizon": 5,
        "holdings": "Existing notes must remain unchanged",
    }
    normalized = normalize_profile(legacy)
    assert normalized == {
        **legacy,
        "risk": "conservative",
        "currency": "USD",
        "market": "US stocks",
    }
    assert legacy["risk"] != normalized["risk"]
    portfolio = build(normalized, 1)
    assert [row["weight"] for row in portfolio["rows"]] == [10, 20, 35, 10, 25]
    assert sum(row["amount"] for row in portfolio["rows"]) == legacy["amount"]
    assert portfolio["rows"][0]["symbol"] == "VTI"
