"""
research/columns.py

Column-name helpers shared by every research command (one copy, not three).

Processed CSV columns look like '금투협 최종호가 국고채권(10년)_val_1'.
  tenor_num('...(10년)_val_1')   -> 10
  tenor_label('...(10년)_val_1') -> '10Y'
  tenor_label('KOSPI_val_1')     -> 'KOSPI'   (no tenor: strip the _val_N suffix)
"""

from __future__ import annotations

import re

from storage.loader import DATE_COL, value_columns  # noqa: F401  (re-exported)

TENOR_RE = re.compile(r"(\d+)\s*년")
_VAL_SUFFIX_RE = re.compile(r"_val_\d+$")


def tenor_num(col: str) -> int:
    """Tenor in years, or 0 if the column has no '(N년)'."""
    m = TENOR_RE.search(col)
    return int(m.group(1)) if m else 0


def tenor_label(col: str, strip_suffix: bool = True) -> str:
    """'10Y' for tenor columns. Otherwise the column name, minus '_val_N'
    unless strip_suffix=False (plot legend keeps the raw name)."""
    m = TENOR_RE.search(col)
    if m:
        return f"{int(m.group(1))}Y"
    return _VAL_SUFFIX_RE.sub("", col) if strip_suffix else col
