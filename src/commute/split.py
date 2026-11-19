import pandas as pd

DEFAULT_GAP = pd.Timedelta(hours=3)


def time_split(df, valid_start, test_start, gap=DEFAULT_GAP):
    """Label each row train / valid / test by time. Never split randomly."""
    t = df["fetched_at"]
    split = pd.Series("drop", index=df.index)
    split[t < valid_start - gap] = "train"
    split[(t >= valid_start) & (t < test_start - gap)] = "valid"
    split[t >= test_start] = "test"

    out = df.assign(split=split)
    out = out[out["split"] != "drop"]

    # a trip run seen in more than one split would leak, so drop those
    n_splits = out.groupby(["trip_id", "start_date"])["split"].transform("nunique")
    return out[n_splits == 1]