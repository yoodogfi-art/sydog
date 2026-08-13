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

_TENOR_RE = re.compile(r"\((\d+)\s*년\)")


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
# Raw number computation (no formatting)
# ---------------------------------------------------------------------------
def _snapshot_numbers(df, col):
    """Return {current, d1, w1, y1, base_*} raw floats, or None if no data.
    base_* are the older reference values (for pct denominators)."""
    s = _series(df, col)
    if s.empty:
        return None
    cur_date = s.iloc[0][DATE_COL]
    cur_val = s.iloc[0][col]

    def bucket(days=None, prev=False):
        if prev:
            if len(s) < 2:
                return None, None
            old = s.iloc[1][col]
            return cur_val - old, old
        res = _asof_on_or_before(s.iloc[1:], cur_date - timedelta(days=days), col)
        if res is None:
            return None, None
        return cur_val - res[1], res[1]

    d1, d1b = bucket(prev=True)
    w1, w1b = bucket(days=7)
    m1, m1b = bucket(days=30)
    y1, y1b = bucket(days=365)
    return {
        "current": cur_val,
        "d1": d1, "d1_base": d1b,
        "w1": w1, "w1_base": w1b,
        "m1": m1, "m1_base": m1b,
        "y1": y1, "y1_base": y1b,
    }


def _period_numbers(df, col, days):
    """Current value + change over a single trailing window of `days`."""
    s = _series(df, col)
    if s.empty:
        return None
    cur_date = s.iloc[0][DATE_COL]
    cur_val = s.iloc[0][col]
    res = _asof_on_or_before(s.iloc[1:], cur_date - timedelta(days=days), col)
    if res is None:
        return {"current": cur_val, "delta": None, "base": None}
    return {"current": cur_val, "delta": cur_val - res[1], "base": res[1]}


def _spec_numbers(df, col, start_date, end_date):
    s = _series(df, col)
    if s.empty:
        return None
    end = _asof_on_or_before(s, end_date, col)
    start = _asof_on_or_before(s, start_date, col)
    if end is None or start is None:
        return None
    end_val = end[1]
    base = start[1]
    return {"current": end_val, "delta": end_val - base, "base": base}


# ---------------------------------------------------------------------------
# Rendering (uses the style formatter)
# ---------------------------------------------------------------------------
def _resolve(instrument: dict, command: str):
    style_name = instrument["style"]
    fmt = get_style(style_name)
    decimals = instrument.get("decimals", fmt["decimals"])
    multi_row = instrument.get("multi_row", fmt["multi_row"])
    label = instrument.get("label", command)
    return fmt, decimals, multi_row, label


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
    fmt, decimals, multi_row, label = _resolve(instrument, command)
    cols = _value_columns(df, instrument.get("cols"))

    if multi_row:
        lines = [f"[{label}]"]
        for col in cols:
            nums = _snapshot_numbers(df, col)
            if nums is None:
                continue
            lines.append(_snapshot_line(fmt, decimals, _tenor_label(col), nums))
        if len(lines) == 1:
            lines.append("no data")
        return "\n".join(lines)

    # single headline value
    if not cols:
        return f"[{label}] no data"
    nums = _snapshot_numbers(df, cols[0])
    if nums is None:
        return f"[{label}] no data"
    return f"[{label}] " + _snapshot_line(fmt, decimals, None, nums)


def spec(command: str, instrument: dict, start_date, end_date) -> str:
    df = _load_csv(instrument.get("file", command))
    fmt, decimals, multi_row, label = _resolve(instrument, command)
    cols = _value_columns(df, instrument.get("cols"))
    tag = f"{start_date:%Y%m%d}-{end_date:%Y%m%d}"

    if multi_row:
        lines = [f"[{label}] {tag}"]
        for col in cols:
            n = _spec_numbers(df, col, start_date, end_date)
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
    n = _spec_numbers(df, cols[0], start_date, end_date)
    if n is None:
        return f"[{label}] {tag} no data in range"
    v = fmt["value"](n["current"], decimals)
    d = fmt["delta"](n["delta"], n["base"], decimals)
    return f"[{label}] {tag} {v} | Δ: {d}"


def period(command: str, instrument: dict, days: int, tag: str) -> str:
    """Current value + change over a single trailing window of `days`.
    `tag` is the human label to show (e.g. '14d', '6m')."""
    df = _load_csv(instrument.get("file", command))
    fmt, decimals, multi_row, label = _resolve(instrument, command)
    cols = _value_columns(df, instrument.get("cols"))

    if multi_row:
        lines = [f"[{label}] {tag}"]
        for col in cols:
            n = _period_numbers(df, col, days)
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
    n = _period_numbers(df, cols[0], days)
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
# Argument parsing + unified dispatch
# ---------------------------------------------------------------------------
# One 8-digit date, or a period token like 14 / 6m / 2w / 1y.
_DATE_RE = re.compile(r"^\d{8}$")
_PERIOD_RE = re.compile(r"^(\d+)\s*([dwmy]?)$", re.IGNORECASE)

_UNIT_DAYS = {"d": 1, "w": 7, "m": 30, "y": 365}


def parse_period(token: str):
    """'14'->(14,'14d'), '6m'->(180,'6m'), '2w'->(14,'2w'), '1y'->(365,'1y').
    Bare number = days. Returns (days:int, tag:str). Raises ValueError."""
    m = _PERIOD_RE.match(token.strip())
    if not m:
        raise ValueError(f"기간 형식 오류: '{token}' (예: 14, 6m, 2w, 1y)")
    n = int(m.group(1))
    unit = (m.group(2) or "d").lower()
    days = n * _UNIT_DAYS[unit]
    tag = f"{n}{unit}" if unit != "d" else f"{n}d"
    return days, tag


def _parse_two_dates(a: str, b: str):
    start = pd.to_datetime(a, format="%Y%m%d")
    end = pd.to_datetime(b, format="%Y%m%d")
    if start > end:
        start, end = end, start
    return start, end


def query(command: str, instrument: dict, args: list[str]) -> str:
    """Single entry point for an instrument command + its arguments.

    args == []                       -> default snapshot (1d/1w/1mo/1y)
    args == ['6m'] or ['14']         -> trailing-period change
    args == ['20260115','20260216']  -> date range (space form)
    args == ['20260115-20260216']    -> date range (dash form)
    """
    # date range, dash form: single token with a dash
    if len(args) == 1 and "-" in args[0]:
        parts = args[0].split("-")
        if len(parts) == 2 and all(_DATE_RE.match(p.strip()) for p in parts):
            s, e = _parse_two_dates(parts[0].strip(), parts[1].strip())
            return spec(command, instrument, s, e)

    # date range, space form: two 8-digit tokens
    if len(args) == 2 and _DATE_RE.match(args[0]) and _DATE_RE.match(args[1]):
        s, e = _parse_two_dates(args[0], args[1])
        return spec(command, instrument, s, e)

    # single trailing period
    if len(args) == 1:
        days, tag = parse_period(args[0])
        return period(command, instrument, days, tag)

    # no args -> default snapshot
    if not args:
        return snapshot(command, instrument)

    raise ValueError(
        "사용법: /명령 (기본) | /명령 6m (기간) | /명령 20260115 20260216 (구간)"
    )


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