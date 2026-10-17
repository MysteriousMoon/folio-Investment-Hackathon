"""Yahoo Finance adapter, bounded symbol input and short-lived process cache."""

import re
import os
from pathlib import Path
import threading
import time
from datetime import datetime, timezone

_cache = {}
_guard = threading.Lock()


def quotes(raw):
    symbols = list(dict.fromkeys(raw.upper().split(",")))
    if not 1 <= len(symbols) <= 8 or any(
        not re.fullmatch(r"[A-Z0-9^][A-Z0-9.^=-]{0,14}", s) for s in symbols
    ):
        return {
            "source": "Yahoo Finance",
            "quotes": [],
            "error": "Enter up to  8  valid symbols",
        }
    key = ",".join(symbols)
    with _guard:
        cached = _cache.get(key)
        if cached and time.time() - cached[0] < 300:
            return cached[1]
    results = []
    try:
        import yfinance as yf

        yf.set_tz_cache_location(
            str(
                Path(
                    os.getenv("FOLIO_DATA_DIR", str(Path(__file__).parent / "instance"))
                )
                / "yahoo-cache"
            )
        )
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                history = ticker.history(period="5d", auto_adjust=False, timeout=8)
                if history.empty:
                    raise ValueError("no observations")
                close = history["Close"].dropna()
                if close.empty:
                    raise ValueError("no close")
                metadata = ticker.history_metadata or {}
                latest = float(close.iloc[-1])
                previous = float(close.iloc[-2]) if len(close) > 1 else None
                results.append(
                    dict(
                        symbol=symbol,
                        price=round(latest, 4),
                        change=(
                            round((latest / previous - 1) * 100, 2)
                            if previous
                            else None
                        ),
                        currency=metadata.get("currency", "Unknown"),
                        date=close.index[-1].isoformat(),
                        source=f"https://finance.yahoo.com/quote/{symbol}/",
                        kind="Latest trading-day close / Incomplete current-day bar",
                    )
                )
            except Exception:
                results.append(dict(symbol=symbol, error="Unable to fetch; refresh later"))
    except ImportError:
        return {
            "source": "Yahoo Finance",
            "quotes": [],
            "error": "Please install  requirements.txt  in  yfinance",
        }
    data = {
        "source": "Yahoo Finance",
        "quotes": results,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "cached_seconds": 300,
    }
    with _guard:
        _cache[key] = (time.time(), data)
    return data


def option_chain(symbol, expiry=None, contract_symbol=None):
    import math

    if not re.fullmatch(r"[A-Z0-9][A-Z0-9.=-]{0,14}", symbol):
        return {"error": "Invalid security symbol", "contracts": []}
    cache_key = "options:" + symbol + ":" + str(expiry) + ":" + str(contract_symbol)
    with _guard:
        cached = _cache.get(cache_key)
        if cached and time.time() - cached[0] < 300:
            return cached[1]
    try:
        import yfinance as yf

        yf.set_tz_cache_location(
            str(
                Path(
                    os.getenv("FOLIO_DATA_DIR", str(Path(__file__).parent / "instance"))
                )
                / "yahoo-cache"
            )
        )
        ticker = yf.Ticker(symbol)
        expiries = list(ticker.options)
        if not expiries:
            return {
                "symbol": symbol,
                "expiries": [],
                "contracts": [],
                "error": "No option chain is available for this security",
            }
        selected = expiry or expiries[min(2, len(expiries) - 1)]
        if selected not in expiries:
            return {"error": "Expiry unavailable", "expiries": expiries, "contracts": []}
        chain = ticker.option_chain(selected)
        history = ticker.history(period="5d", timeout=8)
        spot = float(history["Close"].dropna().iloc[-1]) if not history.empty else None
        contracts = []

        def finite(value):
            try:
                return round(float(value), 5) if math.isfinite(float(value)) else None
            except (ValueError, TypeError):
                return None

        for kind, frame in [("call", chain.calls), ("put", chain.puts)]:
            if contract_symbol:
                frame = frame.loc[frame["contractSymbol"] == contract_symbol]
            elif spot is not None:
                frame = frame.iloc[
                    (frame["strike"] - spot).abs().argsort()[:8]
                ].sort_values("strike")
            else:
                frame = frame.head(8)
            for _, row in frame.iterrows():
                contracts.append(
                    dict(
                        multiplier=(
                            100 if row.get("contractSize") == "REGULAR" else None
                        ),
                        type=kind,
                        symbol=row.get("contractSymbol"),
                        strike=finite(row.get("strike")),
                        bid=finite(row.get("bid")),
                        ask=finite(row.get("ask")),
                        last=finite(row.get("lastPrice")),
                        iv=finite(row.get("impliedVolatility")),
                        volume=finite(row.get("volume")),
                        open_interest=finite(row.get("openInterest")),
                        last_trade=str(row.get("lastTradeDate")),
                    )
                )
        result = dict(
            symbol=symbol,
            spot=spot,
            expiry=selected,
            expiries=expiries,
            contracts=contracts,
            source="Yahoo Finance",
            retrieved_at=datetime.now(timezone.utc).isoformat(),
        )
        with _guard:
            _cache[cache_key] = (time.time(), result)
        return result
    except Exception:
        return {
            "symbol": symbol,
            "contracts": [],
            "error": "Option chain unavailable; retry later",
        }


