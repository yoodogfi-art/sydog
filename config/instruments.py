"""
Instrument registry for the research query engine.

Each command the user can type on Telegram maps to an entry here.
Adding a new book later = add one dict entry. No engine changes needed.

style:
  "rates" -> values are yields in %, changes shown in bp   (e.g. 1d: +10bp)
  "fx"    -> values are levels,       changes shown in level + %  (e.g. 1d: -10 (-0.04%))

file:
  CSV filename (without extension) inside PROCESSED_DIR.

group:
  Optional. If present, this command is a *group* that prints several
  instruments stacked (e.g. "fx" -> usdkrw, usdjpy). group members are
  command keys that must also exist in INSTRUMENTS.
"""

INSTRUMENTS = {
    "kr_govt": {
        "file": "kr_govt",
        "style": "rates",
        "label": "kr_govt",
    },
    # --- FX examples; wire up once the processed CSVs exist ---
    "usdkrw": {
        "file": "usdkrw",
        "style": "fx",
        "label": "usdkrw",
    },
    "usdjpy": {
        "file": "usdjpy",
        "style": "fx",
        "label": "usdjpy",
    },
}

# Group commands: one command -> several instruments printed together.
GROUPS = {
    "fx": ["usdkrw", "usdjpy"],
}