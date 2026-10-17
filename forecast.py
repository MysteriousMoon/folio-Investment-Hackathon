"""Transparent twelve-month earnings and P/E scenarios, not fitted probabilities."""

import math
from datetime import date


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def forecast(security):
    m = security.get("metrics") or {}
    price, eps = security.get("price"), m.get("trailingEps")
    revenue, margin = m.get("totalRevenue"), m.get("profitMargins")
    base = dict(
        available=False,
        horizon_months=12,
        symbol=security.get("symbol"),
        currency=security.get("currency"),
    )
    if security.get("quote_type") not in ("EQUITY", None):
        return {**base, "reason": "Company earnings and P/E valuation do not apply to this security."}
    if security.get("financial_currency") != security.get("currency"):
        return {**base, "reason": "Financials and prices use different currencies; FX and per-share conventions are needed before valuation."}
    if not all(finite(x) and x > 0 for x in (price, eps, revenue, margin)):
        return {
            **base,
            "reason": "Positive EPS, revenue, or net margin is missing; P/E valuation is unavailable.",
        }
    growth = m.get("revenueGrowth")
    source = "Yahoo Latest reported year-over-year revenue growth"
    rows = sorted(security.get("financials", []), key=lambda r: r["period"])
    yoy = []
    for i in range(4, len(rows)):
        older, newer = rows[i - 4].get("revenue"), rows[i].get("revenue")
        try:
            gap = (
                date.fromisoformat(rows[i]["period"])
                - date.fromisoformat(rows[i - 4]["period"])
            ).days
        except (ValueError, TypeError):
            continue
        if 330 <= gap <= 400 and finite(older) and older > 0 and finite(newer):
            yoy.append(newer / older - 1)
    if yoy:
        values = yoy[-4:]
        growth = sum((i + 1) * v for i, v in enumerate(values)) / sum(
            range(1, len(values) + 1)
        )
        source = "Weighted quarterly year-over-year growth, with higher weights on recent periods"
    if not finite(growth):
        return {**base, "reason": "Year-over-year revenue growth is missing; no extrapolation is made."}
    pe = m.get("trailingPE")
    if not finite(pe) or pe <= 0:
        pe = price / eps
    # Fixed assumptions are visible to the user and independent of Gemini.
    g = max(-0.4, min(0.6, growth * 0.5))
    spread = max(0.05, min(0.2, abs(growth) * 0.25))
    scenarios = []
    for label, delta, margin_factor, pe_factor in [
        ("conservative", -spread, 0.9, 0.8),
        ("base", 0, 1, 1),
        ("optimistic", spread, 1.1, 1.2),
    ]:
        gr = max(-0.8, min(1, g + delta))
        net_margin = min(0.95, margin * margin_factor)
        rev = revenue * (1 + gr)
        profit = rev * net_margin
        # Anchor on reported diluted EPS, hold diluted share count constant.
        projected_eps = eps * (1 + gr) * (net_margin / margin)
        multiple = pe * pe_factor
        target = projected_eps * multiple
        scenarios.append(
            dict(
                name=label,
                growth=gr,
                margin=net_margin,
                revenue=rev,
                net_income=profit,
                eps=projected_eps,
                pe=multiple,
                price=target,
                return_pct=(target / price - 1) * 100,
                path=[
                    dict(
                        month=t,
                        price=price * (target / price) ** (t / 12),
                        return_pct=((target / price) ** (t / 12) - 1) * 100,
                    )
                    for t in range(13)
                ],
            )
        )
    return {
        **base,
        "available": True,
        "scenarios": scenarios,
        "current_price": price,
        "base_eps": eps,
        "assumptions": dict(
            observed_growth=growth,
            growth=g,
            margin=margin,
            pe=pe,
            growth_source=source,
            quarterly_samples=len(rows),
            share_count="Diluted share count held constant",
            model="Revenue× net margin projects earnings, EPS scales with earnings changes, then multiplies scenario P/E; growth continuation 50%, base growth capped at −40% to 60%; conservative/optimistic margins relative to base: 90%/110%, P/E: 80%/120%.",
        ),
        "sensitivity": dict(
            growths=[max(-0.8, g - spread), g, min(1, g + spread)],
            pes=[pe * 0.8, pe, pe * 1.2],
            prices=[
                [eps * (1 + gr) * multiple for multiple in [pe * 0.8, pe, pe * 1.2]]
                for gr in [max(-0.8, g - spread), g, min(1, g + spread)]
            ],
        ),
        "path_method": "Curve interpolates from the current price to the 12-month scenario valuation using geometric interpolation; scenarios have no assigned probabilities and are not monthly price forecasts.",
    }
