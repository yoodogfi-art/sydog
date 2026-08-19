"""
research/calendar.py

Independent date-selection route. Decides, for a given book, which rows count
as *real* observations versus carried-forward fills — and resolves the
reference row for a lookback. Pulled out of the engine so:

  1. every command path (snapshot / period / spec) shares one implementation, and
  2. different instruments can use different strategies via config
     ("date_mode"), without touching the engine.

Strategies (config: instrument["date_mode"], default "skip_fill"):
  "skip_fill"  — the CSV forward-fills non-market days (weekends/holidays) as
                 duplicate rows. Treat a row as a real observation only if its
                 value differs from the previous kept row. This is the KTB case.
  "raw"        — every row is a real observation (no fill in the source). Use
                 for books that already contain only market days.

Add a new strategy = one function here + one registry entry. The engine calls
resolve_prev_market_idx() and asof_index() without knowing which strategy ran.
"""

from __future__ import annotations

import pandas as pd

DATE_COL = "일자"


# ---------------------------------------------------------------------------
# Strategy: which earlier row is the "previous real observation" vs row 0
# ---------------------------------------------------------------------------
def _first_real_pos(df: pd.DataFrame, cols: list[str]) -> int | None:
    """Position of the newest row that has real (non-NaN) values in cols.
    A trailing all-blank row (e.g. today not yet published) is skipped."""
    if not cols:
        return None
    for pos in range(df.shape[0]):
        if not df.iloc[pos][cols].isna().all():
            return pos
    return None


def _prev_skip_fill(df: pd.DataFrame, cols: list[str]) -> int | None:
    """First row BELOW the newest real row whose values differ from it (skip
    carried-forward fills). Anchors on the first non-NaN row so a blank trailing
    row (today unpublished) doesn't collapse the 1d delta to zero. Compares only
    this book's own value columns. None if no differing earlier row exists."""
    start = _first_real_pos(df, cols)
    if start is None or start + 1 >= df.shape[0]:
        return None
    latest = df.iloc[start][cols]
    for pos in range(start + 1, df.shape[0]):
        if not df.iloc[pos][cols].equals(latest):
            return df.index[pos]
    return None


def _prev_raw(df: pd.DataFrame, cols: list[str]) -> int | None:
    """Literal previous row — every row is a real observation."""
    return 1 if df.shape[0] >= 2 else None


_PREV_STRATEGIES = {
    "skip_fill": _prev_skip_fill,
    "raw": _prev_raw,
}

DEFAULT_MODE = "skip_fill"


def resolve_prev_market_idx(df, cols, mode: str = DEFAULT_MODE) -> int | None:
    """Book-level index of the previous real-market row (for 1d deltas)."""
    fn = _PREV_STRATEGIES.get(mode, _prev_skip_fill)
    return fn(df, cols)


# ---------------------------------------------------------------------------
# As-of reference for a target date, honoring the fill strategy
# ---------------------------------------------------------------------------
def asof_index(df, cols, target_date, mode: str = DEFAULT_MODE) -> int | None:
    """Index of the row to use as the reference for `target_date`.

    'skip_fill': the most recent real-observation row on-or-before target_date
    (so a lookback that lands on a carried-forward day steps back to the last
    real move). 'raw': simply the most recent row on-or-before target_date.
    Returns None if no row qualifies.
    """
    on_or_before = df[df[DATE_COL] <= target_date]
    if on_or_before.empty:
        return None

    if mode == "raw" or not cols:
        return on_or_before.index[0]

    # skip_fill: walk down from the newest qualifying row; if it's a fill
    # (equals the row just above it), step further back to the last real move.
    idx = on_or_before.index[0]
    pos = df.index.get_loc(idx)
    while pos + 1 < df.shape[0]:
        if not df.iloc[pos][cols].equals(df.iloc[pos + 1][cols]):
            break  # this row differs from the one below -> it's a real obs
        pos += 1
    return df.index[pos]