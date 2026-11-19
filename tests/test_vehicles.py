from datetime import UTC, datetime

import poller
from google.transit import gtfs_realtime_pb2


def make_feed():
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    for i, route in enumerate(["R1", "OTHER"]):
        e = feed.entity.add()
        e.id = str(i)
        e.vehicle.trip.trip_id = f"T{i}"
        e.vehicle.trip.route_id = route
        e.vehicle.position.latitude = 53.35
        e.vehicle.position.longitude = -6.26
        e.vehicle.vehicle.id = str(i)
    # a vehicle with no position cannot go on a map
    e = feed.entity.add()
    e.id = "x"
    e.vehicle.trip.route_id = "R1"
    return feed.SerializeToString()


def test_parse_vehicles_keeps_only_our_routes_with_a_position():
    rows = poller.parse_vehicles(make_feed(), datetime.now(UTC), {"R1"})
    assert len(rows) == 1
    assert rows[0]["route_id"] == "R1"
    assert abs(rows[0]["latitude"] - 53.35) < 1e-4
    assert rows[0]["bearing"] is None