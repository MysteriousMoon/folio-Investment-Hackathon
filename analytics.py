"""Transparent portfolio risk simulation and normalized derivative pricing.
All outputs carry their calibration, expiry and pricing assumptions.
"""

import math
import threading
import time
import numpy as np

_cache = {}
_lock = threading.Lock()
STRATEGIES = {
    "protective_put": ("Protective put", [("put", 95, 1)]),
    "call_spread": ("call spread", [("call", 100, 1), ("call", 110, -1)]),
    "put_spread": ("put spread", [("put", 100, 1), ("put", 90, -1)]),
    "covered_call": ("covered call", [("call", 110, -1)]),
    "collar": ("collar protection", [("put", 95, 1), ("call", 110, -1)]),
    "straddle": ("Long straddle", [("call", 100, 1), ("put", 100, 1)]),
    "butterfly": ("Call butterfly", [("call", 90, 1), ("call", 100, -2), ("call", 110, 1)]),
    "iron_condor": (
        "Iron condor",
        [("put", 85, 1), ("put", 90, -1), ("call", 110, -1), ("call", 115, 1)],
    ),
    "futures_hedge": ("Short index futures hedge", []),
    "futures_long": ("Long index futures", []),
}


def normal_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs(kind, spot, strike, years, rate, vol):
    """European option, zero dividend; vega per 1.0 vol, theta per year."""
    if min(spot, strike, years, vol) <= 0:
        raise ValueError("Pricing parameters must be positive")
    root = math.sqrt(years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * years) / (vol * root)
    d2 = d1 - vol * root
    density = math.exp(-d1 * d1 / 2) / math.sqrt(2 * math.pi)
    discount = math.exp(-rate * years)
    gamma = density / (spot * vol * root)
    vega = spot * density * root
    if kind == "call":
        price = spot * normal_cdf(d1) - strike * discount * normal_cdf(d2)
        delta = normal_cdf(d1)
        theta = -spot * density * vol / (
            2 * root
        ) - rate * strike * discount * normal_cdf(d2)
    else:
        price = strike * discount * normal_cdf(-d2) - spot * normal_cdf(-d1)
        delta = normal_cdf(d1) - 1
        theta = -spot * density * vol / (
            2 * root
        ) + rate * strike * discount * normal_cdf(-d2)
    return dict(price=price, delta=delta, gamma=gamma, vega=vega, theta=theta)


def calibration(symbols):
    key = tuple(symbols)
    with _lock:
        value = _cache.get(key)
        if value and time.time() - value[0] < 3600:
            return value[1]
    try:
        import yfinance as yf
        import pandas as pd
        from pathlib import Path
        import os

        yf.set_tz_cache_location(
            str(
                Path(
                    os.getenv("FOLIO_DATA_DIR", str(Path(__file__).parent / "instance"))
                )
                / "yahoo-cache"
            )
        )
        series = []
        for symbol in symbols:
            h = yf.Ticker(symbol).history(period="3y", auto_adjust=True, timeout=8)
            if h.empty:
                raise ValueError("Missing historical data")
            s = h["Close"].copy()
            s.index = s.index.tz_localize(None).normalize()
            series.append(s.rename(symbol))
        prices = pd.concat(series, axis=1).dropna()
        returns = np.log(prices / prices.shift(1)).dropna()
        if len(returns) < 126:
            raise ValueError("Historical sample has fewer than 126 common trading days")
        cov = returns.cov().to_numpy() * 252
        logmean = returns.mean().to_numpy() * 252
        result = dict(
            cov=cov,
            mean=logmean,
            source="Yahoo Finance · 3  years of adjusted closes on common trading dates",
            count=len(returns),
            start=str(returns.index[0].date()),
            end=str(returns.index[-1].date()),
            prices=prices.to_numpy(),
        )
        with _lock:
            _cache[key] = (time.time(), result)
        return result
    except Exception:
        return None


