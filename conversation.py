"""Typed conversation context, separate from long-lived investment suitability."""

import re

ALIASES = {
    "NVIDIA": "NVDA",
    "Nvidia": "NVDA",
    "Nvidia": "NVDA",
    "NVIDIA Corporation": "NVDA",
    "NVIDIA": "NVDA",
    "Apple": "AAPL",
    "APPLE": "AAPL",
    "Tesla": "TSLA",
    "TESLA": "TSLA",
    "Microsoft": "MSFT",
    "MICROSOFT": "MSFT",
    "Amazon": "AMZN",
    "Google": "GOOGL",
    "GOOGLE": "GOOGL",
    "META": "META",
    "Facebook": "META",
    "TSMC": "TSM",
    "Taiwan Semiconductor": "TSM",
    "Broadcom": "AVGO",
    "AMD": "AMD",
    "Advanced Micro Devices": "AMD",
    "Micron": "MU",
    "Intel": "INTC",
    "Oracle": "ORCL",
    "Netflix": "NFLX",
    "Netflix": "NFLX",
    "Tencent": "0700.HK",
    "Alibaba": "BABA",
    "Alibaba Group": "BABA",
    "Xiaomi": "1810.HK",
    "Meituan": "3690.HK",
    "Moutai": "600519.SS",
    "CATL": "300750.SZ",
    "BYD": "002594.SZ",
    "S&P500": "SPY",
    "S&P futures": "ES=F",
    "Nasdaq futures": "NQ=F",
    "gold futures": "GC=F",
    "crude oil futures": "CL=F",
    "Nasdaq": "QQQ",
    "Nasdaq index": "QQQ",
}
KINDS = {
    "security",
    "comparison",
    "options",
    "hedge",
    "allocation",
    "risk",
    "macro",
    "execution",
    "futures",
    "research",
}
SYMBOL = re.compile(r"[A-Z0-9^][A-Z0-9.^=\-]{0,14}$")
STOP = {
    "I",
    "A",
    "AI",
    "ETF",
    "API",
    "FRED",
    "USD",
    "CNY",
    "CAD",
    "RMB",
    "CEO",
    "PE",
    "PB",
    "EPS",
    "GDP",
    "CPI",
    "VIX",
    "VAR",
    "CVAR",
    "BS",
    "YOY",
    "TTM",
    "ROE",
}


def clean_hint(raw):
    if not isinstance(raw, dict):
        return {}
    out = {}
    if raw.get("kind") in KINDS:
        out["kind"] = raw["kind"]
    if isinstance(raw.get("symbols"), list):
        out["symbols"] = list(
            dict.fromkeys(
                s.upper()
                for s in raw["symbols"]
                if isinstance(s, str)
                and SYMBOL.fullmatch(s.upper())
                and s.upper() not in STOP
            )
        )[:4]
    for field, limit in [("title", 70), ("summary", 500)]:
        if isinstance(raw.get(field), str):
            out[field] = raw[field][:limit]
    # Research points are explicitly hypotheses/questions, never generated market facts.
    for field in ("questions", "drivers", "risks"):
        if isinstance(raw.get(field), list):
            out[field] = [v[:250] for v in raw[field] if isinstance(v, str)][:4]
    if isinstance(raw.get("modules"), list):
        out["modules"] = list(
            dict.fromkeys(
                v
                for v in raw["modules"]
                if v
                in (
                    "price",
                    "valuation",
                    "financials",
                    "news",
                    "company",
                    "options",
                    "questions",
                    "comparison",
                    "risk",
                    "macro",
                )
            )
        )[:6]
    return out


