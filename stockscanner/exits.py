"""Salgsregler fra MSS' videoer, testet på samme køb (byggeplan punkt 9).

Regler (signal ved lukning, salg næste handelsdags åbning):
  SMA20 / SMA50 / SMA200: lukning under gennemsnittet (MSS: 50 = alarm, 200 = ud, 20 ved hurtige løb)
  Supertrend ×3 / ×5: ATR(10), trend vender ned (MSS' "Styr din risiko")
  Hybrid: SMA20 når kursen er mere end 15 % over SMA50 (eksplosiv, SAAB-videoen), ellers SMA50
  StockMap: MSS' salgssignal på ugebarer (pil 180–270° i en anden kvadrant end købet)
  Fast 60 dage: sammenligningsgrundlag
Køb: StockMap simpelt køb (ugentligt) eller trendkøb (luk krydser over SMA50, mens luk > SMA200).
Historisk test, IKKE en købsanbefaling.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from stockscanner.stockmap import StockMapParams, rotation, signals

EXPLOSIVE_PCT = 15.0
FIXED_DAYS = 60
MAX_DAYS = 504  # højst ca. to år i en handel


def _daily(prices: pd.DataFrame) -> pd.DataFrame:
    frame = prices[["Open", "High", "Low", "Close"]].apply(pd.to_numeric, errors="coerce").copy()
    index = pd.DatetimeIndex(pd.to_datetime(prices.index))
    frame.index = (index.tz_localize(None) if index.tz is not None else index).normalize()
    return frame[~frame.index.duplicated(keep="last")].sort_index().dropna()


def supertrend(prices: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.Series:
    """True = optrend. Standard Supertrend med Wilder-ATR."""
    f = _daily(prices)
    high, low, close = f["High"].to_numpy(), f["Low"].to_numpy(), f["Close"].to_numpy()
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(abs(high - prev_close), abs(low - prev_close)))
    atr = pd.Series(tr).ewm(alpha=1 / period, adjust=False, min_periods=period).mean().to_numpy()
    mid = (high + low) / 2
    upper, lower = mid + multiplier * atr, mid - multiplier * atr
    final_upper, final_lower = upper.copy(), lower.copy()
    trend = np.ones(len(close), dtype=bool)
    for i in range(1, len(close)):
        if np.isnan(atr[i]):
            continue
        if np.isnan(final_upper[i - 1]):  # første dag med ATR: bånd starter her
            continue
        final_upper[i] = upper[i] if (upper[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1]) else final_upper[i - 1]
        final_lower[i] = lower[i] if (lower[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1]) else final_lower[i - 1]
        if trend[i - 1]:
            trend[i] = not close[i] < final_lower[i]
        else:
            trend[i] = close[i] > final_upper[i]
    out = pd.Series(trend, index=f.index)
    out[np.isnan(atr)] = True
    return out


def exit_signals(prices: pd.DataFrame) -> pd.DataFrame:
    """Daglige salgssignaler (True = sælg næste åbning) for de daglige regler.

    Et salg er et BRUD: lukningen krydser ned under gennemsnittet, eller Supertrend vender fra op til ned.
    En aktie, der allerede ligger under ved købet, sælges altså først ved næste brud nedad.
    """
    f = _daily(prices)
    close = f["Close"]
    sma = {n: close.rolling(n, min_periods=n).mean() for n in (20, 50, 200)}
    below = {n: close < sma[n] for n in sma}
    cross = {n: below[n] & ~below[n].shift(1, fill_value=True) for n in sma}
    flips = {m: (lambda up: ~up & up.shift(1, fill_value=False))(supertrend(f, 10, m)) for m in (3.0, 5.0)}
    explosive = ((close / sma[50] - 1) * 100 > EXPLOSIVE_PCT).shift(1, fill_value=False)
    return pd.DataFrame({
        "SMA20": cross[20],
        "SMA50": cross[50],
        "SMA200": cross[200],
        "Supertrend x3": flips[3.0],
        "Supertrend x5": flips[5.0],
        "Hybrid 20/50": np.where(explosive, cross[20], cross[50]),
    }, index=f.index).fillna(False).astype(bool)


def trend_entries(prices: pd.DataFrame) -> list[pd.Timestamp]:
    """Signaldage: lukning krydser op over SMA50, mens lukning ligger over SMA200."""
    close = _daily(prices)["Close"]
    sma50, sma200 = close.rolling(50, min_periods=50).mean(), close.rolling(200, min_periods=200).mean()
    cross = (close > sma50) & (close.shift(1) <= sma50.shift(1)) & (close > sma200)
    return list(close.index[cross.fillna(False)])


def stockmap_entries(prices: pd.DataFrame, benchmark: pd.DataFrame, params: StockMapParams = StockMapParams()):
    """(signal-dag, kvadrant ved køb) for MSS' simple købssignal; signaldag = ugens sidste handelsdag."""
    rot = rotation(prices, benchmark, params)
    sig = signals(rot)
    days = _daily(prices).index
    result = []
    for week, kind in sig.items():
        if kind != "køb":
            continue
        last = days[days <= week]
        if len(last):
            result.append((last[-1], rot.loc[week, "quadrant"]))
    return result


