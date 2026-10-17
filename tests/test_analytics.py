import math
import numpy as np
import pytest
from analytics import bs, analyze, positions, overlay_pnl, STRATEGIES
from engine import build, extract


def test_put_call_parity_and_greeks():
    c = bs("call", 100, 100, 1, 0.03, 0.2)
    p = bs("put", 100, 100, 1, 0.03, 0.2)
    assert c["price"] - p["price"] == pytest.approx(100 - 100 * math.exp(-0.03))
    assert c["delta"] - p["delta"] == pytest.approx(1)
    assert c["gamma"] == pytest.approx(p["gamma"])
    epsilon = 0.001
    fd = (
        bs("call", 100 + epsilon, 100, 1, 0.03, 0.2)["price"]
        - bs("call", 100 - epsilon, 100, 1, 0.03, 0.2)["price"]
    ) / (2 * epsilon)
    assert c["delta"] == pytest.approx(fd, abs=1e-7)


@pytest.mark.parametrize("strategy", list(STRATEGIES))
def test_strategy_finite_and_capital_reserved(strategy):
    result = analyze(
        build({"risk": "balanced", "strategies": [strategy]}, 1), historical=False
    )
    assert result["positions"][0]["key"] == strategy
    m = result["metrics"]
    assert all(math.isfinite(v) for v in m.values() if v is not None)
    assert sum(b["probability"] for b in result["histogram"]) == pytest.approx(
        100, abs=0.02
    )
    assert m["cvar95"] >= m["var95"]
    assert m["premium"] <= 1.001
    assert m["margin"] <= 10.001
    assert m["p01"] <= m["p05"] <= m["median"] <= m["p95"] <= m["p99"]


def test_put_protection_lifts_left_tail():
    result = analyze(
        build(
            {
                "risk": "balanced",
                "strategies": ["protective_put"],
                "premium_budget": 1,
                "hedge_ratio": 100,
            },
            1,
        ),
        historical=False,
    )
    assert result["metrics"]["var95"] < result["metrics"]["base_var95"]
    assert result["positions"][0]["delta_pct"] < 0


def test_call_spread_bounded_payoff():
    plans = positions(
        build({"risk": "balanced", "strategies": ["call_spread"]}, 1), 0.35, 0.25, 0.03
    )
    assets = np.zeros((4, 5))
    assets[:, 0] = [-0.9, 0, 0.2, 2]
    pnl = overlay_pnl(plans, assets, 0.25, 0.03)
    assert pnl[0] == pytest.approx(pnl[1])
    assert pnl[2] == pytest.approx(pnl[3])
    assert -pnl[0] <= 0.011


def test_futures_reduces_beta():
    plain = analyze(build({"risk": "balanced"}, 1), historical=False)
    hedge = analyze(
        build({"risk": "balanced", "strategies": ["futures_hedge"]}, 1), historical=False
    )
    assert hedge["metrics"]["beta"] < plain["metrics"]["beta"]
    assert hedge["metrics"]["margin"] > 0


def test_conversation_multiple_derivatives_and_clear():
    p = extract("add collar protection and futures hedge, premium budget 2%, hedge ratio70%", {})
    assert p["strategies"] == ["collar", "futures_hedge"]
    assert p["premium_budget"] == 2 and p["hedge_ratio"] == 70
    assert extract("remove derivatives", p)["strategies"] == []


def test_seed_reproducible():
    p = build({"strategies": ["straddle"]}, 1)
    assert (
        analyze(p, historical=False)["metrics"]
        == analyze(p, historical=False)["metrics"]
    )


def test_premium_financed_from_actual_cash_return():
    plans = positions(
        build({"risk": "balanced", "strategies": ["call_spread"]}, 1), 0.35, 0.25, 0.03
    )
    scenarios = np.zeros((2, 5))
    scenarios[:, 0] = -0.5
    scenarios[1, 4] = 0.1
    pnl = overlay_pnl(plans, scenarios, 0.25, 0.03)
    assert pnl[1] - pnl[0] == pytest.approx(-plans[0]["premium"] * 0.1)


def test_multiple_strategies_never_reserve_more_cash_than_available():
    p = build(
        {
            "risk": "aggressive",
            "strategies": ["iron_condor", "futures_long", "protective_put"],
            "premium_budget": 5,
            "hedge_ratio": 100,
        },
        1,
    )
    plans = positions(p, 0.35, 0.25, 0.03)
    used = sum(max(0, r["premium"]) + r["margin"] for r in plans)
    assert used <= p["rows"][-1]["weight"] / 100 + 1e-10


def test_comparison_uses_shared_histogram_bins_and_complete_probabilities():
    result = analyze(
        build({"risk": "balanced", "strategies": ["collar", "futures_hedge"]}, 1),
        historical=False,
    )
    assert sum(b["probability"] for b in result["histogram"]) == pytest.approx(
        100, abs=0.02
    )
    assert sum(b["base_probability"] for b in result["histogram"]) == pytest.approx(
        100, abs=0.02
    )
    assert result["baseline"]["var95"] == result["metrics"]["base_var95"]
    assert result["baseline"]["cvar95"] >= result["baseline"]["var95"]


def test_comparison_without_derivatives_has_identical_distributions():
    result = analyze(build({"risk": "balanced"}, 1), historical=False)
    assert all(b["probability"] == b["base_probability"] for b in result["histogram"])
    for key in ["annual_vol", "beta", "var95", "cvar95", "median"]:
        assert result["baseline"][key] == result["metrics"][key]
