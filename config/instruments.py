"""
config/instruments.py  —  research command registry.

With canonical-key naming (config/sheet_keys.py), the processor guarantees each
dataset is saved as '<key>.csv'. So a research command named after that key needs
NO 'file' field — the engine defaults the filename to the command name.

You only add a 'file' field when the command name must differ from the filename:
one book holding several series (futures books hold one per currency/index) gives
one command per series, each a 'cols' slice of the same file.

Fields (all optional except style):
  style     required. "rates" | "fx" | "index" | "points" (research/formatters.py)
  label     bracket header; defaults to the command name
  file      filename WITHOUT .csv; defaults to the command name (leave out normally)
  decimals  display precision; per-style default otherwise
  cols      which raw columns to show. An entry is an exact column name, or a
            SUBSTRING matching several — use the substring form when upstream
            bakes a rolling contract code into the header ('SP 2608-2609'),
            so the next roll doesn't silently empty the command.
  labels    column -> display name. Keys may be the '_val_N' suffix alone, which
            is how a futures book names its three positional columns.
  multi_row override; per-style default otherwise
  curve     may '/<cmd>_plot' be registered? Defaults to multi_row. Set False for
            a multi-row book with no tenor axis (futures: 현재가/베이시스/이론).
"""

# A futures sheet repeats the same three columns per series, and the processor
# keeps them positionally (_val_1..3). One map names them for every such book.
FUTURES_LABELS = {
    "_val_1": "현재가",
    "_val_2": "시장베이시스",
    "_val_3": "이론베이시스",
}
FUTURES = {"style": "points", "labels": FUTURES_LABELS, "curve": False}

# Credit books hold issuer x tenor. The processor keeps tenors positionally
# (_val_N) because they live in the Excel sub-header row, so name them here.
# Source: row 1 of kr_capital_type1 / kr_card_type2.
CAPITAL_TENORS = {"_val_1": "3M", "_val_2": "1Y", "_val_3": "2Y", "_val_4": "3Y"}
CARD_TENORS = {"_val_1": "3M", "_val_2": "6M", "_val_3": "9M", "_val_4": "1Y",
               "_val_5": "1.5Y", "_val_6": "2Y", "_val_7": "2.5Y", "_val_8": "3Y"}

# kospi book sub-headers (row 1): price, then buy/sell value per investor type.
# Net flow = buy - sell, which is what research/commands/sectors.py reports.
EQUITY_LABELS = {
    "_val_1": "현재가",
    "_val_2": "기관매도", "_val_3": "기관매수",
    "_val_4": "외국인매도", "_val_5": "외국인매수",
    "_val_6": "개인매도", "_val_7": "개인매수",
}
EQUITY_FLOWS = {   # display name -> (sell suffix, buy suffix)
    "기관": ("_val_2", "_val_3"),
    "외국인": ("_val_4", "_val_5"),
    "개인": ("_val_6", "_val_7"),
}

