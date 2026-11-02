"""MTI-lite: egen tilnærmelse af MSS' Momentum Trend Indicator (byggeplan punkt 3).

MSS (videoerne): MTI måler kursen relativt til indeks og sektor, på dags- og ugegraf; "dobbelt grøn" =
grøn på begge og er deres købsfilter. Vores bud: relativ styrke (aktie/hjemmeindeks) over sit EMA
(20 dage / 10 uger). Indeksets lukning fra dagen før bruges (ingen look-ahead på tværs af børser).
Sektor-delen er ikke med endnu. Screening, IKKE en købsanbefaling.
"""
from __future__ import annotations

import pandas as pd

HOME_INDEX = {".CO": "^OMXC25", ".ST": "^OMX", ".OL": "OSEBX.OL", ".DE": "^GDAXI", ".F": "^GDAXI",
              ".AS": "^AEX", ".PA": "^FCHI", ".SW": "^SSMI", ".MI": "FTSEMIB.MI", ".L": "^FTSE", ".HE": "^OMXH25"}
DEFAULT_INDEX = "RSP"
DAILY_EMA = 20
WEEKLY_EMA = 10


def home_index(ticker: str) -> str:
    for suffix, index in HOME_INDEX.items():
        if ticker.upper().endswith(suffix):
            return index
    return DEFAULT_INDEX


def _dated(series: pd.Series) -> pd.Series:
    series = pd.to_numeric(series, errors="coerce")
    index = pd.DatetimeIndex(pd.to_datetime(series.index))
    series.index = (index.tz_localize(None) if index.tz is not None else index).normalize()
    return series[~series.index.duplicated(keep="last")].sort_index().dropna()


def mti_state(prices: pd.DataFrame, index_prices: pd.DataFrame) -> dict[str, bool | None]:
    """{'daily': bool, 'weekly': bool, 'double_green': bool} ved seneste lukning (None ved for lidt data)."""
    close = _dated(prices["Close"])
    bench = _dated(index_prices["Close"]).shift(1).reindex(close.index, method="ffill")
    rs = (close / bench).dropna()
    if len(rs) < DAILY_EMA + 5:
        return {"daily": None, "weekly": None, "double_green": None}
    daily = bool(rs.iloc[-1] > rs.ewm(span=DAILY_EMA, adjust=False).mean().iloc[-1])
    weekly_rs = rs.resample("W-FRI").last().dropna()
    if not weekly_rs.empty and rs.index[-1] < weekly_rs.index[-1]:
        weekly_rs = weekly_rs.iloc[:-1]  # uafsluttet uge
    weekly = None
    if len(weekly_rs) >= WEEKLY_EMA + 2:
        weekly = bool(weekly_rs.iloc[-1] > weekly_rs.ewm(span=WEEKLY_EMA, adjust=False).mean().iloc[-1])
    return {"daily": daily, "weekly": weekly, "double_green": bool(daily and weekly) if weekly is not None else None}
