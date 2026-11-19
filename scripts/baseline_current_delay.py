import duckdb

FILES = "data/raw/trip_updates/**/*.parquet"
LABELS = "data/curated/labels.parquet"

con = duckdb.connect()

# every poll in which a labelled stop was visible, with its current prediction
con.sql(f"""
    create table examples as
    select o.trip_id, o.start_date, o.route_id, o.stop_id, o.stop_sequence,
           o.fetched_at,
           coalesce(o.arrival_delay, o.departure_delay) as current_delay,
           l.final_delay,
           date_diff('second', o.fetched_at, l.last_seen) as secs_to_pass
    from '{FILES}' o
    join '{LABELS}' l
      on o.trip_id = l.trip_id
     and o.start_date = l.start_date
     and o.stop_sequence = l.stop_sequence
    where coalesce(o.arrival_delay, o.departure_delay) is not null
""")

# dumbest baseline: always predict the typical delay
typical = con.sql(f"select median(final_delay) from '{LABELS}'").fetchall()[0][0]

# error in seconds, grouped by how long before the bus passed the stop we looked
print(con.sql(f"""
    select
        case
            when secs_to_pass < 300 then '0-5 min'
            when secs_to_pass < 600 then '5-10 min'
            when secs_to_pass < 1200 then '10-20 min'
            else '20+ min'
        end as time_before_stop,
        count(*) as examples,
        round(avg(abs(current_delay - final_delay)), 1) as mae_current_delay,
        round(avg(abs({typical} - final_delay)), 1) as mae_typical_delay
    from examples
    group by time_before_stop
    order by min(secs_to_pass)
""").df())