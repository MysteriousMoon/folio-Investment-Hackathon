"""Separate the model's conversation and its compact Markdown strategy card."""

MARKER = "<!--FOLIO_CARD-->"


def split_output(text, final=False):
    if MARKER in text:
        left, card = text.split(MARKER, 1)
        from trade_plan import PLAN_MARKER

        card = card.split(PLAN_MARKER, 1)[0]
        if not final:
            for size in range(len(PLAN_MARKER) - 1, 0, -1):
                if card.endswith(PLAN_MARKER[:size]):
                    card = card[:-size]
                    break
        return left.rstrip(), card.strip()
    if not final:
        for size in range(len(MARKER) - 1, 0, -1):
            if text.endswith(MARKER[:size]):
                return text[:-size], ""
    return text, ""


def fallback_card(workspace, chain=None):
    import re

    query = workspace.get("query", "")
    symbols = workspace.get("symbols", [])
    if symbols and re.search(
        "huge moves|large moves|sharp moves|high volatility|large volatility|huge volatility|no clear direction", query
    ):
        chain = chain or {}
        calls = {
            c.get("strike"): c
            for c in chain.get("contracts", [])
            if c.get("type") == "call"
        }
        puts = {
            c.get("strike"): c
            for c in chain.get("contracts", [])
            if c.get("type") == "put"
        }
        pairs = [
            (k, c, puts[k])
            for k, c in calls.items()
            if k is not None
            and k in puts
            and all(
                isinstance(v.get("ask"), (int, float)) and v["ask"] > 0
                for v in (c, puts[k])
            )
        ]
        title = f"### {symbols[0]} · Long straddle\n\nExpecting large moves without a direction: buy a same-strike, same-expiry Call and Put.\n\n"
        if pairs and chain.get("spot"):
            k, c, p = min(pairs, key=lambda v: abs(v[0] - chain["spot"]))
            premium = c["ask"] + p["ask"]
            title += "| Action (per unit) | Contract | Reference Ask |\n|---|---|---|\n"
            title += f"| Buy 1 contract Call · K={k:g} | {c['symbol']} | ${c['ask']:.2f} |\n| Buy 1 contract Put · K={k:g} | {p['symbol']} | ${p['ask']:.2f} |\n\n"
            lower = f"${k-premium:.2f}" if premium <= k else "No lower break-even"
            title += f"Expiry **{chain['expiry']}**; Reference cost and maximum loss per unit **${premium*100:,.2f}** (standard 100-share multiplier, excluding fees); expiry break-even  **{lower} / ${k+premium:.2f}**. Realized moves must cover the premium; time decay and falling implied volatility hurt the position.\n\n"
            title += f"*Local strategy example · Yahoo option chain retrieved at  {chain.get('retrieved_at', '')[:16]} UTC; Ask  is an observed quote.*"
        else:
            title += "Structure: same expiry, near-the-money  Call + Put, one example unit each. Valid chain quotes are unavailable; identifiers, strikes, and costs remain to be confirmed.\n\n*Local strategy example · Realized moves must cover the premium; time decay and falling implied volatility hurt the position.*"
        return title
    return (
        "### Current research\n\n"
        + workspace.get("summary", "Continue researching the current underlying using quotes and actual contracts.")
        + "\n\n*AI has not generated a strategy. No strategy was generated this turn; current security data remains below.*"
    )
