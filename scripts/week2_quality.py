"""Week 2, step 1: a quick data-quality overview of everything we have collected.

Run from the project root:  python scripts\\week2_quality.py
"""

import duckdb
import pandas as pd

# Show all columns when printing tables (otherwise pandas hides some with "...").
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)

# DuckDB can read every parquet file in every date=/hour= folder with one pattern.
# The "**" means "any number of folders in between".
FILES = "data/raw/trip_updates/**/*.parquet"

con = duckdb.connect()  # an in-memory database: nothing is saved anywhere

# Show times in UTC so the results match our folder names.
# (In November Dublin time equals UTC. In summer Dublin is one hour ahead.)
con.sql("SET TimeZone='UTC'")


def show(title, sql):
    """Run an SQL query and print the result as a table, under a title."""
    print(f"=== {title} ===")
    print(con.sql(sql).df())
    print()


# ---------------------------------------------------------------------------
# 1. Overview: how much data do we have?
# ---------------------------------------------------------------------------
# "polls" counts the different moments we asked the feed for data.
show(
    "1. Overview",
    f"""
    SELECT
        count(*)                    AS total_rows,
        count(DISTINCT fetched_at)  AS polls,
        min(fetched_at)             AS first_poll,
        max(fetched_at)             AS last_poll
    FROM '{FILES}'
    """,
)

# ---------------------------------------------------------------------------
# 2. Is the feed itself updating every minute?
# ---------------------------------------------------------------------------
# Every snapshot carries a "feed_timestamp": the moment NTA generated it.
# If two polls in a row have the SAME feed_timestamp, we downloaded the same
# data twice, which means polling every 60 seconds was more often than needed.
#
# Step by step:
#   polls:   one row per poll with its feed_timestamp
#   compare: lag() looks at the previous poll's feed_timestamp, so we can
#            check whether it is equal to the current one
#   The final query counts how many polls were repeats.
show(
    "2. Polls where the feed had not changed since the previous poll",
    f"""
    WITH polls AS (
        SELECT DISTINCT fetched_at, feed_timestamp
        FROM '{FILES}'
    ),
    compare AS (
        SELECT
            feed_timestamp = lag(feed_timestamp) OVER (ORDER BY fetched_at) AS is_repeat
        FROM polls
    )
    SELECT
        count(*)                               AS polls,
        sum(is_repeat::INT)                    AS repeated_polls,
        round(100.0 * avg(is_repeat::INT), 1)  AS percent_repeated
    FROM compare
    """,
)

# ---------------------------------------------------------------------------
# 3. How often is the delay exactly 0, by hour of day?
# ---------------------------------------------------------------------------
# Many delays are exactly 0. Some are real (the bus is on time), but some may
# be placeholders for buses that have not started yet. If the share of zeros
# changes a lot during the day, that is a hint we need to treat them carefully.
# We only look at rows where arrival_delay exists (is not NULL).
show(
    "3. Share of arrival_delay = 0, by hour of day (UTC)",
    f"""
    SELECT
        hour(fetched_at)                           AS hour_utc,
        count(*)                                   AS rows_with_delay,
        round(100.0 * avg((arrival_delay = 0)::INT), 1) AS percent_zero
    FROM '{FILES}'
    WHERE arrival_delay IS NOT NULL
    GROUP BY hour_utc
    ORDER BY hour_utc
    """,
)