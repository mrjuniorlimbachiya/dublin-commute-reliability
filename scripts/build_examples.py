import duckdb

FILES = "data/raw/trip_updates/**/*.parquet"
LABELS = "data/curated/labels.parquet"
STOP_TIMES = "data/static_gtfs/latest/stop_times.txt"

con = duckdb.connect()
con.sql("SET TimeZone='UTC'")

# scheduled arrival per trip and stop, in seconds after midnight
# (GTFS times can go past 24:00:00 for trips that run after midnight)
con.sql(f"""
    create table sched as
    select trip_id,
           stop_sequence::int as stop_sequence,
           split_part(arrival_time, ':', 1)::int * 3600
             + split_part(arrival_time, ':', 2)::int * 60
             + split_part(arrival_time, ':', 3)::int as sched_secs
    from read_csv('{STOP_TIMES}', header=true, all_varchar=true)
    where trip_id in (select distinct trip_id from '{LABELS}')
""")

con.sql(f"""
    create table examples as
    select o.trip_id, o.start_date, o.route_id, o.stop_id, o.stop_sequence,
           o.fetched_at,
           coalesce(o.arrival_delay, o.departure_delay) as current_delay,
           l.final_delay,
           strptime(o.start_date, '%Y%m%d') + to_seconds(s.sched_secs) as sched_local
    from '{FILES}' o
    join '{LABELS}' l
      on o.trip_id = l.trip_id
     and o.start_date = l.start_date
     and o.stop_sequence = l.stop_sequence
    join sched s
      on o.trip_id = s.trip_id
     and o.stop_sequence = s.stop_sequence
    where coalesce(o.arrival_delay, o.departure_delay) is not null
""")

# sched_local is Dublin clock time; convert it to a real timestamp,
# then work out how long until the bus is expected, using only what we know at poll time
con.sql("""
    create table examples2 as
    select *,
           date_diff('second', fetched_at, timezone('Europe/Dublin', sched_local))
             + current_delay as secs_to_arrival_expected,
           hour(sched_local) as sched_hour,
           dayofweek(sched_local) as sched_dow
    from examples
""")

print(con.sql("select count(*) as examples from examples2").df())

con.sql("copy examples2 to 'data/curated/examples.parquet' (format parquet)")

typical = con.sql(f"select median(final_delay) from '{LABELS}'").fetchall()[0][0]

print(con.sql(f"""
    select
        case
            when secs_to_arrival_expected < 300 then '0-5 min'
            when secs_to_arrival_expected < 600 then '5-10 min'
            when secs_to_arrival_expected < 1200 then '10-20 min'
            else '20+ min'
        end as time_before_stop,
        count(*) as examples,
        round(avg(abs(current_delay - final_delay)), 1) as mae_current_delay,
        round(avg(abs({typical} - final_delay)), 1) as mae_typical_delay,
        round(100.0 * avg((final_delay > 300)::int), 1) as pct_late_over_5min
    from examples2
    group by time_before_stop
    order by min(secs_to_arrival_expected)
""").df())