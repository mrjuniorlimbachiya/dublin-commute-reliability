import os
import time

import requests
from dotenv import load_dotenv
from google.transit import gtfs_realtime_pb2

load_dotenv()
URL = "https://api.nationaltransport.ie/gtfsr/v2/Vehicles"
HEADER = "x-api-key"

r = requests.get(URL, headers={HEADER: os.environ["NTA_API_KEY"]}, timeout=20)
print(r.status_code, r.headers.get("Content-Type"), len(r.content), "bytes")
r.raise_for_status()

feed = gtfs_realtime_pb2.FeedMessage()
feed.ParseFromString(r.content)
vehicles = [e.vehicle for e in feed.entity if e.HasField("vehicle")]
print("vehicles:", len(vehicles))
print("with position:", sum(v.HasField("position") for v in vehicles))
print("with trip_id:", sum(bool(v.trip.trip_id) for v in vehicles))
print("newest position age (s):", int(time.time()) - max(v.timestamp for v in vehicles))
print(vehicles[0])