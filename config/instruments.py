"""
config/instruments.py  —  research command registry.

With canonical-key naming (config/sheet_keys.py), the processor guarantees each
dataset is saved as '<key>.csv'. So a research command named after that key needs
NO 'file' field — the engine defaults the filename to the command name.

You only add a 'file' field in the rare case where the command name must differ
from the filename (e.g. two commands reading one file with different column sets).

Fields (all optional except style):
  style     required. "rates" | "fx" | "index" (see research/formatters.py)
  label     bracket header; defaults to the command name
  file      filename WITHOUT .csv; defaults to the command name (leave out normally)
  decimals  display precision; per-style default otherwise
  cols      whitelist of raw column names to show; None = all
  multi_row override; per-style default otherwise
"""

INSTRUMENTS = {
    # command    : { config }        # reads <command>.csv by convention
    "kr_govt":  {"style": "rates"},
    "ktb":      {"style": "points"},   # KTB futures price, multi-tenor, points only
    "usdkrw":   {"style": "fx"},
    "usdjpy":   {"style": "fx"},

    # --- only when command name must differ from filename ---------------
    # "kr_govt_short": {"style": "rates", "file": "kr_govt",
    #                   "cols": ["금투협 최종호가 국고채권(1년)_val_1"]},
}

GROUPS = {
    "fx": ["usdkrw", "usdjpy"],
}