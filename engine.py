"""Deterministic suitability baseline. No prices or estimated returns are invented."""

import re

FIELDS = {
    "risk": "risk tolerance (conservative / balanced / aggressive, or level 1–5)",
    "horizon": "investment horizon (e.g. 5 years)",
    "amount": "planned investment amount (e.g. 200,000)",
    "market": "accessible markets (US stocks / A  shares / Hong Kong stocks)",
    "holdings": "current holdings and near-term liquidity needs (none is acceptable)",
    "currency": "capital currency (CNY / USD / CAD)",
}


def extract(text, profile):
    p = dict(profile)
    for pattern, risk in [
        (r"conservative|cautious|low risk|(?:risk|level).*?[12]\s*(?:level)?", "conservative"),
        (r"balanced|neutral|moderate|(?:risk|level).*?3\s*(?:level)?", "balanced"),
        (r"aggressive|growth|high risk|(?:risk|level).*?[45]\s*(?:level)?", "aggressive"),
    ]:
        if re.search(pattern, text):
            p["risk"] = risk
    if re.search("lower risk|more conservative", text):
        p["risk"] = "conservative"
    m = re.search(r"(\d+(?:\.\d+)?)\s*(years?|months?)", text)
    if m:
        p["horizon"] = float(m[1]) * (1 if m[2] in ("year", "years") else 1 / 12)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(k CNY|k USD|k CAD|k|CNY|USD|CAD)", text)
    if m:
        n = float(m[1]) * (1000 if m[2].startswith("k") else 1)
        if 0 < n <= 1e10:
            p["amount"] = n
    for label in ["US stocks", "A shares", "A shares", "Hong Kong stocks"]:
        if label in text:
            p["market"] = label.replace("  ", " ")
    for label in ["USD", "CAD", "CNY"]:
        if label in text:
            p["currency"] = label
    if re.search(r"AI|artificial intelligence|Compute|NVIDIA|NVDA", text, re.I):
        p["theme"] = "AI"
    elif re.search("clean energy|healthcare|gold|technology", text):
        p["theme"] = re.search("clean energy|healthcare|gold|technology", text)[0]
    if re.search("holdings|already hold|none|no holdings|liquidity needs|emergency", text):
        p["holdings"] = text[:600]
    if re.search("hedge|protection|drawdown", text):
        p["hedge"] = True
    if re.search("options", text):
        p["options"] = True
    strategies = list(p.get("strategies", []))
    aliases = {
        "protective_put": r"protective put|Protective put|option protection|buy put",
        "call_spread": r"call spread|bull spread",
        "put_spread": r"put spread|bear spread",
        "covered_call": r"covered call|covered call",
        "collar": r"collar",
        "straddle": r"straddle|straddle|long straddle",
        "butterfly": r"butterfly",
        "iron_condor": r"iron condor",
        "futures_hedge": r"futures hedge|short futures|short futures",
        "futures_long": r"long futures|long futures",
    }
    if re.search("remove derivatives|remove derivatives|spot only", text):
        strategies = []
    else:
        found = [key for key, pattern in aliases.items() if re.search(pattern, text)]
        if "options" in text and not any(
            k not in ("futures_hedge", "futures_long") for k in found
        ):
            found.append("protective_put" if p.get("hedge") else "call_spread")
        if "futures" in text and not any(k.startswith("futures") for k in found):
            found.append("futures_hedge")
        for key in found:
            if key not in strategies:
                strategies.append(key)
    p["strategies"] = strategies[-3:]
    for pattern, key, limit in [
        (r"(?:premium budget|option budget)\s*(\d+(?:\.\d+)?)\s*%", "premium_budget", 5),
        (r"(?:hedge ratio|protection ratio)\s*(\d+(?:\.\d+)?)\s*%", "hedge_ratio", 100),
    ]:
        match = re.search(pattern, text)
        if match:
            p[key] = min(limit, max(0, float(match[1])))
    return p


