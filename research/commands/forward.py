"""
research/commands/forward.py  —  /forward [yyyymmdd]

Korean government curve (kr_govt.csv) fitted with four models.
Sends two Telegram messages:
  1. an album of 4 images: one fitted curve per model
  2. one image: the forward-rate matrix for TABLE_MODEL

/forward            -> latest date with data
/forward 20260115   -> latest data on or before that date

kr_govt.csv quotes yields by tenor, so each tenor is treated as a par bond
(coupon = yield, maturing exactly N years out). See analysis/curve_fit.py.
"""

from __future__ import annotations

import io

import matplotlib
matplotlib.use("Agg")  # headless, no display
import matplotlib.pyplot as plt
import pandas as pd

from analysis.curve_fit import MODELS, fit_curves, par_bond
from research import calendar as cal
from research.columns import DATE_COL, tenor_num
from research.render import load_book

TABLE_MODEL = "LINEAR"   # which model's forwards go in the table image
MIN_TENORS = 6           # NSS has 6 parameters
USAGE = "사용법: /forward | /forward 20260115"


def _pick_row(book, args):
    """The row to value the curve on: newest with data, on or before the date."""
    if len(args) > 1:
        raise ValueError(USAGE)
    df = book.df
    if args:
        try:
            target = pd.to_datetime(args[0], format="%Y%m%d")
        except ValueError:
            raise ValueError(USAGE) from None
        df = df[df[DATE_COL] <= target]
    pos = cal._first_real_pos(df, book.cols) if not df.empty else None
    if pos is None:
        raise ValueError(f"[{book.label}] no data on or before that date")
    return df.iloc[pos]


def _build_bonds(book, row):
    val = row[DATE_COL].date()
    points = sorted((tenor_num(c), float(row[c])) for c in book.cols
                    if tenor_num(c) > 0 and pd.notna(row[c]))
    if len(points) < MIN_TENORS:
        raise ValueError(f"[{book.label}] {val}: {len(points)} tenors, need {MIN_TENORS}")
    return val, [par_bond(t, y, val) for t, y in points]


def _png(fig, dpi=150) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _model_chart(bonds, model, rmse, val) -> bytes:
    fig, ax = plt.subplots(figsize=(11, 6))
    x = [b["mod_dur"] for b in bonds]
    ax.scatter(x, [b["yield_pct"] for b in bonds], s=28, color="0.45",
               label="Market yield", zorder=2)
    ax.plot(x, [b["fit"][model]["yield"] for b in bonds], lw=1.5, color="C3",
            label=f"{model} fitted yield", zorder=3)
    ax.set(xlabel="Modified Duration", ylabel="Yield (%)",
           title=f"KTB Yield Curve ({model})  |  {val:%Y-%m-%d}  |  RMSE {rmse:.2f} bp")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return _png(fig)


def _matrix_table(matrix, model, val) -> bytes:
    cells = [["" if pd.isna(v) else f"{v:.3f}" for v in row] for row in matrix.values]
    fig, ax = plt.subplots(figsize=(15, 0.33 * (len(matrix) + 1) + 1))
    ax.axis("off")
    ax.set_title(f"KTB forward matrix ({model}, s.a. %)  |  {val:%Y-%m-%d}  |  "
                 "rows: start, columns: end", fontsize=13)
    table = ax.table(cellText=cells, rowLabels=list(matrix.index),
                     colLabels=list(matrix.columns), loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.35)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#CFDBD4")
        if r == 0 or c == -1:   # header row and start-month column
            cell.set_facecolor("#0B6E4F")
            cell.set_text_props(color="white", fontweight="bold")
        elif r % 2 == 0:
            cell.set_facecolor("#F1F7F3")
    fig.tight_layout()
    return _png(fig, dpi=130)


def run(command: str, instrument: dict, args: list[str]) -> list:
    book = load_book(command, instrument)
    val, bonds = _build_bonds(book, _pick_row(book, args))
    fits = fit_curves(bonds, val)

    album = [
        (_model_chart(bonds, m, fits[m]["rmse"], val),
         f"{m} | {val:%Y-%m-%d} | RMSE {fits[m]['rmse']:.2f}bp, max {fits[m]['max_abs']:.2f}bp")
        for m in MODELS
    ]
    table = (_matrix_table(fits[TABLE_MODEL]["matrix"], TABLE_MODEL, val),
             f"KTB forwards ({TABLE_MODEL}) {val:%Y-%m-%d}\n"
             "1Y 미만 금리 데이터 없음: 1Y 이내 구간은 외삽값")
    return [album, table]
