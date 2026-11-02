"""TPI-lite: egen, åben tilnærmelse af MSS' Turning Point Indicator (byggeplan punkt 4).

MSS (videoerne "Lav god profit med TPI", "Webinar MTCI", "Stock Scores"): tre lag – lang trend, uge og
dag – og tilstande grøn/rød samt gul = oversolgt i akkumulering og grå = overkøbt. Købsregel: lang trend
grøn + uge oversolgt, hold 130 handelsdage uden stop. Deres kalibrering: oversolgt i lang optrend gav
ca. 0,9 % pr. 5 handelsdage mod 0,2 % i dårligste gruppe. Formlen er hemmelig; dette er vores bud:
  lang trend grøn: ugelukning over sit 40-ugers gennemsnit, og gennemsnittet stiger over 10 uger
  oversolgt/overkøbt: aktiens 4-ugers afkast i forhold til sin egen historik (percentil ≤ 20 / ≥ 80)
Kun data til og med dagen bruges. Screening og historisk test, IKKE en købsanbefaling.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LONG_WEEKS = 40
SLOPE_WEEKS = 10
SHORT_WEEKS = 4
HISTORY_WEEKS = 260
OVERSOLD_PCT = 20
OVERBOUGHT_PCT = 80


def _weekly_close(prices: pd.DataFrame) -> pd.Series:
    close = pd.to_numeric(prices["Close"], errors="coerce")
    index = pd.DatetimeIndex(pd.to_datetime(close.index))
    close.index = (index.tz_localize(None) if index.tz is not None else index).normalize()
    close = close[~close.index.duplicated(keep="last")].sort_index().dropna()
    weekly = close.resample("W-FRI").last().dropna()
    if not weekly.empty and close.index[-1] < weekly.index[-1]:
        weekly = weekly.iloc[:-1]  # uafsluttet uge
    return weekly


def tpi_states(prices: pd.DataFrame) -> pd.DataFrame:
    """Ugentlige tilstande: long_green (bool), short_pct (0–100) og state (tekst)."""
    weekly = _weekly_close(prices)
    sma = weekly.rolling(LONG_WEEKS, min_periods=LONG_WEEKS).mean()
    long_green = (weekly > sma) & (sma > sma.shift(SLOPE_WEEKS))
    short = weekly / weekly.shift(SHORT_WEEKS) - 1
    # percentil af dagens 4-ugers afkast i aktiens egen historik (kun fortiden)
    short_pct = short.rolling(HISTORY_WEEKS, min_periods=104).apply(lambda w: (w[:-1] < w[-1]).mean() * 100, raw=True)
    out = pd.DataFrame({"long_green": long_green, "short_pct": short_pct}).dropna()
    out["state"] = np.select(
        [out["short_pct"] <= OVERSOLD_PCT, out["short_pct"] >= OVERBOUGHT_PCT],
        ["oversolgt", "overkøbt"], default="neutral")
    return out


def bucket_returns(prices: pd.DataFrame, horizons=(5, 20, 65, 130), cost_pct: float = 0.1) -> pd.DataFrame:
    """Afkast pr. tilstandsgruppe: signal ved ugens lukning, køb næste handelsdags åbning,
    salg ved lukning efter N handelsdage."""
    states = tpi_states(prices)
    daily = prices[["Open", "Close"]].apply(pd.to_numeric, errors="coerce").copy()
    index = pd.DatetimeIndex(pd.to_datetime(daily.index))
    daily.index = (index.tz_localize(None) if index.tz is not None else index).normalize()
    daily = daily[~daily.index.duplicated(keep="last")].sort_index().dropna()
    position = daily.index.searchsorted(states.index, side="right")  # første dag efter ugens lukning
    rows = []
    for (week, row), start in zip(states.iterrows(), position):
        if start >= len(daily):
            continue
        rec = {"week": week, "group": f"{'lang grøn' if row['long_green'] else 'lang rød'} / {row['state']}"}
        entry = daily["Open"].iloc[start]
        for h in horizons:
            end = start + h - 1
            rec[f"{h}d"] = (daily["Close"].iloc[end] / entry - 1) * 100 - 2 * cost_pct if end < len(daily) else np.nan
        rows.append(rec)
    return pd.DataFrame(rows)
