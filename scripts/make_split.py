import sys

import pandas as pd

sys.path.insert(0, "src")
from commute.split import time_split  # noqa: E402

df = pd.read_parquet(
    "data/curated/features.parquet",
    columns=["trip_id", "start_date", "fetched_at", "late"],
)

# first 70% of time is train, next 15% validation, last 15% test
times = df["fetched_at"].sort_values().reset_index(drop=True)
valid_start = times[int(len(times) * 0.70)]
test_start = times[int(len(times) * 0.85)]

out = time_split(df, valid_start, test_start)
print(out.groupby("split").agg(
    rows=("late", "size"),
    trip_runs=("trip_id", "nunique"),
    late_rate=("late", "mean"),
    first=("fetched_at", "min"),
    last=("fetched_at", "max"),
).to_string())