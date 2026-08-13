"""
storage/loader.py

The single place that reads processed CSVs into clean pandas objects. Both the
research engine and the analysis layer go through here, so file-format details
(encoding, date parsing, sort order, NaN handling) live in ONE spot.

Two data categories, deliberately separated:
  MARKET  (databook_processed/)      daily-ish, one row per date, '일자' column
  MACRO   (databook_macro/)          central-bank/static data: monthly/quarterly,
                                       released with lags, revised. Same on-disk
                                       shape, different folder + semantics so the
                                       two never silently co-mingle.

The loader returns tidy frames; alignment across frequencies (daily market vs
monthly macro) is the caller's job via as-of joins (see analysis/align.py).
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

MARKET_DIR = Path(os.getenv("PROCESSED_DIR", r"C:\Users\User\databook_processed"))
MACRO_DIR = Path(os.getenv("MACRO_DIR", r"C:\Users\User\databook_macro"))

DATE_COL = "일자"
_ENCODINGS = ("utf-8-sig", "cp949", "euc-kr", "utf-8", "cp1252")


def _read(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"data file not found: {path}")
    last = None
    for enc in _ENCODINGS:
        try:
            df = pd.read_csv(path, encoding=enc)
            break
        except (UnicodeDecodeError, UnicodeError) as e:
            last = e
    else:
        raise UnicodeError(f"could not decode {path}: {last}")
    if DATE_COL not in df.columns:
        raise ValueError(f"'{DATE_COL}' missing in {path.name}")
    df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
    df = df.dropna(subset=[DATE_COL]).sort_values(DATE_COL, ascending=False)
    return df.reset_index(drop=True)


def load_market(key: str) -> pd.DataFrame:
    """Load a market databook by canonical key -> DataFrame, latest row first."""
    return _read(MARKET_DIR / f"{key}.csv")


def load_macro(key: str) -> pd.DataFrame:
    """Load a macro/central-bank series by key from the macro folder."""
    return _read(MACRO_DIR / f"{key}.csv")


def load(key: str, category: str = "market") -> pd.DataFrame:
    if category == "macro":
        return load_macro(key)
    return load_market(key)


def series(df: pd.DataFrame, col: str) -> pd.Series:
    """Return a clean, date-indexed, ascending Series for one column.
    Drops NaNs. This is the shape analysis functions want."""
    s = df[[DATE_COL, col]].dropna(subset=[col]).copy()
    s = s.sort_values(DATE_COL).set_index(DATE_COL)[col]
    s.name = col
    return s


def value_columns(df: pd.DataFrame, whitelist=None) -> list[str]:
    cols = [c for c in df.columns if c != DATE_COL]
    if whitelist:
        return [c for c in whitelist if c in cols]
    return cols