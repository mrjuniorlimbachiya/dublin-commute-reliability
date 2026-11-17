
from datetime import UTC, datetime
from google.transit import gtfs_realtime_pb2
import poller


def make_feed():
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"

    # Entity 1: R1 with 5 stop-time updates
    e = feed.entity.add()
    e.id = "1"
    e.trip_update.trip.trip_id = "T1"
    e.trip_update.trip.route_id = "R1"

    for i in range(5):
        stu = e.trip_update.stop_time_update.add()
        stu.stop_sequence = i + 1
        stu.stop_id = f"STOP_{i + 1}"
        stu.arrival.delay = 0

    # Entity 2: OTHER with one stop update (should be filtered out)
    e2 = feed.entity.add()
    e2.id = "2"
    e2.trip_update.trip.trip_id = "T2"
    e2.trip_update.trip.route_id = "OTHER"

    stu = e2.trip_update.stop_time_update.add()
    stu.stop_sequence = 1
    stu.stop_id = "OTHER_STOP"
    stu.arrival.delay = 120

    # Entity 3: R1 with no stop-time updates
    e3 = feed.entity.add()
    e3.id = "3"
    e3.trip_update.trip.trip_id = "T3"
    e3.trip_update.trip.route_id = "R1"

    return feed.SerializeToString()


def test_parse():
    rows = poller.parse(
        make_feed(),
        datetime.now(UTC),
        {"R1"}
    )

    # Only R1 rows should be retained
    assert all(row["route_id"] == "R1" for row in rows)

    # T1 should have at most MAX_STOPS rows
    t1_rows = [row for row in rows if row["trip_id"] == "T1"]
    assert len(t1_rows) == min(5, poller.MAX_STOPS)

    # A real zero delay must remain zero, not None
    assert all(row["arrival_delay"] == 0 for row in t1_rows)

    # Departure delay should be None
    assert all(row["departure_delay"] is None for row in t1_rows)

    # T3 must still produce exactly one row
    t3_rows = [row for row in rows if row["trip_id"] == "T3"]
    assert len(t3_rows) == 1

    assert t3_rows[0]["stop_id"] is None
    assert t3_rows[0]["stop_sequence"] is None
    assert t3_rows[0]["arrival_delay"] is None
    assert t3_rows[0]["departure_delay"] is None

    # OTHER must not appear
    assert not any(row["trip_id"] == "T2" for row in rows)

    print("All tests passed!")


if __name__ == "__main__":
    test_parse()