import duckdb

FILES = "data/raw/trip_updates/**/*.parquet"

con = duckdb.connect()

# one row per trip run, only trips seen in at least 10 polls
con.sql(f"""
    create view per_trip as
    select
        trip_id,
        start_date,
        count(distinct fetched_at) as polls_seen,
        count(distinct arrival_delay) as distinct_delays,
        min(arrival_delay) as min_delay,
        max(arrival_delay) as max_delay
    from '{FILES}'
    where arrival_delay is not null
    group by trip_id, start_date
    having count(distinct fetched_at) >= 10
""")

# trips whose delay was 0 in every poll are probably placeholders
print(con.sql("""
    select
        count(*) as trips,
        round(100.0 * avg((min_delay = 0 and max_delay = 0)::int), 1) as pct_always_zero,
        round(100.0 * avg((distinct_delays = 1)::int), 1) as pct_never_changed
    from per_trip
""").df())

# how many different delay values does a trip show?
print(con.sql("""
    select
        case
            when distinct_delays = 1 then '1'
            when distinct_delays <= 3 then '2-3'
            when distinct_delays <= 10 then '4-10'
            else '11+'
        end as delay_values,
        count(*) as trips,
        round(100.0 * count(*) / sum(count(*)) over (), 1) as pct_of_trips
    from per_trip
    group by delay_values
    order by min(distinct_delays)
""").df())