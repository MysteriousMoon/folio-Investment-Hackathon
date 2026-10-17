import json
import os
import requests

OFFICIAL_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def native_endpoint(model, action):
    base = (
        os.getenv("GEMINI_BASE_URL", "").strip() or OFFICIAL_GEMINI_BASE_URL
    ).rstrip("/")
    return f"{base}/models/{model}:{action}"


def compatible_endpoint():
    base = (
        os.getenv("GEMINI_BASE_URL", "").strip() or OFFICIAL_GEMINI_BASE_URL
    ).rstrip("/")
    if base == OFFICIAL_GEMINI_BASE_URL:
        base += "/openai"
    elif not base.endswith(("/v1", "/openai")):
        base += "/v1"
    return base + "/chat/completions"


def compatible_stream(messages, system):
    with requests.post(
        compatible_endpoint(),
        headers={"Authorization": "Bearer " + os.environ["GEMINI_API_KEY"]},
        json={
            "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            "messages": [{"role": "system", "content": system}]
            + [{"role": m["role"], "content": m["text"]} for m in messages[-30:]],
            "stream": True,
        },
        stream=True,
        timeout=(10, 90),
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line or not line.startswith(b"data:"):
                continue
            body = line[5:].strip()
            if body == b"[DONE]":
                return
            payload = json.loads(body)
            if payload.get("error"):
                raise ValueError("Model stream returned an error")
            for choice in payload.get("choices", []):
                content = choice.get("delta", {}).get("content")
                if isinstance(content, str) and content:
                    yield content


def gemini_stream(messages, portfolio):
    key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    system = """You are Folio's English-language investment research assistant. Ask follow-up interview questions, prioritizing one question at a time. Never promise returns or invent market data, sources, news, or partnerships. Recommend strategies based on the current security and user view; the old account allocation does not constrain this turn. Treasury/equity correlations depend on market conditions. Do not output HTML. Quote risk/return figures only from calculated risk_summary metrics and state their horizon; model distributions are not real-world probabilities. Beta measures market sensitivity, not total volatility. Historical security_risk volatility describes its sample period; three months refers only to the simulation horizon. Refer to financial reports by period-end date, without inferring fiscal-quarter numbering. Follow metric_units; price targets are not promised returns. Stocks, options, and futures may be combined, accounting for overlapping exposure. Use supplied security_data prices, dates, and financial metrics; distinguish verified data from inference. Follow workspace.kind instead of forcing every stock question into five asset buckets. Markdown and TeX are allowed.
You produce both the left conversation and the right strategy card. Output the conversation first, then the exact separator <!--FOLIO_CARD--> exactly once, followed by card-only Markdown. The card describes the current view rather than a complete account shopping list. Use a short title, brief rationale, and at most four trade-leg rows. Initially describe costs, maximum loss, and break-even only when supported by supplied data. A view expecting large moves without direction may suggest a long straddle or strangle; do not interpret all volatility views as bullish. When option_chain supplies real contracts, show side, identifier, expiry, Call/Put, strike, and Bid/Ask. Each leg defaults to one example strategy unit, not an actual order. Standard US option contracts cover 100 shares; use ask for buys and bid for sells. Do not calculate costs from missing or invalid quotes. Bounded-risk strategies need correct maximum loss and expiry break-even; do not invent missing values. Observed quotes do not guarantee execution. Without actual chains, describe the structure and parameters still to be selected, without fabricated identifiers. Pure valuation/financial questions need a brief research conclusion and next step, not a forced purchase. Do not repeat extensive stock data or include HTML, scripts, code fences, or full-account allocations.
The right side consistently contains recommendation, market data, return curve, and risk; do not generate a five-bucket account allocation. State what to buy and the suggested percentage of capital: stock value, option premium, or futures notional exposure rather than margin. Percentages are recommendations, not executed trades. Without a budget, explicitly label quantities as one illustrative strategy unit; one contract is not suitable for every budget. Mixed stock/option strategies are allowed; covered calls require 100 shares per option. The final card should contain only a short title, allocation/action, and brief reason, at most about 100 English words. Leave costs, maximum loss, and break-even to the program's curve/risk modules. Omit version numbers, implementation notes, and research-background fine print.
Append the exact marker <!--FOLIO_PLAN--> followed by a plain JSON object: {"legs":[{"instrument":"stock|call|put|future","symbol":"underlying Yahoo symbol","contract":"actual option-chain contract identifier; omit for non-options","side":"buy|sell","quantity":100,"allocation_pct":10}]}. This is internal calculation data, not user-facing prose. Legs must match the card with correct quantity ratios. Stock-plus-option strategies must return both stock and call/put legs in the same legs array, not only the newly added leg. previous_strategy is the prior structure; return the complete updated structure on adjustment. symbol must be the underlying Yahoo symbol, never an option contract identifier. Use only matching contracts from option_chains. Stock quantity is shares; options/futures quantity is contracts. allocation_pct is a suggested capital percentage, or futures notional percentage. Use an empty legs array for pure research without a recommendation; stock recommendations can use 100 shares as an example. Do not fill in prices, multipliers, Greeks, or curves; the program uses real quotes. Futures must have supplied quotes/specifications; continuous contracts are illustrative and must not be presented as directly tradable dated contracts. forecast contains program-calculated earnings and valuation scenarios: explain assumptions without treating them as real-world probabilities or verified targets. Stock forecast-return curves differ from derivative expiry payoffs. Current context: """ + json.dumps(
        portfolio, ensure_ascii=False
    )
    if os.getenv("GEMINI_API_FORMAT") == "openai":
        yield from compatible_stream(messages, system)
        return
    contents = [
        {
            "role": "user" if m["role"] == "user" else "model",
            "parts": [{"text": m["text"]}],
        }
        for m in messages[-30:]
    ]
    with requests.post(
        native_endpoint(model, "streamGenerateContent"),
        params={"alt": "sse"},
        headers={"x-goog-api-key": key},
        json={"systemInstruction": {"parts": [{"text": system}]}, "contents": contents},
        stream=True,
        timeout=(10, 90),
    ) as res:
        res.raise_for_status()
        for line in res.iter_lines():
            if line and line.startswith(b"data:"):
                data = json.loads(line[5:])
                for c in data.get("candidates", []):
                    for part in c.get("content", {}).get("parts", []):
                        if part.get("text") and not part.get("thought"):
                            yield part["text"]


SERIES = {
    "DGS10": "US 10-year Treasury yield (%)",
    "DGS2": "US 2-year Treasury yield (%)",
    "FEDFUNDS": "Effective federal funds rate (%)",
    "CPIAUCSL": "US  CPI  index (not inflation rate)",
    "UNRATE": "US unemployment rate (%)",
}


def fred_data():
    if not os.getenv("FRED_API_KEY"):
        return {"configured": False, "series": []}
    results = []
    for code, label in SERIES.items():
        try:
            r = requests.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "api_key": os.environ["FRED_API_KEY"],
                    "series_id": code,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 10,
                },
                timeout=8,
            )
            r.raise_for_status()
            point = next(
                (x for x in r.json().get("observations", []) if x["value"] != "."), None
            )
            results.append(
                dict(
                    id=code,
                    label=label,
                    observation=point,
                    source=f"https://fred.stlouisfed.org/series/{code}",
                )
            )
        except (requests.RequestException, ValueError):
            results.append(dict(id=code, label=label, error="Temporarily unavailable"))
    return {"configured": True, "series": results}


