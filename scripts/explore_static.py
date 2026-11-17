from pathlib import Path

import pandas as pd
from google.transit import gtfs_realtime_pb2

d = Path("data/static_gtfs/latest")

agency = pd.read_csv(d / "agency.txt")
routes = pd.read_csv(d / "routes.txt")

print(agency[["agency_id", "agency_name"]])
print(routes.head())

feed = gtfs_realtime_pb2.FeedMessage()
feed.ParseFromString(
    Path("data/raw/sample_trip_updates.pb").read_bytes()
)

feed_routes = pd.Series(
    [e.trip_update.trip.route_id for e in feed.entity],
    name="route_id"
)

# Merge feed routes with static GTFS routes
feed_df = pd.DataFrame(feed_routes)

merged = feed_df.merge(
    routes,
    on="route_id",
    how="left"
)

# Merge with agency to get agency names
merged = merged.merge(
    agency[["agency_id", "agency_name"]],
    on="agency_id",
    how="left"
)

# Count feed entities per agency
agency_counts = merged.groupby("agency_name").size().reset_index(
    name="feed_entity_count"
)

print("\n--- Feed Entities per Agency ---")
print(agency_counts)