def model_inputs(portfolio, historical=True):
    symbols = [r.get("symbol") for r in portfolio["rows"]]
    actual = calibration(symbols) if historical and all(symbols) else None
    if actual:
        return actual
    vol = np.array([0.35, 0.19, 0.065, 0.18, 0.01])
    # Factor loadings produce a positive definite correlation matrix by construction.
    load = np.array(
        [[0.85, 0.15, 0], [0.80, 0, 0], [-0.15, 0.65, 0], [0.05, 0.15, 0.55], [0, 0, 0]]
    )
    corr = load @ load.T
    np.fill_diagonal(corr, 1)
    return dict(
        cov=np.outer(vol, vol) * corr,
        mean=np.zeros(5),
        source="Parameter scenario · Annual volatility 35/19/6.5/18/1%, factor correlation matrix",
        count=0,
        start=None,
        end=None,
        prices=None,
    )


def positions(portfolio, vol, years, rate):
    p = portfolio["profile"]
    weights = np.array([r["weight"] / 100 for r in portfolio["rows"]])
    strategies = p.get("strategies", [])
    budget = min(p.get("premium_budget", 1) / 100, weights[4])
    ratio = p.get("hedge_ratio", 50) / 100
    option_count = max(
        1, sum(k not in ("futures_hedge", "futures_long") for k in strategies)
    )
    plans = []
    remaining_cash = weights[4]
    short_calls = 0.0
    for key in strategies[:3]:
        if key not in STRATEGIES:
            continue
        name, legs = STRATEGIES[key]
        if not legs:
            notional = (weights[0] + weights[1]) * ratio
            if key == "futures_long":
                notional = min(notional, 0.20)
            notional = min(notional, remaining_cash / 0.10)
            margin = notional * 0.10
            remaining_cash -= margin
            plans.append(
                dict(
                    key=key,
                    name=name,
                    legs=[],
                    units=0,
                    notional=notional,
                    margin=margin,
                    premium=0,
                    delta=(-1 if key == "futures_hedge" else 1) * notional,
                    gamma=0,
                    vega=0,
                    theta=0,
                    index=1,
                )
            )
            continue
        prices = [bs(kind, 100, strike, years, rate, vol) for kind, strike, qty in legs]
        net = sum(g["price"] * leg[2] for g, leg in zip(prices, legs))
        if key in ("protective_put", "collar", "covered_call"):
            target = max(0, weights[0] - short_calls) * ratio
            units = target / 100
        else:
            # Trade size uses bounded capital-at-risk, not net credit received.
            width = 5 if key == "iron_condor" else 10
            unit_risk = width + net if key == "iron_condor" else max(net, 0.01)
            units = min(budget / option_count / max(unit_risk, 0.01), 0.20 / 100)
        if net > 0:
            units = min(units, budget / option_count / net, remaining_cash / net)
        if key in ("collar", "covered_call"):
            short_calls += units * 100
        premium = units * net
        margin = units * 5 if key == "iron_condor" else 0
        if margin > remaining_cash:
            units *= remaining_cash / margin
            margin = remaining_cash
            premium = units * net
        remaining_cash -= max(0, premium) + margin
        plans.append(
            dict(
                key=key,
                name=name,
                legs=[
                    dict(kind=k, strike=s, quantity=q, price=round(g["price"], 4))
                    for (k, s, q), g in zip(legs, prices)
                ],
                units=units,
                notional=units * 100,
                margin=margin,
                premium=premium,
                delta=units
                * 100
                * sum(g["delta"] * l[2] for g, l in zip(prices, legs)),
                gamma=units * sum(g["gamma"] * l[2] for g, l in zip(prices, legs)),
                vega=units * sum(g["vega"] * l[2] for g, l in zip(prices, legs)),
                theta=units * sum(g["theta"] * l[2] for g, l in zip(prices, legs)),
                index=0,
            )
        )
    return plans


