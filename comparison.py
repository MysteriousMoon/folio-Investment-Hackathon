"""Risk comparisons calibrated on precisely the same trading dates."""

import numpy as np


def align_risks(securities):
    valid = [s for s in securities if not s.get("error")]
    if len(valid) < 2:
        return securities
    dates = sorted(
        set.intersection(*[{p["date"] for p in s.get("history", [])} for s in valid])
    )[-253:]
    result = [dict(s, comparison_risk=None) for s in securities]
    if len(dates) < 31:
        return result
    shocks = np.random.default_rng(20261017).normal(0, 1, 20000)
    samples = []
    for s in result:
        if s.get("error"):
            continue
        history = {p["date"]: p["close"] for p in s["history"]}
        closes = np.array([history[d] for d in dates], dtype=float)
        if np.any(closes <= 0):
            continue
        returns = np.diff(np.log(closes))
        vol = float(returns.std(ddof=1) * np.sqrt(252))
        sim = np.expm1(shocks * vol * np.sqrt(0.25)) * 100
        threshold = float(np.quantile(sim, 0.05))
        risk = dict(
            annual_vol=vol * 100,
            historical_max_drawdown=float(
                np.min(closes / np.maximum.accumulate(closes) - 1)
            )
            * 100,
            var95=max(0, -threshold),
            cvar95=max(0, -float(sim[sim <= threshold].mean())),
            p05=threshold,
            median=float(np.median(sim)),
            p95=float(np.quantile(sim, 0.95)),
            start=dates[0],
            end=dates[-1],
            samples=len(returns),
            months=3,
        )
        s["comparison_risk"] = risk
        samples.append((risk, sim))
    if samples:
        edges = np.linspace(
            min(v.min() for _, v in samples), max(v.max() for _, v in samples), 25
        )
        if edges[0] == edges[-1]:
            edges = np.linspace(-1, 1, 25)
        for risk, sim in samples:
            counts, _ = np.histogram(sim, bins=edges)
            risk["histogram"] = [
                dict(
                    low=float(edges[i]),
                    high=float(edges[i + 1]),
                    probability=float(c) / len(sim) * 100,
                )
                for i, c in enumerate(counts)
            ]
    return result