def gemini_plan(messages, profile):
    """Plan structured profile changes; validate independently before using any output."""
    prompt = """Update the investment interview profile from the latest user message. Extract only explicitly stated personal investment circumstances; never guess budget, currency, risk, market, or holdings. Stock prices, market capitalization, and financial-report figures are not the user's investment budget. Pure security research or contract lookups must not change account allocations. Retain existing information unless corrected. Allowed profile fields: risk (conservative/balanced/aggressive), horizon (years, numeric), amount (numeric), currency (CNY/USD/CAD), market (US stocks/A shares/Hong Kong stocks), holdings (holdings and liquidity needs), theme (up to 30 characters), hedge (boolean), options (boolean), strategies (up to 3 codes: protective_put/call_spread/put_spread/covered_call/collar/straddle/butterfly/iron_condor/futures_hedge/futures_long), premium_budget (premium percentage of total capital, 0 to 5), hedge_ratio (protected exposure percentage, 0 to 100). Return JSON: {"profile":{...},"weights":[theme,broad equities,short/intermediate Treasuries,gold,cash]}. weights must be five nonnegative integers totaling 100. Conservative theme/equity caps are 15/35, balanced 25/60, aggressive 35/80. For horizons below two years, total equity must not exceed 20 and cash must be at least 50. Adjust to user constraints; use balanced defaults when key information is missing. Do not claim return optimality.
Also return workspace: kind is security/comparison/options/hedge/allocation/risk/macro/execution/research/futures; symbols are up to four Yahoo identifiers for the currently discussed securities (e.g. NVIDIA NVDA, Tencent 0700.HK); title is an English analysis title; modules are up to six relevant entries ordered by relevance from price/valuation/financials/news/company/options/questions/comparison/risk/macro; summary describes the research goal without unverified market facts; questions contains up to three key research questions; drivers/risks contain up to three hypotheses to verify. Select content from the latest question: use futures for futures, options for mixed stock/options while retaining all underlying symbols, security for individual companies, and comparison for company comparisons. Do not force company research into five-bucket allocations. Pronouns retain prior subjects; explicit company changes replace them. Treat claims requiring market/financial verification as research questions, not established facts. Use English for all user-facing text."""
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    if os.getenv("GEMINI_API_FORMAT") == "openai":
        r = requests.post(
            compatible_endpoint(),
            headers={"Authorization": "Bearer " + os.environ["GEMINI_API_KEY"]},
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": prompt
                        + "Return only a JSON object only, without code fences.",
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "existing_profile": profile,
                                "conversation": messages[-20:],
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                "stream": False,
                "response_format": {"type": "json_object"},
            },
            timeout=(10, 60),
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(content)
    else:
        r = requests.post(
            native_endpoint(model, "generateContent"),
            headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
            json={
                "systemInstruction": {"parts": [{"text": prompt}]},
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "existing_profile": profile,
                                        "conversation": messages[-20:],
                                    },
                                    ensure_ascii=False,
                                )
                            }
                        ],
                    }
                ],
                "generationConfig": {"responseMimeType": "application/json"},
            },
            timeout=(10, 35),
        )
        r.raise_for_status()
        payload = r.json()
        parts = payload["candidates"][0]["content"]["parts"]
        result = json.loads(
            "".join(p.get("text", "") for p in parts if not p.get("thought"))
        )
    raw = result.get("profile", {})
    clean = dict(profile)
    enums = {
        "risk": ["conservative", "balanced", "aggressive"],
        "currency": ["CNY", "USD", "CAD"],
        "market": ["US stocks", "A shares", "Hong Kong stocks"],
    }
    for k, allowed in enums.items():
        if raw.get(k) in allowed:
            clean[k] = raw[k]
    for k, upper in [("amount", 1e10), ("horizon", 100)]:
        v = raw.get(k)
        if type(v) in (int, float) and 0 < v <= upper:
            clean[k] = v
    for k, limit in [("theme", 30), ("holdings", 600)]:
        if isinstance(raw.get(k), str) and raw[k].strip():
            clean[k] = raw[k][:limit]
    for k in ["hedge", "options"]:
        if type(raw.get(k)) is bool:
            clean[k] = raw[k]
    from analytics import STRATEGIES

    if isinstance(raw.get("strategies"), list):
        clean["strategies"] = list(
            dict.fromkeys(
                k for k in raw["strategies"] if isinstance(k, str) and k in STRATEGIES
            )
        )[:3]
    for k, upper in [("premium_budget", 5), ("hedge_ratio", 100)]:
        if type(raw.get(k)) in (int, float) and 0 <= raw[k] <= upper:
            clean[k] = raw[k]
    weights = result.get("weights")
    valid = (
        isinstance(weights, list)
        and len(weights) == 5
        and all(type(v) is int and 0 <= v <= 100 for v in weights)
        and sum(weights) == 100
    )
    if valid:
        cap, equity = {
            "conservative": (15, 35),
            "balanced": (25, 60),
            "aggressive": (35, 80),
        }[clean.get("risk", "balanced")]
        valid = weights[0] <= cap and sum(weights[:2]) <= equity
        if clean.get("horizon", 5) < 2:
            valid = valid and sum(weights[:2]) <= 20 and weights[4] >= 50
    from conversation import clean_hint

    from purchases import validate_targets

    targets = validate_targets(result.get("purchase_targets"))
    if targets:
        clean["purchase_targets"] = targets
    clean["_workspace_request"] = clean_hint(result.get("workspace"))
    return clean, weights if valid else None
