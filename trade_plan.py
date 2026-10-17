"""Validate model trade legs against supplied quotes; compute payoff from those legs."""

import json
import math
from collections import defaultdict

PLAN_MARKER = "<!--FOLIO_PLAN-->"
FUTURES = {
    "ES=F": 50,
    "MES=F": 5,
    "NQ=F": 20,
    "MNQ=F": 2,
    "GC=F": 100,
    "MGC=F": 10,
    "CL=F": 1000,
    "MCL=F": 100,
}


def parse_plan(text):
    if PLAN_MARKER not in text:
        return {}
    raw = text.split(PLAN_MARKER, 1)[1].strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def build_plan(raw, securities, chains):
    quotes = {s["symbol"]: s for s in securities if not s.get("error")}
    legs, warnings = [], []
    requested = raw.get("legs") or []
    if not isinstance(requested, list) or len(requested) > 12:
        return dict(
            legs=[], curves=[], warnings=["Invalid strategy structure; regenerate it."], complete=False
        )
    for row in requested:
        if not isinstance(row, dict):
            continue
        symbol, kind, side = row.get("symbol"), row.get("instrument"), row.get("side")
        quantity, pct = row.get("quantity"), row.get("allocation_pct")
        quote = quotes.get(symbol)
        if (
            not quote
            or kind not in ("stock", "call", "put", "future")
            or side not in ("buy", "sell")
        ):
            warnings.append("Some recommendations lack matching quotes and were excluded.")
            continue
        if (
            not number(quantity)
            or not 0 < quantity <= 1000000
            or (kind != "stock" and quantity != int(quantity))
        ):
            warnings.append("Some suggested quantities are invalid and were excluded.")
            continue
        pct = pct if number(pct) and 0 <= pct <= 100 else None
        leg = dict(
            symbol=symbol,
            instrument=kind,
            side=side,
            quantity=quantity,
            allocation_pct=pct,
            currency=quote.get("currency"),
            entry=quote.get("price"),
            multiplier=1,
            expiry=None,
            contract=symbol,
        )
        if kind in ("call", "put"):
            chain = chains.get(symbol) or {}
            contract = next(
                (
                    c
                    for c in chain.get("contracts", [])
                    if c.get("symbol") == row.get("contract") and c.get("type") == kind
                ),
                None,
            )
            if not contract or contract.get("multiplier") != 100:
                warnings.append("Some options did not match standard contracts and were excluded.")
                continue
            price = contract.get("ask" if side == "buy" else "bid")
            if not number(price) or price <= 0:
                warnings.append("Some options lack valid bid/ask quotes and were excluded.")
                continue
            leg.update(
                entry=price,
                strike=contract["strike"],
                expiry=contract.get("expiry") or chain["expiry"],
                multiplier=100,
                contract=contract["symbol"],
                iv=contract.get("iv"),
            )
        elif kind == "future":
            if symbol not in FUTURES:
                warnings.append("The futures multiplier is unavailable; payoff is not calculated.")
                continue
            leg.update(multiplier=FUTURES[symbol], continuous=True)
        elif symbol.endswith("=F"):
            warnings.append("Futures cannot be calculated as stock positions.")
            continue
        if not number(leg["entry"]) or leg["entry"] <= 0:
            continue
        legs.append(leg)
    if len(legs) != len(requested):
        # Never graph a partial structure: omitted hedge legs change its risk completely.
        return dict(
            legs=legs, curves=[], warnings=list(dict.fromkeys(warnings)), complete=False
        )
    groups = defaultdict(list)
    for leg in legs:
        groups[leg["symbol"]].append(leg)
    curves = []
    for symbol, group in groups.items():
        if all(leg["instrument"] == "stock" for leg in group):
            continue
        expiries = {l["expiry"] for l in group if l["expiry"]}
        if len(expiries) > 1:
            warnings.append("Options with different expiries need separate valuations and are not combined into one expiry curve.")
            continue
        spot = quotes[symbol]["price"]
        if any(l["instrument"] == "future" for l in group) and any(
            l["instrument"] in ("call", "put") for l in group
        ):
            warnings.append("Futures and equity options have different settlement conventions and are not combined.")
            continue
        curves.append(
            payoff(
                group, spot, next(iter(expiries), None), quotes[symbol].get("currency")
            )
        )
    if len(groups) > 1 and any(l["instrument"] != "stock" for l in legs):
        expiries = {l["expiry"] for l in legs if l["expiry"]}
        currencies = {l["currency"] for l in legs}
        if len(expiries) <= 1 and len(currencies) == 1:
            virtual = []
            for l in legs:
                spot = quotes[l["symbol"]]["price"]
                v = {
                    **l,
                    "entry": l["entry"] / spot * 100,
                    "multiplier": l["multiplier"] * spot / 100,
                }
                if "strike" in l:
                    v["strike"] = l["strike"] / spot * 100
                virtual.append(v)
            combined = payoff(
                virtual, 100, next(iter(expiries), None), next(iter(currencies))
            )
            combined.update(
                symbol=" + ".join(groups),
                combined=True,
                spot=0,
                basis="Portfolio scenario where all underlyings move by the same percentage; not a correlation or probability forecast. Excludes fees, financing, dividends, and early exercise",
            )
            for point in combined["points"]:
                point["price"] = round(point["price"] - 100, 4)
            combined["break_even"] = [round(v - 100, 4) for v in combined["break_even"]]
            curves = [combined]
        else:
            warnings.append("Different currencies or expiries are not combined; inspect each leg separately.")
    return dict(
        legs=legs, curves=curves, warnings=list(dict.fromkeys(warnings)), complete=True
    )