def _load_security_research(symbol):
    """Same ticker throughout quote, history, financials and news; no surrogate assets."""
    import math
    from concurrent.futures import ThreadPoolExecutor
    from conversation import SYMBOL

    symbol = symbol.upper()
    if not SYMBOL.fullmatch(symbol):
        return {"symbol": symbol, "error": "Invalid security symbol"}
    key = "research:" + symbol
    with _guard:
        cached = _cache.get(key)
        if cached and time.time() - cached[0] < 300:
            return cached[1]
    import yfinance as yf

    yf.set_tz_cache_location(
        str(
            Path(os.getenv("FOLIO_DATA_DIR", str(Path(__file__).parent / "instance")))
            / "yahoo-cache"
        )
    )
    ticker = yf.Ticker(symbol)

    def safe(fn, default):
        try:
            return fn()
        except Exception:
            return default

    def number(v):
        try:
            return float(v) if v is not None and math.isfinite(float(v)) else None
        except (ValueError, TypeError):
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {
            "info": pool.submit(safe, lambda: ticker.get_info(), {}),
            "history": pool.submit(
                safe,
                lambda: ticker.history(period="1y", auto_adjust=False, timeout=10),
                None,
            ),
            "financials": pool.submit(safe, lambda: ticker.quarterly_income_stmt, None),
            "news": pool.submit(safe, lambda: ticker.get_news(count=5), []),
        }
        data = {k: f.result() for k, f in jobs.items()}
    info = data["info"] or {}
    history = data["history"]
    points = []
    if history is not None and not history.empty:
        for date, row in history.iterrows():
            close = number(row.get("Close"))
            if close is not None:
                points.append(
                    dict(
                        date=date.date().isoformat(),
                        close=round(close, 4),
                        volume=number(row.get("Volume")),
                    )
                )
    price = number(info.get("regularMarketPrice")) or (
        points[-1]["close"] if points else None
    )
    if price is None:
        return {
            "symbol": symbol,
            "error": "Yahoo  returned no quotes for this security; check the symbol or retry later",
            "history": [],
        }
    prev = number(info.get("regularMarketPreviousClose")) or (
        points[-2]["close"] if len(points) > 1 else None
    )
    quote_time = number(info.get("regularMarketTime"))
    quote_date = (
        datetime.fromtimestamp(quote_time, timezone.utc).isoformat()
        if quote_time
        else (points[-1]["date"] if points else None)
    )
    financials = []
    frame = data["financials"]
    if frame is not None and not frame.empty:
        for col in list(frame.columns)[:20]:

            def row_value(label):
                return number(frame.at[label, col]) if label in frame.index else None

            financials.append(
                dict(
                    period=col.date().isoformat(),
                    revenue=row_value("Total Revenue"),
                    net_income=row_value("Net Income"),
                    operating_income=row_value("Operating Income"),
                )
            )
        financials.reverse()
    news = []
    for item in data["news"] or []:
        c = item.get("content", item) or {}
        url = (c.get("canonicalUrl") or {}).get("url") or c.get("link")
        if isinstance(url, str) and url.startswith("https://"):
            news.append(
                dict(
                    title=c.get("title", ""),
                    url=url,
                    publisher=(c.get("provider") or {}).get("displayName"),
                    date=c.get("pubDate"),
                )
            )
    fields = [
        "marketCap",
        "trailingPE",
        "forwardPE",
        "priceToBook",
        "beta",
        "totalRevenue",
        "revenueGrowth",
        "earningsGrowth",
        "profitMargins",
        "operatingMargins",
        "freeCashflow",
        "totalCash",
        "totalDebt",
        "returnOnEquity",
        "fiftyTwoWeekLow",
        "fiftyTwoWeekHigh",
        "dividendYield",
        "trailingEps",
        "targetMeanPrice",
    ]
    performance = {}
    if points:
        for label, days in [("1m", 21), ("3m", 63), ("1y", 252)]:
            if len(points) > min(days, 21):
                performance[label] = round(
                    (price / points[max(0, len(points) - days - 1)]["close"] - 1) * 100,
                    3,
                )
    security_risk = None
    if len(points) > 30:
        import numpy as np

        closes = np.array([p["close"] for p in points])
        returns = np.diff(np.log(closes))
        vol = float(returns.std(ddof=1) * np.sqrt(252))
        simulated = np.expm1(
            np.random.default_rng(20261017).normal(0, vol * np.sqrt(0.25), 20000)
        )
        threshold = float(np.quantile(simulated, 0.05))
        counts, edges = np.histogram(simulated * 100, bins=30)
        security_risk = dict(
            annual_vol=round(vol * 100, 3),
            historical_max_drawdown=round(
                float(np.min(closes / np.maximum.accumulate(closes) - 1)) * 100, 3
            ),
            var95=round(max(0, -threshold) * 100, 3),
            cvar95=round(
                max(0, -float(simulated[simulated <= threshold].mean())) * 100, 3
            ),
            p05=round(threshold * 100, 3),
            median=round(float(np.median(simulated)) * 100, 3),
            p95=round(float(np.quantile(simulated, 0.95)) * 100, 3),
            months=3,
            samples=len(returns),
            histogram=[
                dict(
                    low=float(edges[i]),
                    high=float(edges[i + 1]),
                    probability=float(v) / 200,
                )
                for i, v in enumerate(counts)
            ],
            method="Single-security daily return calibration; 3 months, 20000 scenarios, log drift 0, excluding dividends, with a fixed seed.",
        )
    result = dict(
        security_risk=security_risk,
        symbol=symbol,
        name=info.get("longName") or info.get("shortName") or symbol,
        quote_type=info.get("quoteType"),
        exchange=info.get("fullExchangeName") or info.get("exchange"),
        currency=info.get("currency") or "Unknown",
        financial_currency=info.get("financialCurrency")
        or info.get("currency")
        or "Unknown",
        price=price,
        change_pct=round((price / prev - 1) * 100, 3) if prev else None,
        as_of=quote_date,
        history=points,
        financials=financials,
        metrics={k: number(info.get(k)) for k in fields},
        company=dict(
            sector=info.get("sector"),
            industry=info.get("industry"),
            country=info.get("country"),
            description=info.get("longBusinessSummary"),
            website=info.get("website"),
        ),
        news=news,
        performance=performance,
        source=f"https://finance.yahoo.com/quote/{symbol}/",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )
    # Yahoo dividendYield is percentage points; other growth/margin fields are fractions.
    annual_dividend = number(info.get("dividendRate"))
    raw_yield = number(info.get("dividendYield"))
    result["metrics"]["dividendYield"] = (
        annual_dividend / price
        if annual_dividend is not None
        else raw_yield / 100 if raw_yield is not None else None
    )
    result["metric_units"] = {
        "dividendYield": "fraction; forward annual dividend / price, or Yahoo percentage points / 100",
        "revenueGrowth": "fraction",
        "profitMargins": "fraction",
        "returnOnEquity": "fraction",
    }
    from forecast import forecast

    result["forecast"] = forecast(result)
    with _guard:
        _cache[key] = (time.time(), result)
    return result


_research_locks = {}


def security_research(symbol):
    with _guard:
        lock = _research_locks.setdefault(symbol.upper(), threading.Lock())
    with lock:
        return _load_security_research(symbol)
