"""
analysis/stats.py

Statistics over full series — the computation pattern the snapshot engine isn't
shaped for. These take clean pandas Series (from storage.loader.series) and
return numbers or small frames. Pure functions, no file access, easy to test.

Covers the bread-and-butter for macro rates/credit work: rolling vol, z-score,
rolling beta/correlation, simple regression, percentile rank. Extend freely.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_vol(s: pd.Series, window: int = 20, annualize: int = 252) -> pd.Series:
    """Rolling stdev of daily changes, optionally annualized (bp for rates)."""
    chg = s.sort_index().diff()
    vol = chg.rolling(window).std()
    if annualize:
        vol = vol * np.sqrt(annualize)
    return vol


def zscore(s: pd.Series, window: int | None = None) -> pd.Series:
    """Z-score of the level. Full-sample if window is None, else rolling."""
    s = s.sort_index()
    if window:
        mu = s.rolling(window).mean()
        sd = s.rolling(window).std()
    else:
        mu, sd = s.mean(), s.std()
    return (s - mu) / sd


def percentile_rank(s: pd.Series, lookback: int | None = None) -> float:
    """Where does the latest value sit in its own history? 0..100."""
    s = s.sort_index().dropna()
    if lookback:
        s = s.tail(lookback)
    if s.empty:
        return float("nan")
    latest = s.iloc[-1]
    return float((s <= latest).mean() * 100)


def rolling_corr(a: pd.Series, b: pd.Series, window: int = 60) -> pd.Series:
    """Rolling correlation of daily changes between two aligned series."""
    df = pd.concat([a.rename("a"), b.rename("b")], axis=1).sort_index().dropna()
    return df["a"].diff().rolling(window).corr(df["b"].diff())


def rolling_beta(y: pd.Series, x: pd.Series, window: int = 60) -> pd.Series:
    """Rolling beta of y on x (changes). e.g. how a 10Y moves per 1 unit of 2Y."""
    df = pd.concat([y.rename("y"), x.rename("x")], axis=1).sort_index().dropna()
    dy, dx = df["y"].diff(), df["x"].diff()
    cov = dy.rolling(window).cov(dx)
    var = dx.rolling(window).var()
    return cov / var


def ols(y: pd.Series, x: pd.Series) -> dict:
    """Simple OLS y = a + b*x on the overlap. Returns alpha, beta, r2, n."""
    df = pd.concat([y.rename("y"), x.rename("x")], axis=1).dropna()
    if len(df) < 3:
        return {"alpha": float("nan"), "beta": float("nan"),
                "r2": float("nan"), "n": len(df)}
    xv, yv = df["x"].values, df["y"].values
    b, a = np.polyfit(xv, yv, 1)
    yhat = a + b * xv
    ss_res = float(((yv - yhat) ** 2).sum())
    ss_tot = float(((yv - yv.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot else float("nan")
    return {"alpha": float(a), "beta": float(b), "r2": r2, "n": len(df)}