
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ["NTA_API_KEY"]

URL = "https://api.nationaltransport.ie/gtfsr/v2/TripUpdates"
HEADER = "x-api-key"

resp = requests.get(URL, headers={HEADER: api_key}, timeout=20)

print(
    resp.status_code,
    resp.headers.get("Content-Type"),
    len(resp.content),
    "bytes"
)

resp.raise_for_status()

# Save the raw protobuf response
output_path = Path("data/raw/sample_trip_updates.pb")

output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_bytes(resp.content)

print(f"Saved successfully to {output_path}")