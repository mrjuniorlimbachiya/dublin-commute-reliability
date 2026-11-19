import duckdb

FILES = "data/raw/trip_updates/**/*.parquet"
EXAMPLES = "data/curated/examples.parquet"

con = duckdb.connect()
con.sql("SET TimeZone='UTC'")

# for every poll and trip, keep only the next stop the bus will reach
# and use its delay as "how late is this bus right now"
con.sql(f"""
    create table next_stop as
    select fetched_at, route_id, trip_id,
           coalesce(arrival_delay, departure_delay) as d,
           row_number() over (partition by fetched_at, trip_id order by stop_sequence) as rn
    from '{FILES}'
    where coalesce(arrival_delay, departure_delay) is not null
""")

# one row per poll and route: average delay of its buses at that moment
con.sql("""
    create table route_now as
    select fetched_at, route_id,
           avg(d) as delay_now,
           avg((d > 300)::int) as late_share_now
    from next_stop
    where rn = 1
    group by fetched_at, route_id
""")

# smooth over the last 15 polls of the same route (about 15 minutes)
# rows are ordered by time, so a row never sees anything later than itself
con.sql("""
    create table route_recent as
    select fetched_at, route_id,
           avg(delay_now) over w as route_delay_15m,
           avg(late_share_now) over w as route_late_share_15m
    from route_now
    window w as (partition by route_id order by fetched_at
                 rows between 14 preceding and current row)
""")

con.sql(f"""
    create table features as
    select e.route_id, e.sched_hour, e.sched_dow,
           e.current_delay, e.secs_to_arrival_expected,
           r.route_delay_15m, r.route_late_share_15m,
           e.fetched_at, e.trip_id, e.start_date, e.stop_sequence,
           e.final_delay,
           (e.final_delay > 300)::int as late
    from '{EXAMPLES}' e
    left join route_recent r
      on e.fetched_at = r.fetched_at and e.route_id = r.route_id
""")

print(con.sql("select count(*) as rows, avg(late) as late_rate from features").df())
print(con.sql("""
    select count(*) filter (where route_delay_15m is null) as missing_route_delay,
           count(*) filter (where current_delay is null) as missing_current_delay
    from features
""").df())

con.sql("copy features to 'data/curated/features.parquet' (format parquet)")