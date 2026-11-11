"""
research/numbers.py

Pure number crunching for value commands — no formatting, no Telegram.
Every function takes (df, col, cols, mode, ...) and returns a dict of raw
floats, or None if the column has no usable data. Date selection always goes
through research/calendar.py so all commands agree on "previous market day".

Returned dict shapes (what render.py / line functions read):
  snapshot_numbers -> {current, d1, d1_base, w1, w1_base, m1, m1_base, y1, y1_base}
  period_numbers   -> {current, delta, base}
  spec_numbers     -> {current, delta, base}
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd

from research import calendar as cal
from research.columns import DATE_COL


def value_at(df, col, idx):
    """Value of `col` at book row `idx`, or None if missing/NaN."""
    if idx is None:
        return None
    v = df.iloc[df.index.get_loc(idx)][col] if idx in df.index else df.iloc[idx][col]
    return None if pd.isna(v) else v


def current(df, col):
    """Latest real value for a column, skipping trailing NaN -> (pos, date, value)."""
    for pos in range(df.shape[0]):
        v = df.iloc[pos][col]
        if not pd.isna(v):
            return pos, df.iloc[pos][DATE_COL], v
    return None


def _asof_excluding_current(df, cols, target_date, mode):
    """As-of row for target_date, but never the newest row itself."""
    idx = cal.asof_index(df, cols, target_date, mode)
    if idx is not None and df.index.get_loc(idx) == 0:
        return None
    return idx


def snapshot_numbers(df, col, cols, mode):
    """Current + 1d/1w/1mo/1y deltas. 1d uses the previous real-market row
    (per calendar mode); w/m/y use as-of lookback honoring the same mode."""
    cur = current(df, col)
    if cur is None:
        return None
    _, cur_date, cur_val = cur

    def delta_at(idx):
        base = value_at(df, col, idx)
        if base is None:
            return None, None
        return cur_val - base, base

    d1, d1b = delta_at(cal.resolve_prev_market_idx(df, cols, mode))

    def lookback(days):
        return delta_at(_asof_excluding_current(df, cols, cur_date - timedelta(days=days), mode))

    w1, w1b = lookback(7)
    m1, m1b = lookback(30)
    y1, y1b = lookback(365)
    return {
        "current": cur_val,
        "d1": d1, "d1_base": d1b,
        "w1": w1, "w1_base": w1b,
        "m1": m1, "m1_base": m1b,
        "y1": y1, "y1_base": y1b,
    }


def period_numbers(df, col, cols, mode, days):
    """Current + change over a single trailing window of `days`."""
    cur = current(df, col)
    if cur is None:
        return None
    _, cur_date, cur_val = cur
    idx = _asof_excluding_current(df, cols, cur_date - timedelta(days=days), mode)
    base = value_at(df, col, idx)
    if base is None:
        return {"current": cur_val, "delta": None, "base": None}
    return {"current": cur_val, "delta": cur_val - base, "base": base}


def spec_numbers(df, col, cols, mode, start_date, end_date):
    """Value at end_date + change since start_date (both as-of)."""
    if current(df, col) is None:
        return None
    end_val = value_at(df, col, cal.asof_index(df, cols, end_date, mode))
    base = value_at(df, col, cal.asof_index(df, cols, start_date, mode))
    if end_val is None or base is None:
        return None
    return {"current": end_val, "delta": end_val - base, "base": base}