def overlay_pnl(plans, asset_returns, years, rate):
    pnl = np.zeros(len(asset_returns))
    for p in plans:
        change = asset_returns[:, p["index"]]
        if not p["legs"]:
            pnl += p["delta"] * change
            continue
        terminal = 100 * (1 + change)
        payoff = np.zeros(len(asset_returns))
        for leg in p["legs"]:
            intrinsic = (
                np.maximum(terminal - leg["strike"], 0)
                if leg["kind"] == "call"
                else np.maximum(leg["strike"] - terminal, 0)
            )
            payoff += leg["quantity"] * intrinsic
        # Premium is paid from the cash bucket; include its financing opportunity cost.
        pnl += p["units"] * payoff - p["premium"] * (1 + asset_returns[:, 4])
    return pnl


def analyze(portfolio, months=3, drift="zero", historical=True):
    inputs = model_inputs(portfolio, historical)
    cov = inputs["cov"]
    vols = np.sqrt(np.maximum(np.diag(cov), 1e-10))
    sigma = max(0.01, float(vols[0]))
    rate = 0.03
    years = months / 12
    weights = np.array([r["weight"] / 100 for r in portfolio["rows"]])
    plans = positions(portfolio, sigma, years, rate)
    eig, vec = np.linalg.eigh(cov)
    factor = vec @ np.diag(np.sqrt(np.maximum(eig, 1e-10)))
    rng = np.random.default_rng(20261017)
    mean = inputs["mean"] if drift == "historical" and inputs["count"] else np.zeros(5)
    log_changes = (
        rng.standard_normal((20000, 5)) @ factor.T * math.sqrt(years) + mean * years
    )
    assets = np.exp(log_changes) - 1
    core = assets @ weights
    overlay = overlay_pnl(plans, assets, years, rate)
    total = core + overlay
    exposures = weights.copy()
    for p in plans:
        exposures[p["index"]] += p["delta"]
    annual_vol = math.sqrt(max(0, float(exposures @ cov @ exposures)))
    beta = float(exposures @ cov[:, 1] / cov[1, 1]) if cov[1, 1] > 0 else None
    q = np.quantile(total, [0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99])
    tail = total[total <= q[1]]
    sample_mean = float(total.mean())
    std = float(total.std())
    skew = float(np.mean(((total - sample_mean) / std) ** 3)) if std > 0 else 0
    kurt = float(np.mean(((total - sample_mean) / std) ** 4) - 3) if std > 0 else 0
    edges = np.histogram_bin_edges(np.concatenate([core, total]) * 100, bins=36)
    counts, _ = np.histogram(total * 100, bins=edges)
    base_counts, _ = np.histogram(core * 100, bins=edges)
    # A synchronized equity shock curve; non-equity returns held at zero.
    x = np.linspace(-0.5, 0.5, 81)
    curve_assets = np.zeros((len(x), 5))
    curve_assets[:, 0] = x
    curve_assets[:, 1] = x
    base_curve = curve_assets @ weights
    hedge_curve = base_curve + overlay_pnl(plans, curve_assets, years, rate)
    base_var = max(0, -float(np.quantile(core, 0.05)))

    def percent(v):
        return round(float(v) * 100, 3)

    history_drawdown = None
    if inputs["prices"] is not None:
        values = (inputs["prices"] / inputs["prices"][0]) @ weights
        history_drawdown = percent(np.min(values / np.maximum.accumulate(values) - 1))
    metrics = dict(
        annual_vol=percent(annual_vol),
        beta=round(beta, 3) if beta is not None else None,
        var95=percent(max(0, -q[1])),
        cvar95=percent(max(0, -tail.mean())),
        base_var95=percent(base_var),
        probability_loss=percent(np.mean(total < 0)),
        mean=percent(sample_mean),
        median=percent(q[3]),
        p01=percent(q[0]),
        p05=percent(q[1]),
        p25=percent(q[2]),
        p75=percent(q[4]),
        p95=percent(q[5]),
        p99=percent(q[6]),
        skewness=round(skew, 3),
        excess_kurtosis=round(kurt, 3),
        historical_core_max_drawdown=history_drawdown,
        delta_equivalent=percent(sum(exposures[:2])),
        gamma_1pct=round(sum(p["gamma"] for p in plans) * 0.5 * 100, 5),
        vega_1point=round(sum(p["vega"] for p in plans), 5),
        theta_daily=round(sum(p["theta"] for p in plans) / 365 * 100, 5),
        gross_notional=percent(
            sum(weights)
            + sum(
                p["notional"]
                * (sum(abs(l["quantity"]) for l in p["legs"]) if p["legs"] else 1)
                for p in plans
            )
        ),
        premium=percent(sum(p["premium"] for p in plans)),
        margin=percent(sum(p["margin"] for p in plans)),
    )
    clean_plans = []
    for p in plans:
        clean_plans.append(
            dict(
                name=p["name"],
                key=p["key"],
                legs=p["legs"],
                notional_pct=percent(p["notional"]),
                premium_pct=percent(p["premium"]),
                margin_pct=percent(p["margin"]),
                delta_pct=percent(p["delta"]),
                description=(
                    "Index futures use broad-equity returns as a proxy; scenario margin ratio 10%."
                    if not p["legs"]
                    else "Normalized underlying price 100; European zero-dividend pricing, settled at expiry."
                ),
            )
        )
    return dict(
        version=portfolio["version"],
        months=months,
        scenarios=20000,
        seed=20261017,
        drift=drift,
        source=inputs["source"],
        sample_count=inputs["count"],
        sample_start=inputs["start"],
        sample_end=inputs["end"],
        metrics=metrics,
        baseline=dict(
            annual_vol=percent(math.sqrt(max(0, float(weights @ cov @ weights)))),
            beta=(
                round(float(weights @ cov[:, 1] / cov[1, 1]), 3)
                if cov[1, 1] > 0
                else None
            ),
            var95=percent(base_var),
            cvar95=percent(
                max(0, -float(core[core <= np.quantile(core, 0.05)].mean()))
            ),
            median=percent(np.median(core)),
            p05=percent(np.quantile(core, 0.05)),
            p95=percent(np.quantile(core, 0.95)),
        ),
        positions=clean_plans,
        histogram=[
            dict(
                low=round(float(edges[i]), 2),
                high=round(float(edges[i + 1]), 2),
                probability=round(float(c) / len(total) * 100, 3),
                base_probability=round(float(base_counts[i]) / len(core) * 100, 3),
            )
            for i, c in enumerate(counts)
        ],
        payoff=[
            dict(shock=percent(s), core=percent(c), combined=percent(t))
            for s, c, t in zip(x, base_curve, hedge_curve)
        ],
        correlation=np.round(cov / np.outer(vols, vols), 3).tolist(),
        annual_vols=[percent(v) for v in vols],
        assumptions=dict(
            rate_pct=3,
            pricing_vol_pct=percent(sigma),
            normalized_spot=100,
            dividend_yield=0,
            margin_rate_pct=10,
            drift=(
                "Annual historical mean log return"
                if drift == "historical" and inputs["count"]
                else "Annual log drift: 0"
            ),
            model="Correlated geometric Brownian motion; Black–Scholes  European options; linear futures exposure",
            scope="Hold through option expiry without rebalancing. Excludes volatility surfaces, early exercise, daily futures margin calls, basis jumps, taxes, fees, and FX. Margin is not maximum loss.",
            risk_units="VaR/CVaR measure end-of-horizon loss as a percentage of initial NAV; Beta relative to broad-market proxy; Greeks normalized by NAV; Vega for volatility +1 percentage points, Theta for  1-day NAV percentage-point change. Gamma for the underlying +1% second-order NAV change.",
        ),
    )
