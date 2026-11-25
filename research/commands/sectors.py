"""
research/commands/sectors.py  —  /sectors [period] [flow|chart]

Which part of the market is working, and who is paying for it.

The kospi book holds KOSPI plus 28 sector and size indices, and for each one
the buy and sell value of institutions, foreigners and retail. Nothing read it
except the headline index, so the rotation question — what is outperforming,
and is it stretched — had no answer in the bot.

  /sectors              -> 1 month, ranked by return vs KOSPI
  /sectors 3m           -> same over 3 months
  /sectors 3m flow      -> ranked by foreign net buying instead
  /sectors 1y chart     -> horizontal bar chart of relative return

Each row: period return, relative to KOSPI in percentage points, z of the
sector/KOSPI RATIO (not the level — a rising tide lifts every level, the ratio
is what says 'stretched'), and net foreign buying as a share of that sector's
traded value.

Why a share and not an amount
-----------------------------
The flow columns are labelled 금액 but their scale does not survive a sanity
check: summed over a year the KOSPI 외국인 net comes to -356e6 book units,
which is an order of magnitude past any plausible annual foreign net whatever
the unit is. Either the scale is not what the header implies or 합매도/합매수
are not a matched pair. Until that is settled upstream, reporting a won figure
would be asserting something unverified, so this command reports

    net share = (buy - sell) / (buy + sell)

which is unit-free, self-normalising, and still answers "who is accumulating".
flow_amount() keeps the raw sum for whoever resolves the question.
"""

from __future__ import annotations

from datetime import timedelta

import matplotlib.pyplot as plt
import pandas as pd

from analysis.stats import percentile_rank, zscore
from config.instruments import EQUITY_FLOWS
from research import style as sty
from research.args import parse_period
from storage.loader import load_market, series, value_columns

BOOK = "kospi"
BENCH = "KOSPI"                       # the series everything is measured against
SIZE_BUCKETS = ("KOSPI 대형주", "KOSPI 중형주", "KOSPI 소형주")
DEFAULT_PERIOD = "1m"
Z_WINDOW_DAYS = 365                   # ratio z is always measured over 1y
MIN_Z_POINTS = 60
FLOW_UNIT = 1_000_000                 # raw-sum helper only; see the docstring
USAGE = "사용법: /sectors | /sectors 3m | /sectors 3m flow | /sectors 1y chart"


def _roots(df) -> list[str]:
    """Series names in the book, from the '<name>_val_1' price columns."""
    return [c[: -len("_val_1")] for c in value_columns(df) if c.endswith("_val_1")]


def _paired(df, root: str, sell: str, buy: str, start):
    """Sell/buy columns on a common index, windowed. None if either is absent."""
    cols = [f"{root}{sell}", f"{root}{buy}"]
    if not all(c in df.columns for c in cols):
        return None
    joined = pd.concat([series(df, cols[0]).rename("s"),
                        series(df, cols[1]).rename("b")], axis=1).dropna()
    if start is not None:
        joined = joined[joined.index >= start]
    return joined if len(joined) else None


def _net_flow(df, root: str, start) -> dict[str, float]:
    """Net buy as a share of traded value, per investor type, in %.

    (buy - sell) / (buy + sell) over the window. +10 means a tenth of this
    sector's turnover was that group accumulating.
    """
    out = {}
    for who, (sell, buy) in EQUITY_FLOWS.items():
        j = _paired(df, root, sell, buy, start)
        if j is None:
            continue
        gross = float(j["b"].sum() + j["s"].sum())
        if gross <= 0:
            continue
        out[who] = (float(j["b"].sum() - j["s"].sum()) / gross) * 100
    return out


def flow_amount(df, root: str, who: str, start) -> float | None:
    """Raw net sum in book units / FLOW_UNIT. Unused by the views on purpose —
    see the module docstring on why the amount is not reported."""
    sell, buy = EQUITY_FLOWS[who]
    j = _paired(df, root, sell, buy, start)
    if j is None:
        return None
    return float(j["b"].sum() - j["s"].sum()) / FLOW_UNIT


def _ret(s: pd.Series, start) -> float | None:
    """Simple return from the first observation at/after start, in %."""
    win = s if start is None else s[s.index >= start]
    if len(win) < 2 or win.iloc[0] == 0:
        return None
    return float(win.iloc[-1] / win.iloc[0] - 1) * 100


