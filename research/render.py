"""
research/render.py

The ONE place that turns per-column numbers into a Telegram text reply.
Every value-style command (snapshot, period, range, zscore, ...) calls
render_book() with two small functions:

  numbers_fn(df, col, cols, mode) -> dict | None     what to compute per column
  line_fn(book, head, nums)       -> str             how to show one column

render_book handles the rest: loading the CSV, style/decimals/label config,
multi-row (one line per tenor) vs single headline value, and empty messages.
"""

from __future__ import annotations

from dataclasses import dataclass

from research import calendar as cal
from research.columns import DATE_COL, column_label, value_columns
from research.formatters import get_style
from storage.loader import load_market


@dataclass
class Book:
    """Everything a command needs about one instrument, resolved once."""
    command: str
    label: str
    fmt: dict          # formatter entry from research/formatters.py
    decimals: int
    multi_row: bool
    mode: str          # calendar date_mode
    df: object         # pandas DataFrame, newest row first
    cols: list
    labels: dict       # column -> display name (see research/columns.column_label)

    def label_for(self, col: str) -> str:
        return column_label(col, self.labels)

    def value(self, v) -> str:
        return self.fmt["value"](v, self.decimals)

    def delta(self, d, base) -> str:
        return self.fmt["delta"](d, base, self.decimals)

    @staticmethod
    def head(tenor, value_str) -> str:
        return f"{tenor}: {value_str}" if tenor else value_str


def resolve_settings(command: str, instrument: dict) -> dict:
    """Instrument config merged with its style defaults (no file access)."""
    fmt = get_style(instrument["style"])
    return {
        "fmt": fmt,
        "decimals": instrument.get("decimals", fmt["decimals"]),
        "multi_row": instrument.get("multi_row", fmt["multi_row"]),
        "label": instrument.get("label", command),
        "mode": instrument.get("date_mode", cal.DEFAULT_MODE),
        "labels": instrument.get("labels") or {},
    }


def load_book(command: str, instrument: dict) -> Book:
    df = load_market(instrument.get("file", command))
    s = resolve_settings(command, instrument)
    return Book(command=command, df=df, cols=value_columns(df, instrument.get("cols")), **s)


def _as_of(book: Book) -> str | None:
    """'as of 2026-11-10': the newest date that has real values."""
    pos = cal._first_real_pos(book.df, book.cols)
    return None if pos is None else f"as of {book.df.iloc[pos][DATE_COL]:%Y-%m-%d}"


def render_book(command, instrument, numbers_fn, line_fn, tag=None,
                multi_empty="no data", single_empty="no data", show_asof=False) -> str:
    book = load_book(command, instrument)
    parts = [f"[{book.label}]", tag, _as_of(book) if show_asof else None]
    header = " ".join(p for p in parts if p)

    if book.multi_row:
        lines = [header]
        for col in book.cols:
            nums = numbers_fn(book.df, col, book.cols, book.mode)
            if nums is None:
                continue
            lines.append(line_fn(book, book.label_for(col), nums))
        if len(lines) == 1:
            lines.append(multi_empty)
        return "\n".join(lines)

    # single headline value: first column only
    if not book.cols:
        return f"{header} no data"
    nums = numbers_fn(book.df, book.cols[0], book.cols, book.mode)
    if nums is None:
        return f"{header} {single_empty}"
    return f"{header} " + line_fn(book, None, nums)
