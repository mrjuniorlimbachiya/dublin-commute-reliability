# Label definition and data notes

## Label
- Unit: one stop of one trip run (trip_id + start_date + stop_sequence).
- Delay: arrival delay in seconds, falling back to departure delay when missing.
- Label: the last delay prediction seen for that stop before the bus passed it.
  A stop counts as passed once a later stop of the same trip run has been seen.
- Delay-risk target: label > 300 seconds.
- Built by scripts/build_labels.py, saved to data/curated/labels.parquet.

## Data findings (checked 2026-11-19)
- 6.8M rows from 2,646 successful polls. 113 polls failed (mostly short DNS errors).
- The feed changed on every poll, so 60 second polling is not wasteful.
- 99.9% of trip_ids and stop_ids match the static schedule.
- Delay of 0 is a real value: no trip had 0 delay in every poll.
- 174,455 labelled stops over 16,613 trip runs: 25.3% over 5 minutes late,
  median delay 88 s, 95th percentile 891 s.

## Known limits
- Collection started 2026-11-17 11:27 UTC. Only the next 3 stops per trip were kept
  until 2026-11-19, and the next 10 after that.
- The last stop of each trip is never labelled.
- The label is the last prediction from the feed, not a measured arrival time.
