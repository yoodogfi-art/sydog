"""
research/query_engine.py

Read-only research layer. Takes a processed databook CSV and answers:
  - snapshot:   current value + change over 1d / 1w / 1y
  - spec:       current value + change between two user-given dates

Design notes
------------
* Encoding is auto-detected (samples come in cp949; the processor writes
  utf-8-sig). Don't hardcode.
* Dates in the '일자' column are ISO strings ("2026-08-12"). We parse to
  datetime and sort descending so row 0 is the latest.
* The latest row can be entirely NaN (trailing empty). For every tenor we
  take the *last real* (non-NaN) observation as "current", and look back
  from that observation's date.
* "1d" = the immediately-preceding real observation for that tenor.
  "1w"/"1y" = the most recent observation on-or-before (current_date - N).
  If no row is far enough back, that bucket returns None -> printed as n/a.
* bp changes are computed as (new - old) * 100, rounded to nearest bp
  (yields are in %, so 1bp = 0.01%).
"""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

import pandas as pd

# ---- location of processed CSVs -------------------------------------------
# On the Windows box this is C:\Users\User\databook_processed (matches
# data_processor.py). Overridable via env for testing.
import os
PROCESSED_DIR = Path(os.getenv("PROCESSED_DIR", r"C:\Users\User\databook_processed"))

DATE_COL = "일자"
_ENCODINGS = ("utf-8-sig", "cp949", "euc-kr", "utf-8", "cp1252")


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def _load_csv(file_stem: str) -> pd.DataFrame:
    path = PROCESSED_DIR / f"{file_stem}.csv"
    if not path.exists():
        raise FileNotFoundError(f"processed file not found: {path}")

    last_err = None
    for enc in _ENCODINGS:
        try:
            df = pd.read_csv(path, encoding=enc)
            break
        except (UnicodeDecodeError, UnicodeError) as e:
            last_err = e
    else:
        raise UnicodeError(f"could not decode {path}: {last_err}")

    if DATE_COL not in df.columns:
        raise ValueError(f"'{DATE_COL}' column missing in {path.name}")

    df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
    df = df.dropna(subset=[DATE_COL])
    df = df.sort_values(DATE_COL, ascending=False).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Column -> tenor label
# ---------------------------------------------------------------------------
_TENOR_RE = re.compile(r"\((\d+)\s*년\)")  # e.g. "국고채권(10년)_val_1" -> 10

def _tenor_label(col: str) -> str:
    """Pull a clean tenor label out of a verbose column name.

    '금투협 최종호가 국고채권(10년)_val_1' -> '10Y'
    Falls back to the raw column (minus the _val_ suffix) if no (N년) found.
    """
    m = _TENOR_RE.search(col)
    if m:
        return f"{int(m.group(1))}Y"
    return re.sub(r"_val_\d+$", "", col)


def _value_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c != DATE_COL]


