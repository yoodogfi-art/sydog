"""
research/commands/spread.py  —  /spread [name] [window]

The gap the bot was missing: every other command reports ONE book, but the
questions a credit desk asks are differences — credit over govt, 10s-3s, KR
over UST. The data was already there (kr_card, kr_capital, kr_govt, us_govt,
kofr); nothing joined it.

  /spread                 -> headline spreads, one line each
  /spread all             -> every spread in config/spreads.py
  /spread card_3y         -> one spread in detail, 1y z-score
  /spread card_3y 3y      -> same, 3y z-score window
  /spread card_3y chart   -> history chart of that spread

Legs may live in different books with different calendars (kofr starts 2018,
CPI is monthly), so the two legs are as-of joined — the short leg takes its
most recent value on-or-before each long-leg date. No lookahead.
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd

from analysis.align import asof_join
from analysis.stats import percentile_rank, zscore
from config.spreads import HEADLINE, SPREADS
from research import style as sty
from research.args import parse_period
from storage.loader import load_market, series, value_columns

DEFAULT_WINDOW = "1y"
USAGE = ("사용법: /spread | /spread all | /spread card_3y | "
         "/spread card_3y 3y | /spread card_3y chart\n"
         "등록된 스프레드: " + ", ".join(SPREADS))


def leg_series(leg: tuple[str, str]) -> pd.Series:
    """One side of a spread as a clean daily series.

    A selector matching several columns is averaged — that is the sector leg:
    '_val_8' is the 3Y column of every card issuer, so the mean is the card
    sector 3Y. Issuers with no quote on a date simply do not count that day.
    """
    key, selector = leg
    df = load_market(key)
    cols = value_columns(df, [selector])
    if not cols:
        raise ValueError(f"'{selector}' matches no column in {key}.csv")
    if len(cols) == 1:
        return series(df, cols[0])
    frame = pd.concat([series(df, c) for c in cols], axis=1)
    s = frame.mean(axis=1, skipna=True).dropna()
    s.name = f"{key}:{selector}"
    return s


def spread_series(name: str) -> tuple[pd.Series, dict]:
    """(spread in bp, spec). Long minus short, as-of joined on the long leg."""
    spec = SPREADS.get(name)
    if spec is None:
        raise ValueError(f"'{name}' 없음.\n{USAGE}")
    long_s = leg_series(spec["long"]).rename("long")
    short_s = leg_series(spec["short"]).rename("short")
    joined = asof_join(long_s, short_s).dropna()
    if joined.empty:
        raise ValueError(f"[{spec['label']}] 두 구간이 겹치지 않음")
    s = ((joined["long"] - joined["short"]) * 100).rename(name)   # % -> bp
    return s, spec


def _stats(s: pd.Series, days: int | None) -> dict:
    win = s if days is None else s[s.index >= s.index[-1] - timedelta(days=days)]
    out = {"last": float(s.iloc[-1]), "asof": s.index[-1], "n": len(win)}
    for label, d in (("d1", 1), ("w1", 7), ("m1", 30), ("y1", 365)):
        prior = s[s.index <= s.index[-1] - timedelta(days=d)]
        out[label] = float(s.iloc[-1] - prior.iloc[-1]) if len(prior) else None
    if len(win) >= 3 and win.std() > 0:
        out["z"] = float(zscore(win).iloc[-1])
        out["pct"] = percentile_rank(win)
    else:
        out["z"] = out["pct"] = None
    return out


def _chg(v) -> str:
    return "n/a" if v is None else f"{v:+.0f}"


def _line(name: str, spec: dict, st: dict) -> str:
    z = "z n/a" if st["z"] is None else f"z {st['z']:+.2f}, pct {st['pct']:.0f}%"
    return (f"{spec['label']}: {st['last']:.0f}bp | "
            f"1d {_chg(st['d1'])}, 1w {_chg(st['w1'])}, 1mo {_chg(st['m1'])} | {z}")


def _table(names: list[str], days: int | None, tag: str, title: str) -> str:
    lines = [f"[{title}] z-window {tag}"]
    asof = None
    for n in names:
        try:
            s, spec = spread_series(n)
            st = _stats(s, days)
            asof = max(asof, st["asof"]) if asof else st["asof"]
            lines.append(f"/{n}  " + _line(n, spec, st))
        except Exception as e:  # noqa: BLE001  one bad spread never hides the rest
            lines.append(f"/{n}  !! {e}")
    if asof is not None:
        lines.insert(1, f"as of {asof:%Y-%m-%d}  (단위 bp)")
    return "\n".join(lines)


def _chart(name: str, days: int | None, tag: str):
    s, spec = spread_series(name)
    win = s if days is None else s[s.index >= s.index[-1] - timedelta(days=days)]
    if len(win) < 2:
        raise ValueError(f"[{spec['label']}] {tag} 구간 데이터 부족")

    import matplotlib.dates as mdates
    fig, ax = sty.new_fig()
    ax.plot(win.index, win.values, linewidth=1.8, color=sty.color(0),
            label=spec["label"])
    mean = win.mean()
    ax.axhline(mean, color=sty.color(2), linewidth=1.1, linestyle="--",
               label=f"평균 {mean:.0f}bp")
    sd = win.std()
    if sd > 0:
        ax.fill_between(win.index, mean - sd, mean + sd,
                        color=sty.color(1), alpha=0.13, label="±1σ")
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=7))
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(
        mdates.AutoDateLocator(maxticks=7)))
    sty.apply_axes(ax, title=f"{spec['label']} — {tag}", ylabel="bp", decimals=0)
    st = _stats(s, days)
    z = "" if st["z"] is None else f" | z {st['z']:+.2f}, pct {st['pct']:.0f}%"
    return sty.to_png(fig), f"[{spec['label']}] {st['last']:.0f}bp{z}"


def run(command: str, instrument: dict, args: list[str]):
    """command/instrument are unused: /spread is a fixed-name command."""
    args = list(args)
    want_chart = False
    if args and args[-1].lower() in ("chart", "plot", "c"):
        want_chart = True
        args = args[:-1]

    if not args:
        return _table(HEADLINE, *parse_period(DEFAULT_WINDOW), "주요 스프레드")
    if args[0].lower() == "all":
        days, tag = parse_period(args[1]) if len(args) > 1 else parse_period(DEFAULT_WINDOW)
        return _table(list(SPREADS), days, tag, "전체 스프레드")

    name = args[0]
    if name not in SPREADS:
        raise ValueError(f"'{name}' 없음.\n{USAGE}")
    if len(args) > 1 and args[1].lower() == "all":
        days, tag = None, "all"
    elif len(args) > 1:
        days, tag = parse_period(args[1])
    else:
        days, tag = parse_period(DEFAULT_WINDOW)

    if want_chart:
        return _chart(name, days, tag)

    s, spec = spread_series(name)
    st = _stats(s, days)
    return (f"[{spec['label']}] as of {st['asof']:%Y-%m-%d}\n"
            f"{st['last']:.1f}bp | 1d {_chg(st['d1'])}, 1w {_chg(st['w1'])}, "
            f"1mo {_chg(st['m1'])}, 1y {_chg(st['y1'])}\n"
            + ("z n/a" if st["z"] is None else
               f"z({tag}): {st['z']:+.2f}, pct: {st['pct']:.0f}% (n={st['n']})"))
