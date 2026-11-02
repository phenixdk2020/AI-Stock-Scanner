"""Egen StockMap: relativ rotation mod et benchmark på ugebarer (kandidatformel, fase 7).

Bygget ud fra MSS' videoer: relativ styrke mod RSP, ugeniveau, EMA- eller SMA-udglattet "slange",
fire kvadranter og en pil i kompasgrader (0 = kl. 12, 90 = kl. 3, 180 = kl. 6, 270 = kl. 9).
Simpelt køb: i gul eller rød kvadrant, pilen har peget nedad og tipper op over vandret.
Salg: pilen peger ned og tilbage (180–270°). Signal ved ugens lukning, handel næste uges åbning.
MSS' egne parametre er ukendte; standardværdierne her er udgangspunkt for kalibrering.
Screening og historisk test, IKKE en købsanbefaling.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

QUADRANTS = {"leading": "grøn", "weakening": "gul", "lagging": "rød", "improving": "blå"}


@dataclass(frozen=True)
class StockMapParams:
    """Standard = bedste bud fra kalibrering 02-11-2026 (47 aktier 2019–2026 + 9 MSS-vinkler):
    60 % vindere, +5,3 % pr. handel, PF 2,2, median 14 uger; vinkler median 19° fra MSS.
    Valgt blandt 54 kombinationer på få observationer – skal genbekræftes på nye data."""
    smooth: int = 12       # udglatning af RS-linjen (uger)
    window: int = 40       # gennemsnit som RS-niveau måles mod (uger)
    momentum: int = 2      # uger tilbage for RS-momentum
    ema: bool = True       # EMA (True) eller SMA (False), som MSS lader brugeren vælge


def _dates(index: pd.Index) -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(pd.to_datetime(index))
    return (dates.tz_localize(None) if dates.tz is not None else dates).normalize()


def weekly(prices: pd.DataFrame) -> pd.DataFrame:
    """Ugebarer der slutter fredag: første åbning og sidste lukning i ugen."""
    frame = prices[["Open", "Close"]].apply(pd.to_numeric, errors="coerce").copy()
    frame.index = _dates(prices.index)
    frame = frame[~frame.index.duplicated(keep="last")].sort_index().dropna()
    bars = frame.resample("W-FRI").agg({"Open": "first", "Close": "last"}).dropna()
    if not bars.empty and not frame.empty and frame.index[-1] < bars.index[-1]:
        bars = bars.iloc[:-1]  # ugen er ikke afsluttet endnu (signal først ved fredagens lukning)
    return bars


def _smooth(series: pd.Series, span: int, ema: bool) -> pd.Series:
    if span <= 1:
        return series
    if ema:
        return series.ewm(span=span, adjust=False, min_periods=span).mean()
    return series.rolling(span, min_periods=span).mean()


def rotation(prices: pd.DataFrame, benchmark: pd.DataFrame, params: StockMapParams = StockMapParams()) -> pd.DataFrame:
    """Ugentlig RS-niveau (x), RS-momentum (y), kvadrant og pilens vinkel."""
    stock, bench = weekly(prices), weekly(benchmark)
    joined = pd.concat([stock["Close"].rename("stock"), bench["Close"].rename("bench")], axis=1).dropna()
    rs = _smooth(joined["stock"] / joined["bench"], params.smooth, params.ema)
    level = 100 * rs / _smooth(rs, params.window, params.ema)
    momentum = 100 + (level - level.shift(params.momentum))
    out = pd.DataFrame({"x": level, "y": momentum}).dropna()
    dx, dy = out["x"].diff(), out["y"].diff()
    out["angle"] = (np.degrees(np.arctan2(dx, dy)) % 360).where(~(dx.isna() | ((dx == 0) & (dy == 0))))
    out["quadrant"] = np.where(out["x"] >= 100,
                               np.where(out["y"] >= 100, "leading", "weakening"),
                               np.where(out["y"] < 100, "lagging", "improving"))
    return out


def points_up(angle: float) -> bool:
    """Over vandret: mellem kl. 9 og kl. 3 gennem kl. 12 (270–360° eller 0–90°)."""
    return angle > 270 or angle < 90


def signals(rot: pd.DataFrame) -> pd.Series:
    """'køb', 'salg' eller '' pr. uge ud fra MSS' simple regler (uden positionstilstand)."""
    out = pd.Series("", index=rot.index)
    previous = rot["angle"].shift(1)
    for i, (angle, before, quadrant) in enumerate(zip(rot["angle"], previous, rot["quadrant"])):
        if np.isnan(angle) or np.isnan(before):
            continue
        if quadrant in ("weakening", "lagging") and points_up(angle) and not points_up(before):
            out.iloc[i] = "køb"
        elif 180 <= angle <= 270:
            out.iloc[i] = "salg"
    return out


@dataclass(frozen=True)
class Trade:
    entry_week: pd.Timestamp
    exit_week: pd.Timestamp | None
    return_pct: float
    weeks: int


def trades(prices: pd.DataFrame, benchmark: pd.DataFrame, params: StockMapParams = StockMapParams(),
           cost_pct: float = 0.1) -> list[Trade]:
    """Én position ad gangen: køb næste uges åbning efter køb-signal; sælg næste uges åbning efter
    salgssignal i en anden kvadrant end købet. Åbne handler ved dataenes slutning tælles ikke."""
    rot = rotation(prices, benchmark, params)
    sig = signals(rot)
    bars = weekly(prices).reindex(rot.index)
    opens = bars["Open"].shift(-1)  # næste uges åbning
    result, entry, entry_quadrant, entry_i = [], None, None, None
    for i, week in enumerate(rot.index):
        if entry is None and sig.iloc[i] == "køb" and not np.isnan(opens.iloc[i]):
            entry, entry_quadrant, entry_i = opens.iloc[i], rot["quadrant"].iloc[i], i
        elif entry is not None and sig.iloc[i] == "salg" and rot["quadrant"].iloc[i] != entry_quadrant:
            if np.isnan(opens.iloc[i]):
                break
            pct = (opens.iloc[i] / entry - 1) * 100 - 2 * cost_pct
            result.append(Trade(rot.index[entry_i], week, pct, i - entry_i))
            entry = None
    return result


def trade_stats(all_trades: list[Trade]) -> dict[str, float | None]:
    if not all_trades:
        return {"trades": 0, "win_rate": None, "mean_pct": None, "weeks": None, "profit_factor": None}
    pct = np.array([t.return_pct for t in all_trades])
    gains, losses = pct[pct > 0].sum(), -pct[pct < 0].sum()
    return {"trades": len(pct), "win_rate": float((pct > 0).mean() * 100), "mean_pct": float(pct.mean()),
            "weeks": float(np.median([t.weeks for t in all_trades])),
            "profit_factor": float(gains / losses) if losses > 0 else math.inf}


def angle_on(prices: pd.DataFrame, benchmark: pd.DataFrame, date: str,
             params: StockMapParams = StockMapParams()) -> float | None:
    """Pilens vinkel for den seneste afsluttede uge på eller før `date`."""
    rot = rotation(prices, benchmark, params)
    rot = rot[rot.index <= pd.Timestamp(date)]
    if rot.empty or np.isnan(rot["angle"].iloc[-1]):
        return None
    return float(rot["angle"].iloc[-1])
