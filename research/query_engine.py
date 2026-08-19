"""
research/query_engine.py

Read-only research layer. Style-agnostic: it computes raw numbers
(current value + 1d/1w/1y deltas, or a spec two-date delta) and delegates ALL
display to research/formatters.py via the instrument's `style`. The engine never
names a specific book or style.

Data contract (from core/data_processor.py):
  * one CSV per processed sheet, in PROCESSED_DIR
  * encoding utf-8-sig (auto-detected across a fallback list anyway)
  * date column '일자', values 'yyyy-mm-dd' strings, sorted descending
  * value columns named '<indicator>_val_<j>'
  * latest row may be entirely NaN -> per-column "last real value" is used
"""

from __future__ import annotations

import os
import re
from datetime import timedelta
from pathlib import Path

import pandas as pd

from research.formatters import get_style
from config.instruments import INSTRUMENTS, GROUPS
from storage.loader import load_market, DATE_COL
from research import calendar as cal

_TENOR_RE = re.compile(r"(\d+)\s*년")


# ---------------------------------------------------------------------------
# Loading  (delegates to the single storage loader)
# ---------------------------------------------------------------------------
def _load_csv(file_stem: str) -> pd.DataFrame:
    # storage.loader owns encoding/date/sort; engine owns computation.
    return load_market(file_stem)


# ---------------------------------------------------------------------------
# Column helpers
# ---------------------------------------------------------------------------
def _tenor_label(col: str) -> str:
    m = _TENOR_RE.search(col)
    if m:
        return f"{int(m.group(1))}Y"
    return re.sub(r"_val_\d+$", "", col)


def _value_columns(df: pd.DataFrame, whitelist=None) -> list[str]:
    cols = [c for c in df.columns if c != DATE_COL]
    if whitelist:
        # keep whitelist order, silently drop any not present
        return [c for c in whitelist if c in cols]
    return cols


def _series(df: pd.DataFrame, col: str) -> pd.DataFrame:
    return df[[DATE_COL, col]].dropna(subset=[col]).reset_index(drop=True)


def _asof_on_or_before(s: pd.DataFrame, target_date, col: str):
    older = s[s[DATE_COL] <= target_date]
    if older.empty:
        return None
    row = older.iloc[0]
    return row[DATE_COL], row[col]


# ---------------------------------------------------------------------------
# Raw number computation (no formatting) — all date selection via calendar.py
# ---------------------------------------------------------------------------
def _col_value_at(df, col, idx):
    """Value of `col` at book row `idx`, or None if missing/NaN."""
    if idx is None:
        return None
    v = df.iloc[df.index.get_loc(idx)][col] if idx in df.index else df.iloc[idx][col]
    return None if pd.isna(v) else v


def _cur(df, col):
    """Latest (date, value) for a column, skipping trailing NaN. (pos, date, val)."""
    for pos in range(df.shape[0]):
        v = df.iloc[pos][col]
        if not pd.isna(v):
            return pos, df.iloc[pos][DATE_COL], v
    return None


def _snapshot_numbers(df, col, cols, mode):
    """Current + 1d/1w/1mo/1y deltas. 1d uses the previous real-market row
    (per calendar mode); w/m/y use as-of lookback honoring the same mode."""
    cur = _cur(df, col)
    if cur is None:
        return None
    _, cur_date, cur_val = cur

    def delta_at(idx):
        base = _col_value_at(df, col, idx)
        if base is None:
            return None, None
        return cur_val - base, base

    # 1d: previous real-market row (book-level)
    prev_idx = cal.resolve_prev_market_idx(df, cols, mode)
    d1, d1b = delta_at(prev_idx)

    # w/m/y: as-of the target calendar date, honoring fill strategy
    def asof_delta(days):
        idx = cal.asof_index(df, cols, cur_date - timedelta(days=days), mode)
        # exclude the current row itself
        if idx is not None and df.index.get_loc(idx) == 0:
            return None, None
        return delta_at(idx)

    w1, w1b = asof_delta(7)
    m1, m1b = asof_delta(30)
    y1, y1b = asof_delta(365)
    return {
        "current": cur_val,
        "d1": d1, "d1_base": d1b,
        "w1": w1, "w1_base": w1b,
        "m1": m1, "m1_base": m1b,
        "y1": y1, "y1_base": y1b,
    }


