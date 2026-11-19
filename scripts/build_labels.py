import os

import duckdb

FILES = "data/raw/trip_updates/**/*.parquet"
os.makedirs("data/curated", exist_ok=True)

con = duckdb.connect()

# one row per prediction, using arrival delay and falling back to departure delay
con.sql(f"""
    create view obs as
    select trip_id, start_date, route_id, stop_id, stop_sequence, fetched_at,
           coalesce(arrival_delay, departure_delay) as delay
    from '{FILES}'
    where stop_id is not null
      and stop_sequence is not null
      and coalesce(arrival_delay, departure_delay) is not null
""")

# final_delay = the last prediction we saw for that stop
# only keep stops the bus has passed, i.e. we also saw a later stop of the same trip
con.sql("""
    create table labels as
    with per_stop as (
        select trip_id, start_date, stop_sequence,
               any_value(route_id) as route_id,
               any_value(stop_id) as stop_id,
               arg_max(delay, fetched_at) as final_delay,
               min(fetched_at) as first_seen,
               max(fetched_at) as last_seen,
               count(*) as n_obs
        from obs
        group by trip_id, start_date, stop_sequence
    ),
    with_max as (
        select *,
               max(stop_sequence) over (partition by trip_id, start_date) as max_seq_seen
        from per_stop
    )
    select * from with_max where stop_sequence < max_seq_seen
""")

print(con.sql("""
    select count(*) as labelled_stops,
           count(distinct trip_id || start_date) as trip_runs,
           round(100.0 * avg((final_delay > 300)::int), 1) as pct_over_5min,
           median(final_delay) as median_delay,
           quantile_cont(final_delay, 0.95) as p95_delay,
           median(date_diff('second', first_seen, last_seen)) as median_secs_visible
    from labels
""").df())

con.sql("copy labels to 'data/curated/labels.parquet' (format parquet)")