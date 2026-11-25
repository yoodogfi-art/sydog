"""
research/style.py  —  one chart look for every PNG the bot sends.

Charts used to be styled inline in plot.py, so a second chart module meant a
second palette. Colours, fonts and axis furniture live here instead; a new chart
command imports `apply_axes` and gets the house style for free.

Deep green leads, then a graded set that stays distinguishable in greyscale and
for red/green colour blindness.
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # headless: no display on the server
import matplotlib.pyplot as plt
from matplotlib import font_manager

DEEP_GREEN = "#15443A"
SERIES_COLORS = [
    "#15443A",  # deep green
    "#3EBE91",  # mint
    "#F0922B",  # amber
    "#6E8BA8",  # slate blue
    "#C4574B",  # clay
    "#8E7CC3",  # violet
    "#A8A632",  # olive
    "#4D4D4D",  # graphite
]
# Newest-to-oldest fade, for curve snapshots where all lines are one series.
GREEN_FADE = ["#0B6E4F", "#2E9E6B", "#66C08A", "#A9D9B8", "#CDE8D5"]

GRID = "#D8DED9"
TEXT = "#2B2B2B"
FACE = "#FAFBFA"

# Korean labels render as tofu boxes under the default font.
_KR_FONTS = ["Malgun Gothic", "NanumGothic", "NanumSquare", "AppleGothic", "Gulim"]


def _pick_font() -> str | None:
    have = {f.name for f in font_manager.fontManager.ttflist}
    return next((f for f in _KR_FONTS if f in have), None)


_FONT = _pick_font()


def color(i: int) -> str:
    return SERIES_COLORS[i % len(SERIES_COLORS)]


def new_fig(figsize=(9, 5), dpi=130):
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    fig.patch.set_facecolor(FACE)
    ax.set_facecolor(FACE)
    return fig, ax


def apply_axes(ax, title: str = "", ylabel: str = "", legend: bool = True,
               decimals: int = 2, value_axis: str | None = "y"):
    """House style for one axes.

    value_axis names the axis holding NUMBERS, so it gets the thousands/decimals
    formatter. On a horizontal bar chart that is "x" and the y axis holds
    category names — formatting those would replace them with their positions.
    Pass None to format neither.
    """
    if _FONT:
        for t in ([ax.title, ax.xaxis.label, ax.yaxis.label]
                  + ax.get_xticklabels() + ax.get_yticklabels()):
            t.set_fontname(_FONT)
    if title:
        ax.set_title(title, fontsize=13, fontweight="bold", color=TEXT, pad=12,
                     **({"fontname": _FONT} if _FONT else {}))
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10, color=TEXT)
    ax.grid(True, color=GRID, linewidth=0.8, alpha=0.9)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=TEXT, labelsize=9, length=0)
    if value_axis in ("x", "y"):
        fmt = plt.FuncFormatter(lambda v, _: f"{v:,.{decimals}f}")
        getattr(ax, f"{value_axis}axis").set_major_formatter(fmt)
    if legend and ax.get_legend_handles_labels()[0]:
        leg = ax.legend(frameon=False, fontsize=9, loc="best")
        if _FONT:
            for t in leg.get_texts():
                t.set_fontname(_FONT)


def to_png(fig) -> bytes:
    import io
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()