def resolve(text, previous=None, hint=None):
    previous = previous or {}
    hint = clean_hint(hint)
    upper = text.upper()
    symbols = []
    hits = []
    for name, symbol in ALIASES.items():
        pos = upper.find(name.upper())
        if pos >= 0:
            hits.append((pos, symbol))
    for known in set(ALIASES.values()):
        match = re.search(
            r"(?<![A-Za-z0-9])" + re.escape(known) + r"(?![A-Za-z0-9])", text, re.I
        )
        if match:
            hits.append((match.start(), known))
    for m in re.finditer(
        r"(?<![A-Za-z0-9])\$?([A-Z]{1,4}=F|\d{4,6}\.(?:HK|SS|SZ)|[A-Z]{1,5}(?:[.\-][A-Z]{1,3})?)(?![A-Za-z0-9])",
        text,
    ):
        if m[1] not in STOP:
            hits.append((m.start(), m[1]))
    if "Nasdaq futures" in text and "QQQ" not in upper:
        hits = [(pos, symbol) for pos, symbol in hits if symbol != "QQQ"]
    if "S&P futures" in text and "SPY" not in upper:
        hits = [(pos, symbol) for pos, symbol in hits if symbol != "SPY"]
    symbols = list(dict.fromkeys(s for _, s in sorted(hits)))[:4]
    explicit = bool(symbols)
    if (
        len(symbols) == 1
        and previous.get("symbols")
        and re.search(r"(?:compare.*with|with.*compare| and .*compare|which is better)", text)
    ):
        symbols = list(dict.fromkeys(previous["symbols"][:1] + symbols))[:4]
    if not symbols:
        symbols = hint.get("symbols") or previous.get("symbols", [])
    if (
        not explicit
        and not hint.get("symbols")
        and re.search("bullish on AI|AI industry|AI industry|thematic portfolio|entire portfolio|whole account", text, re.I)
    ):
        symbols = []
    derivative_text = re.sub(r"(?:do not want |do not need |do not consider |do not use |do not trade |do not buy )options", "", text)
    if (
        symbols
        and (re.search("futures", text) or any(s.endswith("=F") for s in symbols))
        and not re.search("options", derivative_text)
    ):
        kind = "futures"
    elif symbols and re.search(
        "options|protective put|collar|covered call|straddle|call spread|put spread", derivative_text
    ):
        kind = "options"
    elif re.search(
        "portfolio|purchase list|shopping list|what to buy|how to buy|help me buy|allocation recommendation|return to .*allocation|return to account|overall allocation|asset allocation|risk tolerance|risk level|capital allocation|long-term portfolio|build portfolio|build portfolio|around .*(?:portfolio|allocation)|add .*portfolio",
        text,
    ):
        kind = "allocation"
    elif symbols and re.search(
        "huge moves|large moves|sharp moves|large volatility|high volatility|huge volatility", text
    ):
        kind = "options"
    elif re.search(
        "options|protective put|call spread|put spread|collar|covered call|butterfly|iron condor|straddle|strike|expiry", text
    ):
        kind = "options"
    elif re.search("hedge|protection|drawdown protection", text):
        kind = "hedge"
    elif re.search(
        "VaR|CVaR|Return distribution|volatility|Risk analysis|Risk metrics|stress test|Maximum drawdown", text, re.I
    ):
        kind = "risk"
    elif re.search("enter position|staged entry|rebalance|execution plan", text):
        kind = "execution"
    elif len(symbols) > 1 and (explicit or re.search("compare|compare|which|these two", text)):
        kind = "comparison"
    elif re.search("FRED|macro|Federal Reserve|Federal Reserve|inflation|rate cuts|rate hikes|Treasury yield", text, re.I):
        kind = "macro"
    elif explicit:
        kind = "security"
    elif hint.get("kind"):
        kind = hint["kind"]
    elif symbols:
        kind = previous.get("kind", "security")
    else:
        kind = "research"
    if (
        len(symbols) > 1
        and kind in ("security", "risk", "research", "comparison")
        and (
            explicit
            or previous.get("kind") == "comparison"
            or re.search("compare|compare|these two|two securities|separately|which", text)
        )
    ):
        kind = "comparison"
    if kind == "comparison" and len(symbols) < 2:
        kind = "security" if symbols else "research"
    if kind == "security" and not symbols:
        kind = "research"
    titles = {
        "security": f"{symbols[0]} · Equity research" if symbols else "Equity research",
        "comparison": " / ".join(symbols) + " · Comparison research",
        "options": "Option structures and quotes",
        "hedge": "Protection plan and cost",
        "allocation": "Portfolio allocation",
        "risk": "Return distribution and risk",
        "macro": "Macro and rates",
        "execution": "Portfolio execution plan",
        "futures": "Futures strategy",
        "research": "Investment thesis research",
    }
    return dict(
        kind=kind,
        symbols=symbols,
        title=hint.get("title") or titles[kind],
        summary=hint.get("summary", ""),
        questions=hint.get("questions", []),
        drivers=hint.get("drivers", []),
        risks=hint.get("risks", []),
        query=text[:500],
        modules=hint.get("modules", []),
    )


def workspace_reply(context, profile, portfolio):
    if context.get("symbols") and context.get("kind") in (
        "security",
        "comparison",
        "options",
        "hedge",
        "risk",
    ):
        return (
            "Opened research for  "
            + " / ".join(context["symbols"])
            + "  for this turn. Prices, valuation, financials, and option chains are queried by underlying. Continue with valuation, recent results, risk, or a comparison."
        )
    from engine import reply

    return reply(profile, portfolio)
