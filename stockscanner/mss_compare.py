"""Sammenlign vores egne beregninger med observerede MyStockScanner-tal (fase 7).

Formålet er at måle, hvor tæt vores åbne model kommer på MSS' tal – ikke at kopiere dem.
Observationer ligger lokalt i `data/mss_observations.csv` (semikolon, én række pr. aktie og dato).
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from stockscanner.candles import trend_context

OBSERVATIONS = Path(__file__).resolve().parent.parent / "data" / "mss_observations.csv"


def load_observations(path: Path = OBSERVATIONS) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [row for row in csv.DictReader(handle, delimiter=";") if row.get("yf_ticker")]


def stockmap_angle(prices: pd.DataFrame, benchmark: pd.DataFrame, date: str,
                   ratio_days: int = 50, momentum_days: int = 10, trail_days: int = 5) -> float | None:
    """Første bud på StockMap-pilens retning (kompasgrader: 0 = op, 90 = højre).

    RRG-lignende: x = RS-niveau (RS-linje i forhold til sit gennemsnit), y = RS-momentum
    (ændring i x over `momentum_days`). Retningen er bevægelsen over de sidste `trail_days`.
    MSS' egne parametre kendes ikke; disse er udgangspunkt for kalibrering.
    """
    close = _dated(prices["Close"])
    bench = _dated(benchmark["Close"]).reindex(close.index, method="ffill")
    rs = close / bench
    ratio = 100 * rs / rs.rolling(ratio_days, min_periods=ratio_days).mean()
    momentum = 100 * ratio / ratio.shift(momentum_days)
    upto = pd.Timestamp(date)
    ratio, momentum = ratio[:upto].dropna(), momentum[:upto].dropna()
    if len(momentum) <= trail_days:
        return None
    dx = ratio.iloc[-1] - ratio.iloc[-1 - trail_days]
    dy = momentum.iloc[-1] - momentum.iloc[-1 - trail_days]
    if dx == 0 and dy == 0:
        return None
    return math.degrees(math.atan2(dx, dy)) % 360


def angle_difference(a: float, b: float) -> float:
    """Mindste vinkelforskel i grader (0–180)."""
    return abs((a - b + 180) % 360 - 180)


def _dated(series: pd.Series) -> pd.Series:
    series = pd.to_numeric(series, errors="coerce")
    index = pd.DatetimeIndex(pd.to_datetime(series.index))
    if index.tz is not None:
        index = index.tz_localize(None)
    series.index = index.normalize()
    return series[~series.index.duplicated(keep="last")].sort_index()


def trend_state(prices: pd.DataFrame, date: str) -> str:
    """Vores egen trendtilstand på datoen, til sammenligning med MSS' timingzone."""
    context = trend_context(prices)
    index = pd.DatetimeIndex(pd.to_datetime(prices.index))
    context.index = (index.tz_localize(None) if index.tz is not None else index).normalize()
    context = context[:pd.Timestamp(date)]
    if context.empty:
        return "–"
    last = context.iloc[-1]
    if not last["uptrend"]:
        return "Ingen optrend"
    return "Optrend + rekyl" if last["pullback"] else "Optrend"


def spearman(x: list[float], y: list[float]) -> float | None:
    """Rangkorrelation; None ved færre end 3 par."""
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    if len(pairs) < 3:
        return None
    a, b = zip(*pairs)
    return float(pd.Series(a).rank().corr(pd.Series(b).rank()))


@dataclass(frozen=True)
class ComparisonRow:
    date: str
    ticker: str
    mss_quality: float | None
    our_quality: float | None
    mss_zone: str
    our_trend: str
    mss_angle: float | None
    our_angle: float | None

    @property
    def angle_diff(self) -> float | None:
        if self.mss_angle is None or self.our_angle is None:
            return None
        return angle_difference(self.mss_angle, self.our_angle)


def _float(value: str) -> float | None:
    try:
        return float(value.replace(",", "."))
    except (AttributeError, ValueError):
        return None


def compare(observations, fetch_prices, fetch_quality, benchmark: pd.DataFrame | None) -> list[ComparisonRow]:
    """`fetch_prices(ticker) -> DataFrame`, `fetch_quality(ticker) -> float | None` (injiceres for test)."""
    rows = []
    for obs in observations:
        ticker, date = obs["yf_ticker"], obs["date"]
        try:
            prices = fetch_prices(ticker)
        except Exception:
            prices = None
        try:
            quality = fetch_quality(ticker)
        except Exception:
            quality = None
        rows.append(ComparisonRow(
            date=date, ticker=ticker,
            mss_quality=_float(obs.get("quality", "")), our_quality=quality,
            mss_zone=obs.get("timing_zone", ""),
            our_trend="–" if prices is None else trend_state(prices, date),
            mss_angle=_float(obs.get("stockmap_angle", "")),
            our_angle=None if prices is None or benchmark is None else stockmap_angle(prices, benchmark, date),
        ))
    return rows


def summary(rows: list[ComparisonRow]) -> dict[str, float | None]:
    diffs = [row.angle_diff for row in rows if row.angle_diff is not None]
    quality_pairs = [(r.mss_quality, r.our_quality) for r in rows if r.mss_quality is not None and r.our_quality is not None]
    return {
        "quality_spearman": spearman([p[0] for p in quality_pairs], [p[1] for p in quality_pairs]),
        "quality_mean_abs_diff": float(np.mean([abs(a - b) for a, b in quality_pairs])) if quality_pairs else None,
        "angle_median_diff": float(np.median(diffs)) if diffs else None,
        "angle_within_45": float(np.mean([d <= 45 for d in diffs]) * 100) if diffs else None,
    }
