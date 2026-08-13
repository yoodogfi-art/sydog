"""
analysis/align.py

Joining series that don't share a calendar — the central-bank problem. Market
data is daily; BOK base rate is a step function that changes a handful of times a
year; CPI is monthly and released weeks late. A naive join on exact dates loses
almost everything.

The right tool is an AS-OF join: for each market date, take the most recent macro
value known on-or-before that date. pandas.merge_asof does this efficiently.
"""

from __future__ import annotations

import pandas as pd


def asof_join(left: pd.Series, right: pd.Series, direction: str = "backward") -> pd.DataFrame:
    """As-of join two date-indexed Series onto the LEFT's dates.

    left  : the higher-frequency series (e.g. daily market rate) -> drives dates
    right : the lower-frequency series (e.g. monthly CPI, step-fn policy rate)
    direction 'backward' = use the most recent right value at-or-before each
    left date (correct for released macro data: no lookahead).

    Returns a DataFrame indexed by left's dates with both columns, right
    forward-filled via the as-of logic.
    """
    l = left.sort_index().rename("left").reset_index()
    r = right.sort_index().rename("right").reset_index()
    lcol, rcol = l.columns[0], r.columns[0]
    merged = pd.merge_asof(
        l, r, left_on=lcol, right_on=rcol, direction=direction
    )
    out = merged.set_index(lcol)[["left", "right"]]
    out.columns = [left.name or "left", right.name or "right"]
    return out


def align_many(base: pd.Series, others: dict[str, pd.Series],
               direction: str = "backward") -> pd.DataFrame:
    """As-of join several series onto `base`'s dates. Keys name the columns."""
    frame = base.sort_index().to_frame(base.name or "base")
    for name, s in others.items():
        joined = asof_join(base, s.rename(name), direction=direction)
        frame[name] = joined[name].values
    return frame