"""Convert the saved allocation into a priced, versioned shopping list."""

import math
from conversation import SYMBOL
from market import quotes


def validate_targets(raw):
    if not isinstance(raw, list) or len(raw) > 12:
        return []
    groups = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        b, symbol, share = item.get("bucket"), item.get("symbol"), item.get("share")
        if (
            type(b) is not int
            or b not in range(5)
            or not isinstance(symbol, str)
            or not SYMBOL.fullmatch(symbol.upper())
            or "=" in symbol
            or "^" in symbol
            or type(share) not in (int, float)
            or not math.isfinite(share)
            or not 0 < share <= 100
        ):
            continue
        groups.setdefault(b, []).append(
            dict(
                bucket=b,
                symbol=symbol.upper(),
                share=share,
                reason=str(item.get("reason", ""))[:300],
            )
        )
    return [
        v
        for group in groups.values()
        if abs(sum(v["share"] for v in group) - 100) < 0.001
        and len({v["symbol"] for v in group}) == len(group)
        for v in group
    ]


def purchase_list(portfolio):
    if not portfolio:
        return dict(version=0, items=[], strategies=[])
    p = portfolio["profile"]
    targets = validate_targets(p.get("purchase_targets"))
    items = []
    for bucket, row in enumerate(portfolio["rows"]):
        if not row["weight"]:
            continue
        selected = [t for t in targets if t["bucket"] == bucket]
        if not selected:
            selected = [dict(symbol=row.get("symbol"), share=100, reason=row["reason"])]
        for t in selected:
            weight = row["weight"] * t["share"] / 100
            items.append(
                dict(
                    symbol=t["symbol"],
                    name=row["name"],
                    weight=round(weight, 4),
                    amount=(
                        round(p["amount"] * weight / 100, 2)
                        if p.get("amount")
                        else None
                    ),
                    reason=t["reason"],
                    bucket=bucket,
                )
            )
    symbols = list(dict.fromkeys(i["symbol"] for i in items if i["symbol"]))
    market = []
    for offset in range(0, len(symbols), 8):
        market.extend(quotes(",".join(symbols[offset : offset + 8])).get("quotes", []))
    by_symbol = {q["symbol"]: q for q in market}
    currencies = {"USD": "USD", "CAD": "CAD", "CNY": "CNY"}
    for i in items:
        q = by_symbol.get(i["symbol"], {})
        i.update(
            price=q.get("price"), quote_currency=q.get("currency"), as_of=q.get("date")
        )
        same = (
            currencies.get(p.get("currency")) == q.get("currency")
            and q.get("currency") is not None
        )
        price = q.get("price")
        lot = 100 if i["symbol"] and i["symbol"].endswith((".SS", ".SZ")) else 1
        i["quantity"] = (
            math.floor(i["amount"] / price / lot) * lot
            if same
            and i["amount"] is not None
            and price
            and price > 0
            and not i["symbol"].endswith(".HK")
            else None
        )
        i["estimated_cost"] = (
            round(i["quantity"] * price, 2) if i["quantity"] is not None else None
        )
        i["remainder"] = (
            round(i["amount"] - i["estimated_cost"], 2)
            if i["estimated_cost"] is not None
            else None
        )
        i["quantity_note"] = (
            "Confirm the Hong Kong board-lot size"
            if i["symbol"] and i["symbol"].endswith(".HK")
            else (
                "Confirm budget/currency or quotes"
                if i["quantity"] is None
                else "Estimated in whole shares; remainder held as cash"
            )
        )
    return dict(
        version=portfolio["version"],
        items=items,
        currency=p.get("currency"),
        amount=p.get("amount"),
        strategies=p.get("strategies", []),
        hedges=portfolio.get("hedges", []),
    )