INSTRUMENTS = {
    # command    : { config }        # reads <command>.csv by convention
    "kr_govt":  {"style": "rates", "label": "국고채"},
    "us_govt":  {"style": "rates", "label": "UST"},
    "ktb":      {"style": "points"},   # KTB futures price, multi-tenor, points only
    "ktb_theo": {"style": "points", "label": "KTB 이론가"},
    "kofr":     {"style": "rates", "label": "KOFR", "decimals": 3, "curve": False,
                 "labels": {"한국:KOFR금리(KOREA OVERNIGHT FINANCING REPO RATE)_val_1": "O/N",
                            "한국:KOFR 평균 금리(30일)_val_1": "30D",
                            "한국:KOFR 평균 금리(90일)_val_1": "90D",
                            "한국:KOFR 평균 금리(180일)_val_1": "180D",
                            "한국:KOFR INDEX_val_1": "INDEX"}},

    # --- FX futures: one book (fx_fut.csv), one command per currency --------
    # NOT spot FX. These are the KRX currency-futures calendar spreads, so the
    # numbers are swap points (-0.9, 5.7), not levels (1470).
    "fx_usd": {**FUTURES, "label": "미국달러 SP", "file": "fx_fut", "cols": ["미국달러"]},
    "fx_eur": {**FUTURES, "label": "유로 SP",     "file": "fx_fut", "cols": ["유로"]},
    "fx_jpy": {**FUTURES, "label": "엔 SP",       "file": "fx_fut", "cols": ["엔 "]},
    "fx_cny": {**FUTURES, "label": "위안 SP",     "file": "fx_fut", "cols": ["위안"]},

    # --- credit curves: one command per issuer, sliced out of one book -----
    "cap_hyundai": {"style": "rates", "label": "현대캐피탈", "file": "kr_capital",
                    "cols": ["현대캐피탈"], "labels": CAPITAL_TENORS},
    "cap_ibk":     {"style": "rates", "label": "IBK캐피탈", "file": "kr_capital",
                    "cols": ["아이비케이캐피탈"], "labels": CAPITAL_TENORS},
    "cap_shinhan": {"style": "rates", "label": "신한캐피탈", "file": "kr_capital",
                    "cols": ["신한캐피탈"], "labels": CAPITAL_TENORS},
    "cap_meritz":  {"style": "rates", "label": "메리츠캐피탈", "file": "kr_capital",
                    "cols": ["메리츠캐피탈"], "labels": CAPITAL_TENORS},
    "card_samsung": {"style": "rates", "label": "삼성카드", "file": "kr_card",
                     "cols": ["삼성카드"], "labels": CARD_TENORS},
    "card_shinhan": {"style": "rates", "label": "신한카드", "file": "kr_card",
                     "cols": ["신한카드"], "labels": CARD_TENORS},
    "card_hyundai": {"style": "rates", "label": "현대카드", "file": "kr_card",
                     "cols": ["현대카드"], "labels": CARD_TENORS},
    "card_bc":      {"style": "rates", "label": "비씨카드", "file": "kr_card",
                     "cols": ["비씨카드"], "labels": CARD_TENORS},

    # --- macro: monthly releases carried forward on a daily index ---------
    "cpi":      {"style": "index", "label": "한국 CPI", "multi_row": True,
                 "curve": False, "decimals": 1,
                 "labels": {"한국:CPI(YOY)_val_1": "YoY",
                            "한국:CPI(MOM)_val_1": "MoM",
                            "한국:근원CPI(YOY)_val_1": "근원 YoY",
                            "한국:근원CPI(MOM)_val_1": "근원 MoM"}},
    "ind_prod": {"style": "index", "label": "한국 생산", "multi_row": True,
                 "curve": False, "decimals": 1,
                 "labels": {"한국:전산업생산(YOY)_val_1": "전산업 YoY",
                            "한국:광공업생산(YOY)_val_1": "광공업 YoY",
                            "한국:서비스업생산(YOY)_val_1": "서비스 YoY",
                            "한국:전산업생산(MOM)_val_1": "전산업 MoM",
                            "한국:광공업생산(MOM)_val_1": "광공업 MoM",
                            "한국:서비스업생산(MOM)_val_1": "서비스 MoM"}},

}

# Outside fixed income, so no commands are generated for these. The books are
# still mapped in config/sheet_keys.py and still rebuilt on every /update, so
# the history keeps accruing — move an entry up into INSTRUMENTS (and, for the
# equity book, re-add the sectors CommandKind in research/registry.py) when
# commodities or sector data is actually needed, e.g. for a CPI or net-export
# forecast. research/commands/sectors.py is kept for that.
DORMANT = {
    "gold":       {**FUTURES, "label": "금 선물"},
    "kospi_fut":  {**FUTURES, "label": "코스피200 선물",
                   "file": "kr_equity_fut", "cols": ["코스피200"]},
    "kosdaq_fut": {**FUTURES, "label": "코스닥150 선물",
                   "file": "kr_equity_fut", "cols": ["코스닥150"]},
    "kospi":      {"style": "index", "label": "KOSPI", "cols": ["KOSPI_val_1"],
                   "curve": False, "labels": EQUITY_LABELS},
}

GROUPS = {
    "fx":      ["fx_usd", "fx_eur", "fx_jpy", "fx_cny"],
    "govt":    ["kr_govt", "us_govt"],
    "capital": ["cap_hyundai", "cap_ibk", "cap_shinhan", "cap_meritz"],
    "card":    ["card_samsung", "card_shinhan", "card_hyundai", "card_bc"],
    "macro":   ["cpi", "ind_prod"],
}
