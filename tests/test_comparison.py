from datetime import date, timedelta
from comparison import align_risks


def sample(symbol, start=0, vol=0.01):
    import math

    return dict(
        symbol=symbol,
        history=[
            dict(
                date=(date(2025, 1, 1) + timedelta(days=i)).isoformat(),
                close=100 * math.exp(vol * (i % 7) + i * 0.001),
            )
            for i in range(start, 100)
        ],
    )


def test_common_dates_and_shared_histogram():
    data = align_risks([sample("MSFT"), sample("NVDA", 20, 0.03)])
    a, b = [s["comparison_risk"] for s in data]
    assert a["start"] == b["start"] == "2025-01-21"
    assert a["end"] == b["end"] and a["samples"] == b["samples"] == 79
    assert b["annual_vol"] > a["annual_vol"]
    assert [(x["low"], x["high"]) for x in a["histogram"]] == [
        (x["low"], x["high"]) for x in b["histogram"]
    ]
    assert abs(sum(x["probability"] for x in a["histogram"]) - 100) < 0.0001


def test_no_overlap_no_fabricated_risk():
    a = sample("A")
    b = sample("B")
    b["history"] = []
    result = align_risks([a, b])
    assert all(s["comparison_risk"] is None for s in result)
    assert "comparison_risk" not in a
