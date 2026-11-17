
from pathlib import Path
from google.transit import gtfs_realtime_pb2

data = Path("data/raw/sample_trip_updates.pb").read_bytes()
feed = gtfs_realtime_pb2.FeedMessage()
feed.ParseFromString(data)

print("timestamp:", feed.header.timestamp, "entities:", len(feed.entity))
print(feed.entity[0])

# 1. Count entities with a trip_update
trip_update_count = 0

# 2. Count stop_time_updates with arrival and departure delay
arrival_delay_count = 0
departure_delay_count = 0

# 3. Collect distinct route_ids
route_ids = set()

# 4. Count trips with zero stop_time_updates
zero_stop_updates_count = 0

for entity in feed.entity:

    if entity.HasField("trip_update"):
        trip_update_count += 1

        trip = entity.trip_update
        route_id = trip.trip.route_id

        if route_id:
            route_ids.add(route_id)

        if len(trip.stop_time_update) == 0:
            zero_stop_updates_count += 1

        for stu in trip.stop_time_update:

            if stu.HasField("arrival"):
                arrival_delay_count += 1

            if stu.HasField("departure"):
                departure_delay_count += 1


print("\n--- GTFS Realtime Analysis ---")
print("Entities with trip updates:", trip_update_count)
print("Stop updates with arrival:", arrival_delay_count)
print("Stop updates with departure:", departure_delay_count)
print("Distinct route IDs:", len(route_ids))
print("Five example route IDs:", list(route_ids)[:5])
print("Trips with zero stop-time updates:", zero_stop_updates_count)
