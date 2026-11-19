import pandas as pd

from commute.split import time_split


def make_df():
    rows = []
    for i in range(48):
        start = pd.Timestamp("2026-11-17", tz="UTC") + pd.Timedelta(hours=i)
        # each run is seen for 5 hours, so some runs cross a boundary
        for minute in range(0, 300, 30):
            rows.append({
                "trip_id": f"T{i}",
                "start_date": "20261117",
                "fetched_at": start + pd.Timedelta(minutes=minute),
            })
    return pd.DataFrame(rows)


def test_split_is_ordered_and_trips_do_not_straddle():
    df = make_df()
    valid_start = pd.Timestamp("2026-11-18 06:00", tz="UTC")
    test_start = pd.Timestamp("2026-11-18 18:00", tz="UTC")
    out = time_split(df, valid_start, test_start, gap=pd.Timedelta(hours=3))

    t = out.groupby("split")["fetched_at"]
    assert t.max()["train"] < t.min()["valid"]
    assert t.max()["valid"] < t.min()["test"]
    assert t.min()["valid"] - t.max()["train"] >= pd.Timedelta(hours=3)
    assert out.groupby("trip_id")["split"].nunique().max() == 1
    assert len(out) < len(df)  # straddling trips really were removed