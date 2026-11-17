import json, os, sys, time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from dotenv import load_dotenv
from google.transit import gtfs_realtime_pb2

URL = "https://api.nationaltransport.ie/gtfsr/v2/TripUpdates"
HEADER = "x-api-key"                      # same header as scripts/explore_fetch.py
RAW_DIR = Path("data/raw/trip_updates")
LOG_FILE = Path("data/raw/poll_log.jsonl")
STATIC_DIR = Path("data/static_gtfs/latest")
DUBLIN_BUS_AGENCY = "1"
MAX_STOPS = 3        # keeping only the next 3 stops per trip, to limit storage
INTERVAL = 60        # seconds between polls


def load_route_ids():
    routes = pd.read_csv(STATIC_DIR / "routes.txt", dtype=str)
    return set(routes.loc[routes.agency_id == DUBLIN_BUS_AGENCY, "route_id"])



def parse(payload, fetched_at, route_ids):
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(payload)

    rows = []

    for e in feed.entity:
        if not e.HasField("trip_update"):
            continue

        tu = e.trip_update

        if tu.trip.route_id not in route_ids:
            continue

        # Common trip-level fields
        trip_fields = {
            "fetched_at": fetched_at,
            "feed_timestamp": feed.header.timestamp,
            "trip_id": tu.trip.trip_id,
            "route_id": tu.trip.route_id,
            "direction_id": tu.trip.direction_id if tu.trip.HasField("direction_id") else None,
            "start_date": tu.trip.start_date,
            "start_time": tu.trip.start_time,
        }

        # Keep trips even when they have no stop-time updates
        if len(tu.stop_time_update) == 0:
            rows.append({
                **trip_fields,
                "stop_sequence": None,
                "stop_id": None,
                "arrival_delay": None,
                "departure_delay": None,
            })
            continue

        # Keep only the first MAX_STOPS updates
        for stu in tu.stop_time_update[:MAX_STOPS]:

            arrival_delay = (
                stu.arrival.delay
                if stu.HasField("arrival") and stu.arrival.HasField("delay")
                else None
            )

            departure_delay = (
                stu.departure.delay
                if stu.HasField("departure") and stu.departure.HasField("delay")
                else None
            )

            rows.append({
                **trip_fields,
                "stop_sequence": stu.stop_sequence if stu.HasField("stop_sequence") else None,
                "stop_id": stu.stop_id,
                "arrival_delay": arrival_delay,
                "departure_delay": departure_delay,
            })

    return rows



def write_snapshot(rows, fetched_at):

    folder = (
        RAW_DIR
        / f"date={fetched_at:%Y-%m-%d}"
        / f"hour={fetched_at:%H}"
    )

    folder.mkdir(parents=True, exist_ok=True)

    file = f"{fetched_at:%Y%m%dT%H%M%S}.parquet"

    final = folder / file
    tmp = Path(str(final) + ".tmp")

    pq.write_table(
        pa.Table.from_pylist(rows),
        tmp,
        compression="zstd"
    )

    os.replace(tmp, final)

    return final


def poll_once(api_key, route_ids):
    fetched_at = datetime.now(UTC)
    rec = {"ts": fetched_at.isoformat(), "ok": False, "rows": 0, "error": None}
    try:
        r = requests.get(URL, headers={HEADER: api_key}, timeout=20)
        r.raise_for_status()
        rows = parse(r.content, fetched_at, route_ids)
        write_snapshot(rows, fetched_at)
        rec.update(ok=True, rows=len(rows))
    except Exception as e:                       # one bad poll must never stop the collector
        rec["error"] = f"{type(e).__name__}: {e}"
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    print(rec)
    return rec["ok"]


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