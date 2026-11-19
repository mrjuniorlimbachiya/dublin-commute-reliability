import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from dotenv import load_dotenv
from google.transit import gtfs_realtime_pb2

BASE_URL = "https://api.nationaltransport.ie/gtfsr/v2"
HEADER = "x-api-key" 
RAW_DIR = Path("data/raw")
STATIC_DIR = Path("data/static_gtfs/latest")
DUBLIN_BUS_AGENCY = "1"
MAX_STOPS = 10  # keep only the next 10 stops per trip, to limit storage
INTERVAL = 60  # seconds between polls

FEEDS = {
    "trip_updates": {
        "url": f"{BASE_URL}/TripUpdates",
        "log": RAW_DIR / "poll_log.jsonl",
    },
    "vehicles": {
        "url": f"{BASE_URL}/Vehicles",
        "log": RAW_DIR / "poll_log_vehicles.jsonl",
    },
}

# explicit schemas: every file has identical column types, even if a column is all-null
TRIP_SCHEMA = pa.schema(
    [
        ("fetched_at", pa.timestamp("us", tz="UTC")),
        ("feed_timestamp", pa.int64()),
        ("trip_id", pa.string()),
        ("route_id", pa.string()),
        ("direction_id", pa.int64()),
        ("start_date", pa.string()),
        ("start_time", pa.string()),
        ("stop_sequence", pa.int64()),
        ("stop_id", pa.string()),
        ("arrival_delay", pa.int64()),
        ("departure_delay", pa.int64()),
    ]
)

VEHICLE_SCHEMA = pa.schema(
    [
        ("fetched_at", pa.timestamp("us", tz="UTC")),
        ("feed_timestamp", pa.int64()),
        ("trip_id", pa.string()),
        ("route_id", pa.string()),
        ("direction_id", pa.int64()),
        ("start_date", pa.string()),
        ("start_time", pa.string()),
        ("vehicle_id", pa.string()),
        ("latitude", pa.float64()),
        ("longitude", pa.float64()),
        ("bearing", pa.float64()),
        ("position_timestamp", pa.int64()),
    ]
)

SCHEMAS = {"trip_updates": TRIP_SCHEMA, "vehicles": VEHICLE_SCHEMA}


def load_route_ids():
    routes = pd.read_csv(STATIC_DIR / "routes.txt", dtype=str)
    return set(routes.loc[routes.agency_id == DUBLIN_BUS_AGENCY, "route_id"])


def parse(payload, fetched_at, route_ids):
    """Trip updates: one row per upcoming stop, for our routes only."""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(payload)
    rows = []
    for e in feed.entity:
        if not e.HasField("trip_update"):
            continue
        tu = e.trip_update
        trip = tu.trip
        if trip.route_id not in route_ids:
            continue
        base = {
            "fetched_at": fetched_at,
            "feed_timestamp": feed.header.timestamp,
            "trip_id": trip.trip_id,
            "route_id": trip.route_id,
            "direction_id": trip.direction_id if trip.HasField("direction_id") else None,
            "start_date": trip.start_date,
            "start_time": trip.start_time,
        }
        stops = list(tu.stop_time_update)[:MAX_STOPS]
        if not stops:
            # keep trips with no stop updates (e.g. cancelled) as one row
            rows.append(
                {**base, "stop_sequence": None, "stop_id": None,
                 "arrival_delay": None, "departure_delay": None}
            )
            continue
        for stu in stops:
            rows.append(
                {
                    **base,
                    "stop_sequence": (
                        stu.stop_sequence if stu.HasField("stop_sequence") else None
                    ),
                    "stop_id": stu.stop_id or None,
                    "arrival_delay": (
                        stu.arrival.delay
                        if stu.HasField("arrival") and stu.arrival.HasField("delay")
                        else None
                    ),
                    "departure_delay": (
                        stu.departure.delay
                        if stu.HasField("departure") and stu.departure.HasField("delay")
                        else None
                    ),
                }
            )
    return rows


def parse_vehicles(payload, fetched_at, route_ids):
    """Vehicle positions: one row per bus on our routes that has a position."""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(payload)
    rows = []
    for e in feed.entity:
        if not e.HasField("vehicle"):
            continue
        v = e.vehicle
        if v.trip.route_id not in route_ids or not v.HasField("position"):
            continue
        rows.append(
            {
                "fetched_at": fetched_at,
                "feed_timestamp": feed.header.timestamp,
                "trip_id": v.trip.trip_id,
                "route_id": v.trip.route_id,
                "direction_id": v.trip.direction_id if v.trip.HasField("direction_id") else None,
                "start_date": v.trip.start_date,
                "start_time": v.trip.start_time,
                "vehicle_id": v.vehicle.id or None,
                "latitude": v.position.latitude,
                "longitude": v.position.longitude,
                "bearing": v.position.bearing if v.position.HasField("bearing") else None,
                "position_timestamp": v.timestamp if v.HasField("timestamp") else None,
            }
        )
    return rows


def write_snapshot(rows, fetched_at, kind):
    if not rows:
        return None
    folder = RAW_DIR / kind / f"date={fetched_at:%Y-%m-%d}" / f"hour={fetched_at:%H}"
    folder.mkdir(parents=True, exist_ok=True)
    final = folder / f"{fetched_at:%Y%m%dT%H%M%S}.parquet"
    tmp = final.with_suffix(".parquet.tmp")
    table = pa.Table.from_pylist(rows, schema=SCHEMAS[kind])
    pq.write_table(table, tmp, compression="zstd")
    os.replace(tmp, final)  # atomic: a crash never leaves a half-written file
    return final


def poll_feed(kind, api_key, route_ids):
    fetched_at = datetime.now(UTC)
    rec = {"ts": fetched_at.isoformat(), "ok": False, "rows": 0, "error": None}
    try:
        r = requests.get(FEEDS[kind]["url"], headers={HEADER: api_key}, timeout=20)
        r.raise_for_status()
        if kind == "trip_updates":
            rows = parse(r.content, fetched_at, route_ids)
        else:
            rows = parse_vehicles(r.content, fetched_at, route_ids)
        write_snapshot(rows, fetched_at, kind)
        rec.update(ok=True, rows=len(rows))
    except Exception as e:  # noqa: BLE001 - one bad poll must never stop the collector
        rec["error"] = f"{type(e).__name__}: {e}"
    log_file = FEEDS[kind]["log"]
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    print(kind, rec)
    return rec["ok"]


def poll_once(api_key, route_ids):
    # poll each feed separately so one failing never blocks the other
    results = [poll_feed(kind, api_key, route_ids) for kind in FEEDS]
    return all(results)


if __name__ == "__main__":
    load_dotenv()
    key = os.environ["NTA_API_KEY"]
    ids = load_route_ids()
    if "--once" in sys.argv:
        sys.exit(0 if poll_once(key, ids) else 1)
    while True:
        start = time.monotonic()
        poll_once(key, ids)
        time.sleep(max(0, INTERVAL - (time.monotonic() - start)))