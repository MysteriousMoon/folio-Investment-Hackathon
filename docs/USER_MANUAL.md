# Folio User Guide

Enter a stock, option, or futures symbol and your investment view. The right side shows:

1. **Recommendation:** direction, suggested allocation, and strategy legs. Stock allocation is a percentage of capital; options use premium as a percentage of capital; futures use notional exposure.
2. **Market data:** current prices and historical charts, with financials and valuation when relevant.
3. **Return curve:** calculated from actual quotes and trade legs for stocks, options, futures, and mixed strategies. Move the pointer or use arrow keys to inspect profit and loss.
4. **Risk:** maximum strategy loss/gain, break-even levels, price scenarios, historical volatility, and return distributions.

Expand the option chain, contract identifiers, and calculation details as needed. Separate securities normally have separate curves, and options with different expiries are not combined into one expiry model. Missing contracts or quotes prevent incomplete strategy curves.

The current interface does not expose the account allocation workspace. Existing conversations remain saved; new recommendations follow the current subject.

Examples:

- “I am bullish on Apple. What stock allocation should I consider?”
- “I expect large moves in NVIDIA without a clear direction. Explore a straddle.”
- “Analyze 100 NVIDIA shares with one protective put.”
- “Analyze Nasdaq futures NQ=F and the payoff for one contract.”

## Four-panel analysis

Below the recommendation, the interface shows price, security risk, return curve, and future valuation scenarios. Wide screens use a 2×2 grid; narrow screens stack the panels. Stocks show conservative, base, and optimistic twelve-month model return scenarios. Derivatives show expiry or price-scenario payoffs from the actual legs.

## Saved investments

When an AI response contains a validated, structured investment recommendation, a plus button appears beside the Recommendation heading. Select it to keep the current investment or portfolio. Use the Analysis and Saved investments controls in the top bar to switch pages.

The Saved investments page keeps the selected ideas in a list on the left. Opening an item restores its recommendation and the same four analysis panels on the right. On smaller screens, the investment list becomes a horizontal strip and the panels stack vertically. Starting a new conversation does not remove saved investments; remove an item with the close control in its list row.

The earnings model uses revenue, net margin, and diluted EPS. Available quarterly year-over-year revenue growth is weighted toward recent periods and continued at 50%, holding diluted shares constant. Three P/E assumptions produce EPS, P/E, price, and return scenarios. Stock paths use geometric interpolation between the current price and scenario endpoint; no probabilities are assigned. ETFs, futures, and companies lacking suitable earnings or currency data do not receive forced company valuations.

When a new question is sent, the prior recommendation remains until new recommendation Markdown starts streaming. Mixed strategies validate all stock and option legs. Multi-security strategies sharing a currency and expiry can use a synchronized percentage-change scenario; the axis explicitly shows the common percentage move. This is not a correlation or probability forecast.

Earnings forecasts and model assumptions appear directly as ordinary content. Script URLs include file versions so refreshing retrieves the latest interface.

## Security comparisons

Compare multiple securities to align risk and expected-return scenarios. Prices retain their own currencies; forecast returns use percentages and a shared twelve-month horizon. Conservative, base, and optimistic scenarios switch together. Valuation lists every security and scenario, with earnings assumptions displayed directly. Insufficient common trading dates or financial data leave the affected results unavailable with an explanation. Risk follow-up questions retain comparison mode.