def payoff(legs, spot, expiry, currency):
    def pnl(price):
        total = 0
        for leg in legs:
            direction = 1 if leg["side"] == "buy" else -1
            kind = leg["instrument"]
            value = (
                max(price - leg["strike"], 0)
                if kind == "call"
                else max(leg["strike"] - price, 0) if kind == "put" else price
            )
            total += (
                direction * leg["quantity"] * leg["multiplier"] * (value - leg["entry"])
            )
        return total

    strikes = [l["strike"] for l in legs if "strike" in l]
    low, high = max(0, min([spot * 0.6] + [s * 0.9 for s in strikes])), max(
        [spot * 1.4] + [s * 1.1 for s in strikes]
    )
    prices = sorted(
        set([low + (high - low) * i / 120 for i in range(121)] + strikes + [spot])
    )
    knots = sorted(set([0] + strikes + [max([spot] + strikes) * 2 + 1]))
    breaks = []
    for a, b in zip(knots, knots[1:]):
        va, vb = pnl(a), pnl(b)
        if abs(va) < 1e-8:
            breaks.append(a)
        if va * vb < 0:
            breaks.append(a - va * (b - a) / (vb - va))
    last = knots[-1]
    slope = pnl(last + 1) - pnl(last)
    if slope and (root := last - pnl(last) / slope) > last:
        breaks.append(root)
    values = [pnl(k) for k in knots]
    has_future = any(l["instrument"] == "future" for l in legs)
    downside_slope = pnl(-1) - pnl(0)
    loss_unbounded = slope < -1e-7 or (
        has_future and legs[0]["symbol"] in ("CL=F", "MCL=F") and downside_slope < -1e-7
    )
    gain_unbounded = slope > 1e-7 or (
        has_future and legs[0]["symbol"] in ("CL=F", "MCL=F") and downside_slope > 1e-7
    )
    return dict(
        symbol=legs[0]["symbol"],
        currency=currency,
        spot=spot,
        expiry=expiry,
        points=[dict(price=round(p, 4), pnl=round(pnl(p), 2)) for p in prices],
        max_loss=None if loss_unbounded else round(max(0, -min(values)), 2),
        max_gain=None if gain_unbounded else round(max(0, max(values)), 2),
        break_even=sorted(set(round(v, 4) for v in breaks)),
        scenario=[
            dict(change=v, pnl=round(pnl(spot * (1 + v / 100)), 2))
            for v in [-20, -10, 0, 10, 20]
        ],
        basis=(
            "Same-expiry payoff excluding fees, taxes, dividends, financing, and early exercise"
            if expiry
            else "Price-scenario payoff excluding fees and financing"
        ),
        continuous=has_future,
    )


def resolve_plan_data(raw, securities, chains):
    """Verify any additionally recommended underlying/expiry against the market adapter."""
    import re
    from datetime import datetime
    from conversation import SYMBOL
    from market import security_research, option_chain

    rows = raw.get("legs", [])
    if not isinstance(rows, list) or len(rows) > 12:
        return securities, chains
    securities = list(securities)
    chains = dict(chains)
    known = {s["symbol"] for s in securities}
    symbols = list(
        dict.fromkeys(
            r.get("symbol")
            for r in rows
            if isinstance(r, dict)
            and isinstance(r.get("symbol"), str)
            and SYMBOL.fullmatch(r["symbol"])
        )
    )[:4]
    for symbol in symbols:
        if symbol not in known:
            securities.append(security_research(symbol))
            known.add(symbol)
    for row in rows:
        if (
            not isinstance(row, dict)
            or row.get("instrument") not in ("call", "put")
            or row.get("symbol") not in symbols
        ):
            continue
        symbol = row["symbol"]
        contract = row.get("contract", "")
        if not isinstance(contract, str):
            continue
        if any(
            c.get("symbol") == contract
            for c in chains.get(symbol, {}).get("contracts", [])
        ):
            continue
        match = re.fullmatch(r"([A-Z.]{1,10})(\d{6})([CP])(\d{8})", contract)
        if not match or match[1] != symbol:
            continue
        try:
            expiry = datetime.strptime(match[2], "%y%m%d").date().isoformat()
        except ValueError:
            continue
        fresh = option_chain(symbol, expiry, contract)
        if fresh.get("error"):
            continue
        # Multiple expiry chains may be verified, but build_plan will not mislabel them as one expiry.
        old = chains.get(symbol, {})
        contracts = {
            c["symbol"]: {**c, "expiry": c.get("expiry") or old.get("expiry")}
            for c in old.get("contracts", [])
        }
        contracts.update(
            {
                c["symbol"]: {**c, "expiry": fresh.get("expiry")}
                for c in fresh.get("contracts", [])
            }
        )
        chains[symbol] = {**fresh, "contracts": list(contracts.values())}
    return securities, chains