# ---------------------------------------------------------------------------
# Lookback helpers
# ---------------------------------------------------------------------------
def _series(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Return a 2-col frame [date, value] for one tenor, latest first,
    with NaN values dropped. Empty if the tenor has no data at all."""
    s = df[[DATE_COL, col]].dropna(subset=[col])
    return s.reset_index(drop=True)


def _asof_on_or_before(s: pd.DataFrame, target_date, col: str):
    """Most recent (date, value) at or before target_date. None if none."""
    older = s[s[DATE_COL] <= target_date]
    if older.empty:
        return None
    row = older.iloc[0]  # s is sorted latest-first
    return row[DATE_COL], row[col]


def _changes_for_col(df: pd.DataFrame, col: str) -> dict | None:
    """Compute current value and 1d/1w/1y deltas for one tenor.

    Returns dict{current, d1, w1, y1} where each delta is a raw float
    difference (new - old) or None if not resolvable. None (whole) if the
    tenor has no data.
    """
    s = _series(df, col)
    if s.empty:
        return None

    cur_date = s.iloc[0][DATE_COL]
    cur_val = s.iloc[0][col]

    # 1d = previous real observation
    d1 = None
    if len(s) > 1:
        d1 = cur_val - s.iloc[1][col]

    # 1w / 1y = as-of on or before cur_date - N, excluding the current point
    def _delta(days):
        res = _asof_on_or_before(s.iloc[1:], cur_date - timedelta(days=days), col)
        if res is None:
            return None
        return cur_val - res[1]

    w1 = _delta(7)
    y1 = _delta(365)

    return {"current": cur_val, "date": cur_date, "d1": d1, "w1": w1, "y1": y1}


def _spec_change(df: pd.DataFrame, col: str, start_date, end_date):
    """Value at end_date (asof) and change vs start_date (asof).
    Returns (end_val, end_date_actual, delta) or None."""
    s = _series(df, col)
    if s.empty:
        return None
    end = _asof_on_or_before(s, end_date, col)
    start = _asof_on_or_before(s, start_date, col)
    if end is None or start is None:
        return None
    return end[1], end[0], end[1] - start[1]


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
def _fmt_bp(delta) -> str:
    if delta is None:
        return "n/a"
    bp = round(delta * 100)
    return f"{bp:+d}bp"


def _fmt_fx(delta, base_val) -> str:
    """Level change + percent, e.g. '-10 (-0.04%)'. base_val is the
    reference (older) level for the pct denominator."""
    if delta is None or base_val is None:
        return "n/a"
    pct = (delta / base_val) * 100 if base_val else 0.0
    # level change: keep 2dp for fx, strip if whole-ish
    return f"{delta:+.2f} ({pct:+.2f}%)"


def _fmt_rates_line(label: str, ch: dict) -> str:
    return (f"{label}: {ch['current']:.2f}% | "
            f"1d: {_fmt_bp(ch['d1'])}, "
            f"1w: {_fmt_bp(ch['w1'])}, "
            f"1y: {_fmt_bp(ch['y1'])}")


def _fx_delta_and_base(df, col, s_row, days):
    """helper unused placeholder kept for clarity"""
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Public: snapshot (plain command)
# ---------------------------------------------------------------------------
def snapshot(command: str, instrument: dict) -> str:
    """Build the snapshot message for one instrument command."""
    df = _load_csv(instrument["file"])
    label = instrument.get("label", command)
    style = instrument["style"]
    cols = _value_columns(df)

    lines = [f"[{label}]"]

    if style == "rates":
        for col in cols:
            ch = _changes_for_col(df, col)
            if ch is None:
                continue
            lines.append(_fmt_rates_line(_tenor_label(col), ch))
        if len(lines) == 1:
            lines.append("no data")
        return "\n".join(lines)

    # fx: single value per file (first value column). Level + pct.
    col = cols[0]
    s = _series(df, col)
    if s.empty:
        return f"[{label}] no data"
    cur_val = s.iloc[0][col]

    def fx_bucket(days=None, prev_row=False):
        if prev_row:
            if len(s) < 2:
                return "n/a"
            old = s.iloc[1][col]
            return _fmt_fx(cur_val - old, old)
        res = _asof_on_or_before(s.iloc[1:], s.iloc[0][DATE_COL] - timedelta(days=days), col)
        if res is None:
            return "n/a"
        return _fmt_fx(cur_val - res[1], res[1])

    line = (f"[{label}] {cur_val:.2f} | "
            f"1d: {fx_bucket(prev_row=True)}, "
            f"1w: {fx_bucket(days=7)}, "
            f"1y: {fx_bucket(days=365)}")
    return line


# ---------------------------------------------------------------------------
# Public: spec (two-date range)
# ---------------------------------------------------------------------------
def spec(command: str, instrument: dict, start_date, end_date) -> str:
    df = _load_csv(instrument["file"])
    label = instrument.get("label", command)
    style = instrument["style"]
    cols = _value_columns(df)

    date_tag = f"{start_date:%Y%m%d}-{end_date:%Y%m%d}"
    lines = [f"[{label}] {date_tag}"]

    if style == "rates":
        for col in cols:
            r = _spec_change(df, col, start_date, end_date)
            if r is None:
                continue
            end_val, _, delta = r
            lines.append(f"{_tenor_label(col)}: {end_val:.2f}% | Δ: {_fmt_bp(delta)}")
        if len(lines) == 1:
            lines.append("no data in range")
        return "\n".join(lines)

    col = cols[0]
    r = _spec_change(df, col, start_date, end_date)
    if r is None:
        return f"[{label}] {date_tag} no data in range"
    end_val, _, delta = r
    # base for pct = start value = end_val - delta
    base = end_val - delta
    return f"[{label}] {date_tag} {end_val:.2f} | Δ: {_fmt_fx(delta, base)}"


# ---------------------------------------------------------------------------
# Public: group (e.g. fx -> several instruments)
# ---------------------------------------------------------------------------
def snapshot_group(members: list[str], instruments: dict) -> str:
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


# ---------------------------------------------------------------------------
# Date parsing for the _spec reply
# ---------------------------------------------------------------------------
_SPEC_RE = re.compile(r"^\s*(\d{8})\s*-\s*(\d{8})\s*$")

def parse_spec_range(text: str):
    """Parse 'yyyymmdd-yyyymmdd' -> (start_dt, end_dt). Raises ValueError."""
    m = _SPEC_RE.match(text)
    if not m:
        raise ValueError("format must be yyyymmdd-yyyymmdd, e.g. 20260115-20260216")
    start = pd.to_datetime(m.group(1), format="%Y%m%d")
    end = pd.to_datetime(m.group(2), format="%Y%m%d")
    if start > end:
        start, end = end, start
    return start, end