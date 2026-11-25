"""
config/spreads.py  —  THE list of spreads /spread reports.

A spread is one number a desk actually watches: credit over govt, a curve
slope, a cross-market gap. Each entry names two legs; the spread is
`long - short` in basis points.

A leg is (book_key, column_selector):
  book_key  the processed CSV, i.e. a key from config/sheet_keys.py
  selector  substring of the column name. If it matches SEVERAL columns they
            are averaged — that is how a sector spread works: '_val_8' picks
            the 3Y column of every card issuer, and the mean is the sector.

Legs may come from different books with different calendars: the engine as-of
joins them (analysis/align.py), so a monthly macro leg against a daily market
leg is fine and never looks ahead.

TO ADD A SPREAD: one line here. Nothing else changes.
"""

# Credit tenor positions, mirroring config/instruments.py:
#   capital _val_1..4 = 3M 1Y 2Y 3Y      card _val_1..8 = 3M 6M 9M 1Y 1.5Y 2Y 2.5Y 3Y
SPREADS = {
    # --- credit over govt --------------------------------------------------
    "card_3y": {
        "label": "카드채(평균) 3Y - 국고 3Y",
        "long":  ("kr_card", "_val_8"),
        "short": ("kr_govt", "(3년)"),
    },
    "card_1y": {
        "label": "카드채(평균) 1Y - 국고 1Y",
        "long":  ("kr_card", "_val_4"),
        "short": ("kr_govt", "(1년)"),
    },
    "cap_3y": {
        "label": "캐피탈(평균) 3Y - 국고 3Y",
        "long":  ("kr_capital", "_val_4"),
        "short": ("kr_govt", "(3년)"),
    },
    "cap_1y": {
        "label": "캐피탈(평균) 1Y - 국고 1Y",
        "long":  ("kr_capital", "_val_2"),
        "short": ("kr_govt", "(1년)"),
    },
    "cap_card_3y": {
        "label": "캐피탈 - 카드 3Y (업종간)",
        "long":  ("kr_capital", "_val_4"),
        "short": ("kr_card", "_val_8"),
    },

    # --- curve slopes ------------------------------------------------------
    "kr_3_10": {
        "label": "국고 10Y - 3Y",
        "long":  ("kr_govt", "(10년)"),
        "short": ("kr_govt", "(3년)"),
    },
    "kr_10_30": {
        "label": "국고 30Y - 10Y",
        "long":  ("kr_govt", "(30년)"),
        "short": ("kr_govt", "(10년)"),
    },
    "us_2_10": {
        "label": "UST 10Y - 2Y",
        "long":  ("us_govt", "10년"),
        "short": ("us_govt", "2년"),
    },

    # --- cross-market ------------------------------------------------------
    "kr_us_10y": {
        "label": "국고 10Y - UST 10Y",
        "long":  ("kr_govt", "(10년)"),
        "short": ("us_govt", "10년"),
    },
    "kr_us_2y": {
        "label": "국고 2Y - UST 2Y",
        "long":  ("kr_govt", "(2년)"),
        "short": ("us_govt", "2년"),
    },

    # --- funding -----------------------------------------------------------
    "govt1y_kofr": {
        "label": "국고 1Y - KOFR O/N",
        "long":  ("kr_govt", "(1년)"),
        "short": ("kofr", "KOFR금리"),
    },
}

# Shown first by /spread, because they are the desk's standing questions.
HEADLINE = ["card_3y", "cap_3y", "kr_3_10", "kr_us_10y", "govt1y_kofr"]
