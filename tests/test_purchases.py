from purchases import validate_targets, purchase_list
from engine import build
from conversation import resolve


def test_purchase_intent():
    assert resolve("give me the NVIDIA purchase list")["kind"] == "allocation"
    assert resolve("help me design a portfolio")["kind"] == "allocation"
    assert resolve("NVIDIA financials")["kind"] == "security"


def test_validate_groups():
    assert not validate_targets([dict(bucket=0, symbol="NVDA", share=50)])
    assert not validate_targets([dict(bucket=0, symbol="ES=F", share=100)])
    assert not validate_targets([dict(bucket=0, symbol="NVDA", share=float("nan"))])
    assert (
        len(
            validate_targets(
                [
                    dict(bucket=0, symbol="NVDA", share=60),
                    dict(bucket=0, symbol="AMD", share=40),
                ]
            )
        )
        == 2
    )


def test_purchase_sizing_and_currency(monkeypatch):
    monkeypatch.setattr(
        "purchases.quotes",
        lambda raw: {
            "quotes": [
                dict(symbol=s, price=120, currency="USD", date="2026-10-17")
                for s in raw.split(",")
            ]
        },
    )
    p = build(
        dict(
            amount=10000,
            currency="USD",
            market="US stocks",
            purchase_targets=[
                dict(bucket=0, symbol="NVDA", share=60),
                dict(bucket=0, symbol="AMD", share=40),
            ],
        ),
        9,
    )
    result = purchase_list(p)
    assert result["version"] == 9
    assert sum(i["weight"] for i in result["items"]) == 100
    assert result["items"][0]["symbol"] == "NVDA"
    assert result["items"][0]["quantity"] == 10
    assert sum(i["amount"] for i in result["items"]) == 10000
    p["profile"]["currency"] = "CAD"
    assert all(i["quantity"] is None for i in purchase_list(p)["items"])
