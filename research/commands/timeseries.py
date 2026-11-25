"""
research/commands/timeseries.py  —  /<instrument>_ts [period] [cols...]

History through time, which the other chart command does not show: plot.py
draws a CURVE (x = tenor, one line per date), so nothing in the bot could draw
a plain line chart of a series over time.

  /kr_govt_ts              -> every tenor, last 1 year
  /kr_govt_ts 5y           -> every tenor, last 5 years
  /kr_govt_ts 3y 3Y 10Y    -> only the 3Y and 10Y lines
  /kospi_ts all            -> full history

Trailing arguments filter columns by their display label (case-insensitive), so
you ask for the same '3Y' / '현재가' the text commands print.
"""

from __future__ import annotations

import matplotlib.dates as mdates

from research import style as sty
from research.args import parse_period
from research.render import load_book

DEFAULT_WINDOW = "1y"
MAX_LINES = 8          # one per palette colour; more is unreadable on a phone
USAGE = "사용법: /명령_ts | /명령_ts 5y | /명령_ts 3y 3Y 10Y | /명령_ts all"


def _parse_args(args: list[str]):
    """-> (days|None, tag, wanted_labels). First token may be a period."""
    if not args:
        return (*parse_period(DEFAULT_WINDOW), [])
    head, rest = args[0], args[1:]
    if head.lower() == "all":
        return None, "all", rest
    try:
        days, tag = parse_period(head)
    except ValueError:
        # No period given: every token is a column filter.
        return (*parse_period(DEFAULT_WINDOW), args)
    return days, tag, rest


def _select(book, wanted: list[str]) -> list[str]:
    if not wanted:
        return book.cols[:MAX_LINES]
    want = {w.lower() for w in wanted}
    hit = [c for c in book.cols if book.label_for(c).lower() in want]
    if not hit:  # fall back to substring, so '국채' or 'kospi' also work
        hit = [c for c in book.cols
               if any(w in book.label_for(c).lower() or w in c.lower() for w in want)]
    if not hit:
        raise ValueError(
            f"[{book.label}] no column matches {wanted}. "
            f"available: {', '.join(book.label_for(c) for c in book.cols[:12])}")
    return hit[:MAX_LINES]


def run(command: str, instrument: dict, args: list[str]) -> tuple[bytes, str]:
    from datetime import timedelta
    from storage.loader import series

    days, tag, wanted = _parse_args(args)
    book = load_book(command, instrument)
    cols = _select(book, wanted)

    fig, ax = sty.new_fig()
    drawn = 0
    for i, col in enumerate(cols):
        s = series(book.df, col)
        if days is not None and len(s):
            s = s[s.index >= s.index[-1] - timedelta(days=days)]
        if len(s) < 2:
            continue
        ax.plot(s.index, s.values, linewidth=1.8, color=sty.color(i),
                label=book.label_for(col))
        drawn += 1

    if not drawn:
        raise ValueError(f"[{book.label}] not enough data in {tag}")

    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(
        mdates.AutoDateLocator(maxticks=7)))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=7))
    unit = "%" if instrument.get("style") == "rates" else ""
    sty.apply_axes(ax, title=f"{book.label} — {tag}", ylabel=unit,
                   decimals=book.decimals)

    return sty.to_png(fig), f"[{book.label}] {tag} · {drawn}개 시리즈"