def build(p, version, planned_weights=None):
    risk = p.get("risk", "balanced")
    short = p.get("horizon", 5) < 2
    weights = (
        [10, 10, 25, 5, 50]
        if short
        else {
            "conservative": [10, 20, 35, 10, 25],
            "balanced": [20, 35, 25, 10, 10],
            "aggressive": [30, 45, 10, 10, 5],
        }[risk]
    )
    if planned_weights is not None:
        weights = planned_weights
    theme = p.get("theme", "Global growth")
    market = p.get("market")
    us = market == "US stocks"
    names = [
        f"{theme} thematic equity basket",
        "Broad equities",
        "Short/intermediate high-quality Treasuries",
        "gold",
        "Cash / Short-term Treasury bills",
    ]
    examples = (
        [
            ("SMH", "Semiconductor fund with some  AI infrastructure exposure"),
            ("VT", "Broad global equities"),
            ("VGIT", "US intermediate Treasuries, with USD and duration risk"),
            ("IAU", "Physical-gold trust; verify fees"),
            ("SGOV", "USD short-term Treasury bill fund"),
        ]
        if us
        else [
            ("Locally available thematic fund", "Confirm market access and account permissions for specific products"),
            ("Locally available low-cost broad-market fund", "Check regional, sector, and holdings overlap"),
            ("Local-currency short/intermediate high-quality government bond fund", "Verify duration, issuer, and currency"),
            ("Locally available gold fund", "Verify benchmark and product structure"),
            ("Local-currency cash or short-term government bonds", "Prioritize near-term funding needs"),
        ]
    )
    if us and theme != "AI":
        theme_examples = {
            "technology": ("VGT", "US information-technology fund"),
            "healthcare": ("VHT", "US healthcare fund"),
            "clean energy": ("ICLN", "Global clean-energy equity fund"),
            "gold": ("GDX", "Gold-mining equities, distinct from physical gold"),
        }
        examples[0] = theme_examples.get(
            theme, ("VTI", "US equity market; theme needs clarification")
        )
    if p.get("focus_symbol"):
        from conversation import SYMBOL

        symbol = p["focus_symbol"]
        if isinstance(symbol, str) and SYMBOL.fullmatch(symbol):
            names[0] = symbol + " · theme allocation"
            examples[0] = (symbol, "Allocate to the current security after checking concentration against existing exposure")
    reasons = [
        "Express the thesis through a limited allocation rather than concentrating the whole portfolio in one theme.",
        "Diversifies theme concentration, although broad funds may also hold technology companies.",
        "May cushion equity declines during recession or rate cuts; inflation and rate hikes can hurt both stocks and bonds.",
        "Adds a different risk source without guaranteeing gains during crises.",
        "Meets liquidity and rebalancing needs, with inflation risk.",
    ]
    rows = [
        dict(
            name=n,
            weight=w,
            amount=round(p["amount"] * w / 100, 2) if p.get("amount") else None,
            example=e[0],
            symbol=e[0] if us or (i == 0 and p.get("focus_symbol")) else None,
            detail=e[1],
            reason=r,
        )
        for i, (n, w, e, r) in enumerate(zip(names, weights, examples, reasons))
    ]
    if p.get("amount"):
        rows[-1]["amount"] = round(p["amount"] - sum(r["amount"] for r in rows[:-1]), 2)
    missing = [k for k in FIELDS if k not in p]
    hedges = [
        dict(
            name="Limit theme exposure first",
            text=f"Theme budget {weights[0]}%; Check existing holdings and manage concentration across the whole account. Reducing exposure also reduces upside participation.",
        ),
        dict(
            name="Conditional Treasury diversification",
            text="Short/intermediate Treasuries reduce equity concentration. AI  valuation declines may benefit Treasuries when accompanied by recession and rate cuts. Inflation or rising rates can hurt both stocks and bonds. Long-duration Treasuries are more rate-sensitive and are not a direct inverse of  AI  as a direct inverse asset.",
        ),
        dict(
            name="Protective put (optional)",
            text="Research only after confirming permissions, holdings, protection horizon, and premium budget. Contract counts depend on market value, underlying price, multiplier, and cross-hedge error. No contracts or costs are fabricated; cross-security hedges carry basis risk.",
        ),
    ]
    stress = []
    for name, shocks in [
        ("Theme valuation decline", [-35, -15, 3, 0, 0]),
        ("Inflation and rising rates", [-25, -20, -8, -5, 0]),
        ("Slowing growth and rate cuts", [-25, -20, 5, 5, 0]),
    ]:
        impact = round(sum(w * s / 100 for w, s in zip(weights, shocks)), 2)
        stress.append(
            dict(
                name=name,
                shocks=shocks,
                impact=impact,
                loss=round(p["amount"] * impact / 100, 2) if p.get("amount") else None,
            )
        )
    return dict(
        title=f"{theme} · {risk} allocation",
        profile=p,
        version=version,
        rows=rows,
        missing=missing,
        status="Incomplete" if missing else "Research draft",
        hedges=hedges,
        stress=stress,
        assumptions="Stress scenarios weight manually specified asset shocks; they are not historical backtests, forecasts, or maximum-loss estimates. No live prices are used.",
        rebalance="Review quarterly; when an asset deviates from target by 5 percentage points, consider rebalancing with taxes, costs, liquidity, and new contributions in mind. Review earlier if the thesis or funding needs change.",
    )


def reply(p, portfolio):
    parts = []
    if p.get("theme"):
        parts.append(
            f'Recorded your bullish view on {p["theme"]}. I will consider the theme thesis separately from the account risk budget.'
        )
    if p.get("risk"):
        parts.append(
            f'Using {p["risk"]} risk preference, I updated the allocation on the right. '
            + (
                "The horizon is short; prioritize liquidity."
                if p.get("horizon", 5) < 2
                else "The remaining allocation uses broad equities, Treasuries, gold, and cash, totaling 100%."
            )
        )
    else:
        parts.append("The right side shows a draft using balanced assumptions; risk preferences remain to be confirmed.")
    if p.get("hedge"):
        parts.append(
            "The report describes three risk-management paths: theme limits, Treasury diversification, and option protection."
        )
    if p.get("strategies"):
        parts.append(
            "Derivatives exposure analysis is available in the right-side risk panel, including strategy legs, Greeks, return distributions and expiry payoff."
        )
    if portfolio["missing"]:
        k = portfolio["missing"][0]
        parts.append("Next, please tell me your " + FIELDS[k] + ".")
    else:
        parts.append(
            "The basic information is complete. Why do you favor this theme, and what would change your view? Portfolio details, stress scenarios, and hedge conditions are in the report."
        )
    parts.append("Adjust the amount, horizon, or risk level to update the portfolio.")
    return "\n\n".join(parts)
