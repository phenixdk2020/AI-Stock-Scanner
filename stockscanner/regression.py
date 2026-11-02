"""Regressionskanal og ADX (backlog B-08 og B-12). Rene funktioner, ingen netværk.

Regressionskanal: lineær regression på log(luk) over de seneste N dage (inkl. dagen selv),
bånd = ±k·σ af residualerne. Alt på dag t bruger kun data til og med dag t.
Salgsregel: korrelationen R ≥ 0.9 (tydelig optrend) og lukningen BRYDER ned under nedre bånd.
ADX: Wilders ADX(14), bruges som trendfilter på køb (ADX > 25).
Historisk test, IKKE en købsanbefaling.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

MIN_R = 0.9
BAND_SIGMA = 2.0
ADX_PERIOD = 14
ADX_MIN = 25.0


def regression_channel(close: pd.Series, window: int = 126, sigma: float = BAND_SIGMA) -> pd.DataFrame:
    """Rullende regression på log(luk). Kolonner: mid, lower, upper (i kurs), r (korrelation med tid), slope (log pr. dag).

    De første `window - 1` dage er NaN.
    """
    values = np.log(pd.to_numeric(close, errors="coerce").to_numpy(dtype=float))
    n = len(values)
    out = {k: np.full(n, np.nan) for k in ("mid", "lower", "upper", "r", "slope")}
    if n >= window and window >= 3:
        x = np.arange(window, dtype=float)
        xc = x - x.mean()
        sxx = float((xc ** 2).sum())
        win = sliding_window_view(values, window)          # (n-window+1, window)
        ymean = win.mean(axis=1)
        yc = win - ymean[:, None]
        sxy = yc @ xc
        syy = (yc ** 2).sum(axis=1)
        slope = sxy / sxx
        fitted_end = ymean + slope * xc[-1]                 # regressionslinjen på sidste dag i vinduet
        sse = np.maximum(syy - slope * sxy, 0.0)
        std = np.sqrt(sse / (window - 2))
        with np.errstate(invalid="ignore", divide="ignore"):
            r = np.where(syy > 0, sxy / np.sqrt(sxx * syy), 0.0)
        sl = slice(window - 1, None)
        out["mid"][sl] = np.exp(fitted_end)
        out["lower"][sl] = np.exp(fitted_end - sigma * std)
        out["upper"][sl] = np.exp(fitted_end + sigma * std)
        out["r"][sl] = r
        out["slope"][sl] = slope
    return pd.DataFrame(out, index=close.index)


def regression_break(close: pd.Series, window: int = 126, min_r: float = MIN_R,
                     sigma: float = BAND_SIGMA) -> pd.Series:
    """True på den dag, lukningen krydser ned under nedre bånd, mens R ≥ min_r (brud, ikke tilstand).

    R måles på dagen før bruddet (kanalen skal have været en ren optrend, før kursen faldt ud af den),
    og dagens brud ligger under dagens nedre bånd.
    """
    ch = regression_channel(close, window, sigma)
    below = close < ch["lower"]
    cross = below & ~below.shift(1, fill_value=True)
    trending = ch["r"].shift(1) >= min_r
    return (cross & trending).fillna(False).astype(bool)


def adx(prices: pd.DataFrame, period: int = ADX_PERIOD) -> pd.Series:
    """Wilders ADX. Bruger High/Low/Close; de første ca. 2·period dage er NaN."""
    high = pd.to_numeric(prices["High"], errors="coerce")
    low = pd.to_numeric(prices["Low"], errors="coerce")
    close = pd.to_numeric(prices["Close"], errors="coerce")
    up, down = high.diff(), -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=prices.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=prices.index)
    prev = close.shift(1)
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    tr.iloc[0] = np.nan
    wilder = lambda s: s.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    atr = wilder(tr)
    with np.errstate(invalid="ignore", divide="ignore"):
        plus_di = 100 * wilder(plus_dm) / atr
        minus_di = 100 * wilder(minus_dm) / atr
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return wilder(dx.fillna(0).where(atr.notna())).where(atr.notna())
