"""Fase 5, første tests: giver trend, relativ styrke og tilbagerekyl bedre afkast end en tilfældig dag?

A: optrend alene (samme definition som `candles.trend_context`).
B: A + relativ styrke mod benchmark (RS-linjen over sit 50-dages gennemsnit).
C: A med tilbagerekyl mod A uden tilbagerekyl.
Ingen tuning: faste parametre, og den urørte slutperiode rapporteres for sig.
Screening og historisk test, IKKE en købsanbefaling.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from stockscanner.candles import DEFAULT_COST_PCT, forward_returns, trend_context

DEFAULT_BENCHMARK = "RSP"  # ligevægtet S&P 500, MSS' foretrukne benchmark
RS_SMA_DAYS = 50
REGIMES = {
    "alle": "Alle dage (basis)",
    "A_trend": "A: optrend",
    "B_trend_rs": "B: optrend + relativ styrke",
    "C_trend_rekyl": "C: optrend + tilbagerekyl",
    "C_trend_uden_rekyl": "C: optrend uden tilbagerekyl",
}


def relative_strength(prices: pd.DataFrame, benchmark: pd.DataFrame, sma_days: int = RS_SMA_DAYS) -> pd.Series:
    """True når RS-linjen (aktie/benchmark) ligger over sit eget gennemsnit.

    Benchmark forskydes én handelsdag: en europæisk lukning kendes før den amerikanske
    samme dag, så vi bruger kun benchmarkens lukning fra dagen før (ingen look-ahead).
    """
    close = pd.to_numeric(prices["Close"], errors="coerce")
    bench = pd.to_numeric(benchmark["Close"], errors="coerce")
    bench.index = _naive_dates(bench.index)
    bench = bench[~bench.index.duplicated(keep="last")].sort_index()
    known = bench.shift(1).reindex(_naive_dates(close.index), method="ffill")
    known.index = close.index
    rs = close / known
    return (rs > rs.rolling(sma_days, min_periods=sma_days).mean()).fillna(False)


def _naive_dates(index: pd.Index) -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(pd.to_datetime(index))
    if dates.tz is not None:
        dates = dates.tz_localize(None)
    return dates.normalize()


def regime_masks(prices: pd.DataFrame, benchmark: pd.DataFrame | None = None) -> pd.DataFrame:
    """Én boolsk kolonne pr. regime, målt ved dagens lukning."""
    context = trend_context(prices)
    trend, pullback = context["uptrend"].astype(bool), context["pullback"].astype(bool)
    masks = pd.DataFrame(index=prices.index)
    masks["alle"] = True
    masks["A_trend"] = trend
    if benchmark is not None:
        masks["B_trend_rs"] = trend & relative_strength(prices, benchmark)
    masks["C_trend_rekyl"] = trend & pullback
    masks["C_trend_uden_rekyl"] = trend & ~pullback
    return masks


@dataclass(frozen=True)
class RegimeRow:
    period: str
    regime: str
    horizon: str
    days: int
    mean_pct: float | None
    median_pct: float | None
    hit_rate_pct: float | None
    edge_pct: float | None
    worst5_pct: float | None = None  # 5 %-fraktilen: hvor slemt de dårligste udfald er


def regime_backtest(histories: dict[str, pd.DataFrame], benchmark: pd.DataFrame | None = None,
                    horizons=(5, 20, 60), holdout_start: str | None = None,
                    cost_pct: float = DEFAULT_COST_PCT) -> list[RegimeRow]:
    """Afkast efter signal ved lukning (køb næste åbning, salg ved lukning efter N dage).

    Edge = regimets snit minus snittet for alle dage i samme periode.
    `holdout_start` deler i "udvikling" og "urørt"; uden den rapporteres kun "alt".
    Dage overlapper, så `days` er ikke uafhængige observationer.
    """
    parts = []
    for ticker, frame in histories.items():
        masks = regime_masks(frame, benchmark)
        returns = forward_returns(frame, horizons, cost_pct)
        joined = pd.concat([masks, returns], axis=1)
        joined.index = pd.MultiIndex.from_arrays([[ticker] * len(joined), _naive_dates(frame.index)])
        parts.append(joined)
    if not parts:
        return []
    data = pd.concat(parts)
    dates = data.index.get_level_values(1)
    periods = {"alt": slice(None)}
    if holdout_start:
        cut = pd.Timestamp(holdout_start)
        periods = {"udvikling": dates < cut, "urørt": dates >= cut}

    rows = []
    regimes = [name for name in REGIMES if name in data.columns]
    for period, selector in periods.items():
        subset = data[selector] if period != "alt" else data
        for horizon in returns.columns:
            base = subset[horizon].dropna()
            base_mean = float(base.mean()) if len(base) else None
            for regime in regimes:
                values = subset.loc[subset[regime].astype(bool), horizon].dropna()
                if values.empty:
                    rows.append(RegimeRow(period, regime, horizon, 0, None, None, None, None))
                    continue
                mean = float(values.mean())
                rows.append(RegimeRow(period, regime, horizon, len(values), mean, float(values.median()),
                                      float((values > 0).mean() * 100),
                                      None if base_mean is None else mean - base_mean,
                                      float(values.quantile(0.05))))
    return rows