def rank(period: str = DEFAULT_PERIOD) -> tuple[list[dict], pd.Timestamp, str]:
    """(rows, as-of date, period tag). Rows carry everything the views need."""
    days, tag = (None, "all") if period.lower() == "all" else parse_period(period)
    df = load_market(BOOK)

    bench = series(df, f"{BENCH}_val_1")
    if bench.empty:
        raise ValueError(f"[{BENCH}] 데이터 없음")
    asof = bench.index[-1]
    start = None if days is None else asof - timedelta(days=days)
    bench_ret = _ret(bench, start)

    rows = []
    for root in _roots(df):
        if root == BENCH:
            continue
        px = series(df, f"{root}_val_1")
        r = _ret(px, start)
        if r is None:
            continue

        # Ratio z: how stretched is this sector against the market, over 1y.
        ratio = (px / bench.reindex(px.index).ffill()).dropna()
        zwin = ratio[ratio.index >= asof - timedelta(days=Z_WINDOW_DAYS)]
        if len(zwin) >= MIN_Z_POINTS and zwin.std() > 0:
            z, pct = float(zscore(zwin).iloc[-1]), percentile_rank(zwin)
        else:
            z = pct = None

        rows.append({
            "name": root.replace("코스피 ", ""),
            "size": root in SIZE_BUCKETS,
            "ret": r,
            "rel": None if bench_ret is None else r - bench_ret,
            "z": z, "pct": pct,
            "flow": _net_flow(df, root, start),
            "n": len(px if start is None else px[px.index >= start]),
        })
    return rows, asof, tag


# ---------------------------------------------------------------------------
# views
# ---------------------------------------------------------------------------
def _fmt(v, suffix="", decimals=1) -> str:
    return "  n/a" if v is None else f"{v:+.{decimals}f}{suffix}"


def _row_line(r: dict) -> str:
    z = "     " if r["z"] is None else f"z{r['z']:+.1f}"
    frn = r["flow"].get("외국인")
    f = "" if frn is None else f"  외{frn:+.1f}%"
    return f"  {r['name'][:9]:<10} {r['ret']:>+6.1f}% {_fmt(r['rel'],'pp'):>8} {z}{f}"


def _table(rows: list[dict], asof, tag: str, by_flow: bool) -> str:
    sectors = [r for r in rows if not r["size"]]
    if by_flow:
        sectors = [r for r in sectors if r["flow"].get("외국인") is not None]
        sectors.sort(key=lambda r: -r["flow"]["외국인"])
        head = "외국인 순매수 순"
    else:
        sectors.sort(key=lambda r: (r["rel"] is None, -(r["rel"] or 0)))
        head = "KOSPI 대비 순"

    out = [f"*[섹터 랭킹]* {tag} · {head}",
           f"as of {asof:%Y-%m-%d}  _수익률 / vs KOSPI / z(1y 비율) / 외국인 순매수비중_"]
    out += [_row_line(r) for r in sectors]

    size = [r for r in rows if r["size"]]
    if size:
        out.append("")
        out.append("*규모별*")
        out += [_row_line(r) for r in size]
    return "\n".join(out)


def _chart(rows: list[dict], asof, tag: str):
    sectors = [r for r in rows if not r["size"] and r["rel"] is not None]
    if not sectors:
        raise ValueError("차트에 쓸 섹터 데이터 없음")
    sectors.sort(key=lambda r: r["rel"])

    names = [r["name"] for r in sectors]
    vals = [r["rel"] for r in sectors]
    colors = [sty.SERIES_COLORS[0] if v >= 0 else sty.SERIES_COLORS[4] for v in vals]

    fig, ax = sty.new_fig(figsize=(8, max(4.5, 0.32 * len(names))))
    ax.barh(range(len(names)), vals, color=colors, height=0.72)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names)
    ax.axvline(0, color=sty.TEXT, linewidth=1.0)
    # value_axis=None: the y axis holds sector names, not numbers.
    sty.apply_axes(ax, title=f"KOSPI 대비 초과수익 — {tag} (as of {asof:%Y-%m-%d})",
                   ylabel="", legend=False, decimals=0, value_axis=None)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:+.0f}pp"))
    ax.grid(axis="y", visible=False)

    best, worst = sectors[-1], sectors[0]
    cap = (f"[섹터 {tag}] 최고 {best['name']} {best['rel']:+.1f}pp · "
           f"최저 {worst['name']} {worst['rel']:+.1f}pp")
    return sty.to_png(fig), cap


def run(command: str, instrument: dict, args: list[str]):
    """command/instrument unused: /sectors is a fixed-name command."""
    args = [a.lower() for a in args]
    want_chart = "chart" in args or "plot" in args
    by_flow = "flow" in args
    rest = [a for a in args if a not in ("chart", "plot", "flow")]
    if len(rest) > 1:
        raise ValueError(USAGE)

    rows, asof, tag = rank(rest[0] if rest else DEFAULT_PERIOD)
    if not rows:
        raise ValueError("섹터 데이터 없음")
    if want_chart:
        return _chart(rows, asof, tag)
    return _table(rows, asof, tag, by_flow)
