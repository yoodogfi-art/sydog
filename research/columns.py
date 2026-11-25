"""
research/columns.py

Column-name helpers shared by every research command (one copy, not three).

Processed CSV columns look like '금투협 최종호가 국고채권(10년)_val_1'.
  tenor_num('...(10년)_val_1')   -> 10
  tenor_label('...(10년)_val_1') -> '10Y'
  tenor_label('KOSPI_val_1')     -> 'KOSPI'   (no tenor: strip the _val_N suffix)

column_label() is what commands show. It exists because _val_N is positional:
in a futures book the three columns of one series are 현재가 / 시장베이시스 /
이론베이시스, and stripping the suffix would print the same label three times.
An instrument can name them (config/instruments.py 'labels').
"""

from __future__ import annotations

import re

from storage.loader import DATE_COL, value_columns  # noqa: F401  (re-exported)

TENOR_RE = re.compile(r"(\d+(?:\.\d+)?)\s*년")
MONTH_RE = re.compile(r"(\d+(?:\.\d+)?)\s*개?월")
_VAL_SUFFIX_RE = re.compile(r"_val_\d+$")


def tenor_num(col: str) -> int:
    """Tenor in years, or 0 if the column has no '(N년)'."""
    m = TENOR_RE.search(col)
    return int(m.group(1)) if m else 0


def _num(text: str) -> float | int:
    v = float(text)
    return int(v) if v.is_integer() else v


def tenor_label(col: str, strip_suffix: bool = True) -> str:
    """'10Y' / '3M' for tenor columns. Otherwise the column name, minus '_val_N'
    unless strip_suffix=False (plot legend keeps the raw name).

    Months matter because the US curve starts at 1개월: without them every
    sub-year point would print as its full Korean column name.
    """
    m = TENOR_RE.search(col)
    if m:
        return f"{_num(m.group(1))}Y"
    m = MONTH_RE.search(col)
    if m:
        return f"{_num(m.group(1))}M"
    return _VAL_SUFFIX_RE.sub("", col) if strip_suffix else col


def tenor_sort_key(col: str) -> float:
    """Tenor in years as a float, for ordering a curve's x-axis.

    tenor_num() stays integer-years because analysis/curve_fit.py builds coupon
    schedules from it; this one exists so 3개월 sorts before 1년 instead of
    collapsing to 0 with every other sub-year point.
    """
    m = TENOR_RE.search(col)
    if m:
        return float(m.group(1))
    m = MONTH_RE.search(col)
    if m:
        return float(m.group(1)) / 12.0
    return 0.0


def column_label(col: str, labels: dict | None = None) -> str:
    """Display label for one column, honouring an instrument's `labels` map.

    A labels key is either the full column name or just its '_val_N' suffix, so
    one map ({'_val_1': '현재가', ...}) serves every book with that layout and
    survives contract-code changes in the column name.
    """
    if labels:
        if col in labels:
            return labels[col]
        m = _VAL_SUFFIX_RE.search(col)
        if m and m.group(0) in labels:
            return labels[m.group(0)]
    return tenor_label(col)