def _period_numbers(df, col, days, cols, mode):
    """Current + change over a single trailing window of `days`."""
    cur = _cur(df, col)
    if cur is None:
        return None
    _, cur_date, cur_val = cur
    idx = cal.asof_index(df, cols, cur_date - timedelta(days=days), mode)
    if idx is not None and df.index.get_loc(idx) == 0:
        idx = None
    base = _col_value_at(df, col, idx)
    if base is None:
        return {"current": cur_val, "delta": None, "base": None}
    return {"current": cur_val, "delta": cur_val - base, "base": base}


def _spec_numbers(df, col, start_date, end_date, cols, mode):
    cur = _cur(df, col)
    if cur is None:
        return None
    end_idx = cal.asof_index(df, cols, end_date, mode)
    start_idx = cal.asof_index(df, cols, start_date, mode)
    end_val = _col_value_at(df, col, end_idx)
    base = _col_value_at(df, col, start_idx)
    if end_val is None or base is None:
        return None
    return {"current": end_val, "delta": end_val - base, "base": base}


# ---------------------------------------------------------------------------
# Rendering (uses the style formatter)
# ---------------------------------------------------------------------------
def _resolve(instrument: dict, command: str):
    style_name = instrument["style"]
    fmt = get_style(style_name)
    decimals = instrument.get("decimals", fmt["decimals"])
    mode = instrument.get("date_mode", cal.DEFAULT_MODE)  # noqa: F841 (used by callers)
    multi_row = instrument.get("multi_row", fmt["multi_row"])
    label = instrument.get("label", command)
    return fmt, decimals, multi_row, label, mode


def _snapshot_line(fmt, decimals, tenor, nums):
    v = fmt["value"](nums["current"], decimals)
    d1 = fmt["delta"](nums["d1"], nums["d1_base"], decimals)
    w1 = fmt["delta"](nums["w1"], nums["w1_base"], decimals)
    m1 = fmt["delta"](nums["m1"], nums["m1_base"], decimals)
    y1 = fmt["delta"](nums["y1"], nums["y1_base"], decimals)
    head = f"{tenor}: {v}" if tenor else v
    return f"{head} | 1d: {d1}, 1w: {w1}, 1mo: {m1}, 1y: {y1}"


def snapshot(command: str, instrument: dict) -> str:
    df = _load_csv(instrument.get("file", command))
    fmt, decimals, multi_row, label, mode = _resolve(instrument, command)
    cols = _value_columns(df, instrument.get("cols"))

    if multi_row:
        lines = [f"[{label}]"]
        for col in cols:
            nums = _snapshot_numbers(df, col, cols, mode)
            if nums is None:
                continue
            lines.append(_snapshot_line(fmt, decimals, _tenor_label(col), nums))
        if len(lines) == 1:
            lines.append("no data")
        return "\n".join(lines)

    # single headline value
    if not cols:
        return f"[{label}] no data"
    nums = _snapshot_numbers(df, cols[0], cols, mode)
    if nums is None:
        return f"[{label}] no data"
    return f"[{label}] " + _snapshot_line(fmt, decimals, None, nums)


def spec(command: str, instrument: dict, start_date, end_date) -> str:
    df = _load_csv(instrument.get("file", command))
    fmt, decimals, multi_row, label, mode = _resolve(instrument, command)
    cols = _value_columns(df, instrument.get("cols"))
    tag = f"{start_date:%Y%m%d}-{end_date:%Y%m%d}"

    if multi_row:
        lines = [f"[{label}] {tag}"]
        for col in cols:
            n = _spec_numbers(df, col, start_date, end_date, cols, mode)
            if n is None:
                continue
            v = fmt["value"](n["current"], decimals)
            d = fmt["delta"](n["delta"], n["base"], decimals)
            lines.append(f"{_tenor_label(col)}: {v} | Δ: {d}")
        if len(lines) == 1:
            lines.append("no data in range")
        return "\n".join(lines)

    if not cols:
        return f"[{label}] {tag} no data"
    n = _spec_numbers(df, cols[0], start_date, end_date, cols, mode)
    if n is None:
        return f"[{label}] {tag} no data in range"
    v = fmt["value"](n["current"], decimals)
    d = fmt["delta"](n["delta"], n["base"], decimals)
    return f"[{label}] {tag} {v} | Δ: {d}"


