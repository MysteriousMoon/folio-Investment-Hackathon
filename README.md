# Folio Studio

A Flask investment research and portfolio application. No account is required: anonymous browser sessions are saved to local SQLite storage so conversations, allocations, and reports survive a refresh.

## Quick start

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python app.py
```

The server listens on `127.0.0.1:5050` by default. Open http://127.0.0.1:5050 on this Mac. Set `HOST=0.0.0.0` explicitly if you need LAN access. On macOS, you can also double-click `Start-Folio.command`. The first launch generates a private session signing key. Preserve `instance/` to retain history and the signing key; clearing browser cookies loses access to the original anonymous session.

## Project layout

```text
folio-studio/
├── app.py                   # Flask routes, streaming, and persistence
├── engine.py                # Interview extraction and allocation
├── analytics.py             # Pricing, simulation, and portfolio risk
├── conversation.py          # Research context and subject resolution
├── providers.py             # Gemini and FRED adapters
├── market.py                # Yahoo market and financial data
├── localization.py          # Legacy profile enum compatibility
├── forecast.py              # Earnings and valuation scenarios
├── comparison.py            # Comparable security risk data
├── purchases.py             # Priced allocation shopping lists
├── strategy_card.py         # Strategy card parsing and fallback
├── trade_plan.py            # Trade validation and payoff calculation
├── templates/               # Active Flask HTML template
├── static/
│   ├── js/                  # Application JavaScript
│   ├── css/                 # Application stylesheets
│   └── vendor/              # Bundled third-party scripts and fonts
├── tests/                   # Backend and browser renderer checks
├── docs/
│   ├── USER_MANUAL.md       # User flows and calculation conventions
│   └── VALIDATION.md        # Historical validation record
├── archive/prototype/       # Original standalone frontend reference
├── Start-Folio.command      # macOS launcher
├── requirements.txt         # Runtime dependencies
├── requirements-dev.txt     # Development dependencies
└── requirements.lock.txt    # Pinned dependencies
```

Legacy risk, market, and currency identifiers are normalized to English when loaded; saved conversation text is preserved.

Backend modules remain at the root to preserve imports and the `app:app` deployment entry point. `archive/prototype/` is a reference implementation, not the active Flask frontend. Local `.venv/`, `instance/`, and caches are not source artifacts.

## Configuration

Edit `.env` and restart the service. The example contains no credentials. Add your own Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey). The default uses Google’s official native API at `https://generativelanguage.googleapis.com/v1beta`; no third-party endpoint is configured. Copy `.env.example` to `.env` and fill in your credentials locally before running. `.env` is ignored by Git; commit only the credential-free `.env.example`.

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | Server-side Gemini key; optional for local fallback. |
| `GEMINI_BASE_URL` | Full API base URL; defaults to `https://generativelanguage.googleapis.com/v1beta` when unset or blank. Custom URLs override it for both streaming and planning. |
| `GEMINI_API_FORMAT` | `google` (default) for native Gemini requests; `openai` for an OpenAI-compatible API. For a gateway, set its base URL (e.g. `https://gateway.example/v1`) and matching format. |
| `GEMINI_MODEL` | Defaults to `gemini-2.5-flash`; choose a model available to your account. |
| `FRED_API_KEY` | Optional FRED key. |
| `SECRET_KEY` | Stable random deployment key; otherwise `instance/secret.key` is used. |
| `FOLIO_DATA_DIR` | Database and signing-key directory; defaults to `instance/`. |
| `COOKIE_SECURE` | Set to `1` for HTTPS deployment, `0` for local HTTP. |

Without Gemini, interviews, allocations, reports, saving, and Yahoo data use the local allocation engine. With Gemini, structured JSON first extracts and validates the profile and risk budget, then SSE streams explanations and follow-up questions. Model failures fall back locally without losing the conversation. Streaming is genuine model output, not a simulated typing animation.

## Features and data

- Blue-and-white dashboard, animated strategy examples, and mobile chat/analysis switching.
- Structured recommendations can be added to a persistent Saved investments page, with a compact investment list on the left and the four analysis panels on the right.
- Multi-turn interviews covering risk, theme, budget, currency, horizon, market, holdings, and liquidity needs.
- Synchronized weights, amounts, and charts; model allocations must satisfy total-weight, risk-budget, and short-horizon constraints.
- Yahoo Finance/yfinance prices, available daily history, dates, currency, daily changes, five-minute caching, refresh, and explicit failures.
- FRED observations for DGS10, DGS2, FEDFUNDS, CPIAUCSL, and UNRATE, with dates and source links.
- Reports covering asset details, allocation rationale, risk management, stress scenarios, rebalancing, and methodology.
- SQLite autosave, manual save, print/PDF, JSON export, and new conversations.
- Cookie session isolation, CSRF checks, input limits, escaped rendering, per-session generation locking, and server-side secrets.

## Deployment