def stockmap_exit_days(prices: pd.DataFrame, benchmark: pd.DataFrame, params: StockMapParams = StockMapParams()):
    """Ugens sidste handelsdag for hvert salgssignal, med kvadranten den uge."""
    rot = rotation(prices, benchmark, params)
    sig = signals(rot)
    days = _daily(prices).index
    out = []
    for week, kind in sig.items():
        if kind == "salg":
            last = days[days <= week]
            if len(last):
                out.append((last[-1], rot.loc[week, "quadrant"]))
    return out


@dataclass(frozen=True)
class ExitTrade:
    rule: str
    entry_day: pd.Timestamp
    exit_day: pd.Timestamp
    return_pct: float
    days: int
    worst_pct: float     # dybeste fald under handlen (lukkekurser) i forhold til købet
    best_pct: float      # højeste gevinst undervejs (lukkekurser)


def simulate(prices: pd.DataFrame, entries, rule: str, daily_exits: pd.DataFrame | None = None,
             stockmap_sells=None, cost_pct: float = 0.1) -> list[ExitTrade]:
    """Én handel pr. købssignal (overlap tilladt). Køb næste åbning efter signaldagen.

    `entries` er en liste af (signaldag, kvadrant) eller signaldage. Handler, der stadig er åbne ved
    dataenes slutning (og under MAX_DAYS), tælles ikke.
    """
    f = _daily(prices)
    opens, closes = f["Open"].to_numpy(), f["Close"].to_numpy()
    index = f.index
    position = {day: i for i, day in enumerate(index)}
    exit_mask = None if daily_exits is None or rule not in daily_exits else daily_exits[rule].reindex(index).fillna(False).to_numpy()
    trades = []
    for entry in entries:
        signal_day, quadrant = entry if isinstance(entry, tuple) else (entry, None)
        i = position.get(signal_day)
        if i is None or i + 1 >= len(index):
            continue
        start = i + 1
        exit_i = None
        if rule == "Fast 60 dage":
            if start + FIXED_DAYS < len(index):
                exit_i = start + FIXED_DAYS
        elif rule == "StockMap":
            for day, sell_quadrant in stockmap_sells or []:
                j = position.get(day)
                if j is not None and j >= start and sell_quadrant != quadrant and j + 1 < len(index):
                    exit_i = j + 1
                    break
                if j is not None and j >= start + MAX_DAYS:
                    break
        else:
            for j in range(start, min(start + MAX_DAYS, len(index) - 1)):
                if exit_mask[j]:
                    exit_i = j + 1
                    break
        if exit_i is None:
            if start + MAX_DAYS < len(index):
                exit_i = start + MAX_DAYS
            else:
                continue
        entry_px, exit_px = opens[start], opens[exit_i]
        path = closes[start:exit_i] / entry_px - 1 if exit_i > start else np.array([0.0])
        trades.append(ExitTrade(rule, index[start], index[exit_i], (exit_px / entry_px - 1) * 100 - 2 * cost_pct,
                                exit_i - start, float(path.min() * 100), float(path.max() * 100)))
    return trades


def summarize(trades: list[ExitTrade]) -> dict[str, float | None]:
    if not trades:
        return {"trades": 0}
    pct = np.array([t.return_pct for t in trades])
    gains, losses = pct[pct > 0].sum(), -pct[pct < 0].sum()
    best = np.array([t.best_pct for t in trades])
    capture = pct[best > 5] / best[best > 5] if (best > 5).any() else np.array([np.nan])
    return {
        "trades": len(pct),
        "mean_pct": float(pct.mean()),
        "median_pct": float(np.median(pct)),
        "win_rate": float((pct > 0).mean() * 100),
        "profit_factor": float(gains / losses) if losses > 0 else float("inf"),
        "days": float(np.median([t.days for t in trades])),
        "worst_mean": float(np.mean([t.worst_pct for t in trades])),
        "worst_p5": float(np.percentile([t.worst_pct for t in trades], 5)),
        "capture": float(np.nanmedian(capture) * 100),
        "pct_per_100d": float(pct.mean() / max(np.mean([t.days for t in trades]), 1) * 100),
    }


DAILY_RULES = ["SMA20", "SMA50", "SMA200", "Supertrend x3", "Supertrend x5", "Hybrid 20/50"]
ALL_RULES = DAILY_RULES + ["StockMap", "Fast 60 dage"]
