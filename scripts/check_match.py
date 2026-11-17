
import glob

import pandas as pd

rt = pd.concat(
    pd.read_parquet(f)
    for f in glob.glob("data/raw/trip_updates/**/*.parquet", recursive=True)
)

trips = pd.read_csv("data/static_gtfs/latest/trips.txt", dtype=str)
stops = pd.read_csv("data/static_gtfs/latest/stops.txt", dtype=str)

# Share of distinct real-time trip_ids found in static GTFS trips
print(rt.trip_id.drop_duplicates().isin(trips.trip_id).mean())

# Share of distinct real-time stop_ids found in static GTFS stops
print(rt.stop_id.drop_duplicates().isin(stops.stop_id).mean())
