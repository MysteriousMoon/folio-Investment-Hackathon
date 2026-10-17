from forecast import forecast


def sample():
    return dict(
        symbol="TEST",
        quote_type="EQUITY",
        price=100,
        currency="USD",
        financial_currency="USD",
        metrics=dict(
            trailingEps=5,
            totalRevenue=1000,
            profitMargins=0.2,
            revenueGrowth=0.2,
            trailingPE=20,
        ),
        financials=[],
    )


def test_forecast_arithmetic_and_path():
    f = forecast(sample())
    assert f["available"]
    b = f["scenarios"][1]
    assert round(b["revenue"], 4) == 1100
    assert round(b["net_income"], 4) == 220
    assert round(b["eps"], 4) == 5.5
    assert round(b["price"], 4) == 110
    assert round(b["return_pct"], 4) == 10
    assert b["path"][0]["return_pct"] == 0
    assert round(b["path"][-1]["return_pct"], 4) == 10
    assert [s["price"] for s in f["scenarios"]] == sorted(
        s["price"] for s in f["scenarios"]
    )
    assert "no assigned probabilities" in f["path_method"]


def test_loss_company_and_fx_not_valued():
    s = sample()
    s["metrics"]["trailingEps"] = -1
    assert not forecast(s)["available"]
    s = sample()
    s["financial_currency"] = "CNY"
    assert not forecast(s)["available"]
    s = sample()
    s["quote_type"] = "FUTURE"
    assert not forecast(s)["available"]


def test_growth_clamped_and_missing():
    s = sample()
    s["metrics"]["revenueGrowth"] = 10
    assert forecast(s)["assumptions"]["growth"] == 0.6
    s["metrics"]["revenueGrowth"] = None
    assert not forecast(s)["available"]


def test_quarterly_growth_used_not_qoq():
    s = sample()
    s["financials"] = [
        dict(period=f"{2024+i//4}-{[3,6,9,12][i%4]:02d}-28", revenue=v)
        for i, v in enumerate([100, 100, 100, 100, 120, 130, 140, 150])
    ]
    f = forecast(s)
    assert round(f["assumptions"]["observed_growth"], 3) == 0.4
    assert f["assumptions"]["quarterly_samples"] == 8
