"""
config/sheet_keys.py  —  THE ONE PLACE messy upstream names become clean keys.

WHY THIS FILE EXISTS
--------------------
Every API provider gives you Excel files with sheet names you don't control:
'국고채', 'USDKRW 최종호가', 'US Treasury Curve', 'JGB Yields (Bloomberg)', ...
Those names are chaos and they change without warning.

Instead of teaching every downstream tool (the research bot, future analytics)
to understand each messy name, you translate ONCE, here, into a canonical key.
After the processor runs, the messy names are gone: every output file is
'<key>.csv' and every research command is '/<key>'.

HOW TO USE
----------
Add one line per dataset:  "<exact sheet name>": "<canonical_key>"

  - LEFT  side = the sheet name EXACTLY as it appears in the Excel file
                 (copy-paste it; spaces, Korean, parentheses and all).
  - RIGHT side = your clean key: lowercase, ascii, underscores, no spaces.
                 This becomes the filename (kr_govt.csv) AND the Telegram
                 command (/kr_govt). Pick it once, use it everywhere.

If a sheet is NOT in this map, the processor falls back to a slugified version
of the sheet name AND prints a warning, so a newly-added sheet is never silently
lost — you just see the warning and add a proper line here.
"""

# 그냥 시트명으로 저장해도 되는데 텔레그램에서 명령어로 짧게 칠거면 키를 등록하는게 나아서 이렇게 사용. 여기에만 입력하면 됨
SHEET_TO_KEY = {
    # exact sheet name (from Excel)      : canonical key (file + command)
    "kr_govt_rates_databook":            "kr_govt",
    "ktb_futues_market":                   "ktb",
    "ktb_futures_theoretical": "ktb_theo",
    "kr_kofr_databook" : "kofr",
    "ktb" : "ktb",
    "ktb theo": "ktb_theo",
    "kr_macro_cpi_databook" : "cpi",
    "kr_macro_industrial_databook" : "ind_prod",

    # futures books: one sheet holds several series side by side, so the key is
    # the BOOK and config/instruments.py slices it into one command per series.
    "world_fx_spreads_1m":               "fx_fut",        # KRX 통화선물 SP (not spot FX)
    "kr_equity_market_futures":          "kr_equity_fut",
    "gold_futures":                      "gold",

    # rate curves
    "us_govt_rates_databook":            "us_govt",       # UST 1M..30Y

    # credit: one sheet per issuer TYPE, columns are issuer x tenor
    "kr_capital_type1":                  "kr_capital",    # 11 캐피탈 x 4 tenors
    "kr_card_type2":                     "kr_card",       # 6 카드 x 8 tenors

    # equity: KOSPI + 28 sector indices
    "Sheet1":                            "kospi",
}


def key_for_sheet(sheet_name: str):
    """Return (canonical_key, matched: bool).

    matched=False means this sheet wasn't in the map; caller should fall back
    to a slug and warn. Matching is done on the stripped sheet name so trailing
    spaces in Excel don't cause misses.
    """
    cleaned = str(sheet_name).strip()
    if cleaned in SHEET_TO_KEY:
        return SHEET_TO_KEY[cleaned], True
    return _slugify(cleaned), False


def _slugify(name: str) -> str:
    """Fallback only: make an unmapped sheet name filesystem-safe.
    Not meant to produce pretty keys — just to avoid crashing and to make the
    warning's suggested filename usable until you add a real mapping."""
    return str(name).strip().replace(" ", "_")