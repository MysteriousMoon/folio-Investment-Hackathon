import pandas as pd
import pytest
import market
import yfinance as yf


@pytest.mark.parametrize(
    "annual_dividend,raw,expected", [(1.39, 0.99, 0.01), (None, 0.47, 0.0047)]
)
def test_quote_units_and_research_series(monkeypatch, annual_dividend, raw, expected):
    class Ticker:
        quarterly_income_stmt = pd.DataFrame()

        def get_info(self):
            return {
                "regularMarketPrice": 139,
                "regularMarketPreviousClose": 138,
                "longName": "Test company",
                "currency": "USD",
                "dividendRate": annual_dividend,
                "dividendYield": raw,
                "trailingPE": 20,
            }

        def history(self, **kwargs):
            return pd.DataFrame(
                {"Close": range(100, 140), "Volume": [1000] * 40},
                index=pd.date_range("2026-01-01", periods=40, tz="UTC"),
            )

        def get_news(self, **kwargs):
            return []

    monkeypatch.setattr(yf, "Ticker", lambda symbol: Ticker())
    market._cache.pop("research:TESTY", None)
    d = market.security_research("TESTY")
    assert d["symbol"] == "TESTY" and len(d["history"]) == 40
    assert d["metrics"]["dividendYield"] == pytest.approx(expected)
    assert d["security_risk"]["samples"] == 39
    assert d["security_risk"]["cvar95"] >= d["security_risk"]["var95"]