```sh
.venv/bin/waitress-serve --listen=127.0.0.1:5050 --threads=8 app:app
```

Use one Waitress process behind an HTTPS reverse proxy. Disable buffering on SSE routes and allow read timeouts above 180 seconds. Mount persistent storage for the instance directory. Anonymous sessions have no account authentication; public deployments need gateway rate limits and request quotas to control model usage.

```nginx
location / {
    proxy_pass http://127.0.0.1:5050;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
    proxy_read_timeout 180s;
}
```

## Verification

```sh
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

Tests cover interviews, weights and amounts, stress arithmetic, session isolation, CSRF, concurrency, streamed responses, and fallback. External services use test doubles; live Gemini/FRED checks require configured keys. See the [validation record](docs/VALIDATION.md).

## Derivatives and quantitative risk

`analytics.py` supports up to three concurrent strategies: protective puts, call spreads, put spreads, covered calls, collars, long straddles, call butterflies, iron condors, short index-futures hedges, and long index futures. Premium budgets and hedge ratios can be adjusted through the conversation or portfolio controls.

- Historical calibration uses three years of Yahoo adjusted daily closes, aligned on common dates, with at least 126 samples and a one-hour cache. Missing history switches explicitly to parameter scenarios.
- Returns use 20,000 correlated geometric Brownian motion scenarios with a fixed seed and 1/3/6/12-month horizons. Annual log drift defaults to zero or can use the historical mean. Outputs include percentiles, loss probability, skewness, and excess kurtosis.
- Risk includes delta-based annual volatility, broad-market beta, 95% VaR/CVaR, a spot-only baseline, net equity delta, Greeks, notional exposure, premiums, and margin.
- Options use a normalized underlying price of 100 and European zero-dividend Black–Scholes pricing. Cash limits determine size; covered calls cannot exceed available theme exposure, and iron condors reserve collateral for spread width. Actual Yahoo option chains are queried separately from model prices.
- Futures use broad-market returns as a proxy, linear exposure, and a 10% margin scenario reserved from cash. The default hedge covers 50% of theme and broad-market exposure. Margin is not maximum loss.
- Payoff curves compare spot-only and derivative portfolios under synchronized equity moves.

Endpoints include `GET /api/analytics?months=3&drift=zero&calibration=historical` and `GET /api/options?symbol=SMH&expiry=YYYY-MM-DD`. Option chains show real contract identifiers, strikes, bid/ask, IV, and open interest. Risk outputs are saved and exported with parameters and versions.

## Markdown and TeX

Live replies, saved messages, and report discussions support GFM Markdown and KaTeX with `$…$`, `$$…$$`, `\(…\)`, and `\[…\]`. Math is handled during Markdown tokenization so underscores and backslashes remain intact. Code and common dollar amounts remain literal. Streaming updates are batched by animation frame; incomplete formulas remain text until the final render.

Marked, DOMPurify, KaTeX, and fonts are bundled under `static/vendor/`; `manifest.json` records pinned versions and npm integrity hashes. HTML is sanitized before math rendering, KaTeX trust is disabled, and external chat images are blocked.

Run `.venv/bin/python tests/build_richtext_checks.py`, then open `/static/.richtext-check.html` for the 12 browser checks. Delete the generated page after verification; keep the test sources.

## Research and workspace behavior

The retained account workspace has portfolio, risk, and strategy tabs, expandable positions, a derivatives overlay, an execution-plan entry point, shared-bin return distributions, Greeks, correlations, and real option chains. Market background data loads on expansion. Tabs support arrow keys and Home/End. Profile edits highlight changed positions and summarize weight, amount, or strategy changes. The `baseline` and histogram `base_probability` fields compare identical simulated paths.

The current interface follows the conversation's subject. `conversation.py` records the task, symbols, and relevant modules; server-side validation checks Gemini's structured intent. Company aliases and follow-up references are resolved locally. New companies replace previous subjects; comparisons retain the relevant prior subject.

- Single securities show Yahoo prices, history, valuation, quarterly financials, company details, and security-specific risk.
- Comparisons align common trading dates and normalize price history to 100.
- Options use the current security's actual chain and expiry dates, with selectable contracts.
- Macro discussions use FRED observations. Explicit allocation requests retain separate account analysis.

`GET /api/research?symbols=NVDA,AAPL` accepts up to four symbols. Price/financial data has a five-minute cache and concurrent requests for the same symbol are combined. Missing news and metrics are never invented. Dividend yields, growth rates, and financial currencies retain explicit units. Research data is shared with Gemini and the right-side display.

Security research does not change saved account amounts, risk levels, or allocations. Research context persists across refreshes. The current strategy interface presents recommendations, prices, return curves, and risk; see the [user manual](docs/USER_MANUAL.md) for current behavior.

API references: [Gemini Generate Content](https://ai.google.dev/api/generate-content), [FRED observations](https://fred.stlouisfed.org/docs/api/fred/series_observations.html).