def period(command: str, instrument: dict, days: int, tag: str) -> str:
    """Current value + change over a single trailing window of `days`.
    `tag` is the human label to show (e.g. '14d', '6m')."""
    df = _load_csv(instrument.get("file", command))
    fmt, decimals, multi_row, label, mode = _resolve(instrument, command)
    cols = _value_columns(df, instrument.get("cols"))

    if multi_row:
        lines = [f"[{label}] {tag}"]
        for col in cols:
            n = _period_numbers(df, col, days, cols, mode)
            if n is None:
                continue
            v = fmt["value"](n["current"], decimals)
            d = fmt["delta"](n["delta"], n["base"], decimals)
            lines.append(f"{_tenor_label(col)}: {v} | Δ: {d}")
        if len(lines) == 1:
            lines.append("no data in range")
        return "\n".join(lines)

    if not cols:
        return f"[{label}] {tag} no data"
    n = _period_numbers(df, cols[0], days, cols, mode)
    if n is None:
        return f"[{label}] {tag} no data"
    v = fmt["value"](n["current"], decimals)
    d = fmt["delta"](n["delta"], n["base"], decimals)
    return f"[{label}] {tag} {v} | Δ: {d}"


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------
def snapshot_group(members, instruments) -> str:
    out = []
    for m in members:
        inst = instruments.get(m)
        if not inst:
            out.append(f"[{m}] unknown instrument")
            continue
        try:
            out.append(snapshot(m, inst))
        except FileNotFoundError:
            out.append(f"[{inst.get('label', m)}] file missing")
        except Exception as e:  # noqa: BLE001
            out.append(f"[{inst.get('label', m)}] error: {e}")
    return "\n".join(out)


def spec_group(members, instruments, start_date, end_date) -> str:
    out = []
    for m in members:
        inst = instruments.get(m)
        if not inst:
            out.append(f"[{m}] unknown instrument")
            continue
        try:
            out.append(spec(m, inst, start_date, end_date))
        except FileNotFoundError:
            out.append(f"[{inst.get('label', m)}] file missing")
        except Exception as e:  # noqa: BLE001
            out.append(f"[{inst.get('label', m)}] error: {e}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Unified dispatch (argument grammar lives in research/args.py)
# ---------------------------------------------------------------------------
from research.args import parse_query_args, parse_period  # noqa: E402


def query(command: str, instrument: dict, args: list[str]) -> str:
    """Single entry point for an instrument command + its arguments.
    Grammar is parsed by research.args.parse_query_args; this just dispatches.

    args == []                       -> default snapshot (1d/1w/1mo/1y)
    args == ['6m'] or ['14']         -> trailing-period change
    args == ['20260115','20260216']  -> date range (space form)
    args == ['20260115-20260216']    -> date range (dash form)
    """
    kind, payload = parse_query_args(args)
    if kind == "snapshot":
        return snapshot(command, instrument)
    if kind == "period":
        days, tag = payload
        return period(command, instrument, days, tag)
    if kind == "range":
        s, e = payload
        return spec(command, instrument, s, e)
    raise ValueError("사용법: /명령 | /명령 6m | /명령 20260115 20260216")


def query_group(members, instruments, args: list[str]) -> str:
    out = []
    for m in members:
        inst = instruments.get(m)
        if not inst:
            out.append(f"[{m}] unknown instrument")
            continue
        try:
            out.append(query(m, inst, args))
        except FileNotFoundError:
            out.append(f"[{inst.get('label', m)}] file missing")
        except ValueError as e:
            out.append(str(e))
        except Exception as e:  # noqa: BLE001
            out.append(f"[{inst.get('label', m)}] error: {e}")
    return "\n".join(out)