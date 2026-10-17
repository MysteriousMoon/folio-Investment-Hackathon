# Folio V1 Validation Record

This document preserves historical validation results from the original implementation. Counts below describe the corresponding development stages; they are not claims that all live integrations were rechecked during later documentation maintenance.

## Initial application

- 32 backend tests passed, covering interviews, persistence, session isolation, CSRF, concurrency, Gemini chunks/fallback, risk-budget validation, European put-call parity, numerical delta, ten derivatives strategies, bounded option payoffs, capital requirements, hedge comparisons, percentiles/probabilities, reproducibility, and cash financing costs.
- All Python modules compiled; frontend app.js and risk.js passed syntax checks.
- Desktop checks entered risk and amounts, changed risk, added collars and futures hedges, and verified synchronized weights, amounts, reports, risk metrics, and market data.
- At 390 × 844, mobile chat/portfolio switching, metric grids, distributions, and payoff curves were usable.
- Yahoo returned stock/ETF and ES=F daily history, three-year common-date calibration, and SMH expiries with 16 near-the-money contracts.
- Locally configured Gemini structured planning and SSE worked, and all five FRED series returned dated observations. Automated tests isolate real keys and external requests.
- Flask + Waitress ran on port 5050 without a frontend build.

See [USER_MANUAL.md](USER_MANUAL.md) for assumptions and operation. Model return distributions remain separate from actual option-chain quotes.

## Markdown and TeX

All 12 browser assertions passed: GFM, four math delimiters, matrices, code blocks, dollar amounts, character-by-character streaming, invalid/incomplete TeX, HTML sanitization, disabled TeX trust, external-link attributes, table formulas, and macro isolation. After reload, eight historical messages rendered as rich text with 23 paragraphs, and local KaTeX scripts/fonts loaded. The original 32 backend tests still passed.

## Workspace redesign

34 backend tests passed, adding shared distribution bins, probability totals, and baseline equality without derivatives. Desktop checks covered tabs, positions, keyboard navigation, risk metrics, and strategy comparisons. Changing the horizon preserved the current tab and advanced-setting expansion. At 390 × 844 there was no horizontal overflow. Markdown/TeX and reports remained available; market data moved to lazy loading.

## Conversation-driven security research

48 backend tests passed, covering subject replacement, pronouns, comparisons, module validation, correct symbol queries, account preservation, financial units, and security-specific risk. Live Yahoo checks returned roughly one year of history, four financial quarters, prices, and valuation for NVDA/AAPL. A Gemini/browser flow moved from NVDA valuation and financials to NVDA/AAPL comparison and AAPL quarterly results, updating symbols, tables, charts, and ordering from shared security data. Account risk remained separate from individual-security risk.

## Unified strategy interface

69 tests passed, including straddles, protective puts, covered calls, call spreads, and futures multipliers. Strategy JSON was separated from Markdown and contract matches, quote sides, quantities, and multipliers were validated independently. Missing hedge legs prevented partial curves; different symbols/expiries were kept separate. A browser check of 100 NVDA shares plus one put confirmed calculated maximum loss, break-even, and scenarios without mobile overflow. Separate live sessions for AAPL stock and NQ=F futures returned recommendations and calculated curves.

Futures multiplier references: [CME Micro E-mini options](https://www.cmegroup.com/education/articles-and-reports/trading-micro-e-mini-options), [Micro WTI fact card](https://www.cmegroup.com/trading/energy/files/micro-wti-crude-oil-futures-fact-card.pdf), [Gold futures and options fact card](https://www.cmegroup.com/trading/metals/files/fact-card-gold-futures-options.pdf).

## Earnings forecasts and four-panel layout

73 tests passed, adding earnings arithmetic, path endpoints, growth shrinkage/caps, quarterly year-over-year growth, losses, and missing currency data. Desktop checks confirmed two columns and a complete valuation table without overflow. Stocks showed three twelve-month scenarios; mixed options showed actual contract expiry payoffs.

## Recommendation updates and mixed strategies

75 tests passed, covering stock-plus-put structures, synchronized cross-security scenarios, and rejection of missing protection legs. Additional contracts were fetched using actual identifiers/expiries; existing expiries were retained. The frontend kept old recommendations until new Markdown streamed, and forecast assumptions were expanded. The NVDA backend curve contained 122 price points; browser checks confirmed the strategy SVG was visible and the stock forecast hidden. Forecast assumptions became ordinary content, and mtime resource versions prevented stale scripts.

## Complete comparison

78 tests passed, adding common-date alignment, shared risk bins, missing-sample handling, and comparison-mode persistence on risk follow-ups. All securities fed the four panels, with percentage return curves, a shared twelve-month horizon, and synchronized scenario switching.
