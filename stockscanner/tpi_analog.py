"""TPI-analog (B-16): mønstergenkendelse i aktiens egen historik, tættere på MSS' beskrivelse af TPI end tpi_lite.

MSS: TPI sammenholder aktiens nuværende mønster med ca. 20 års egen historik. Her beskrives hver uge af en lille
vektor fra aktiens egne ugekurser (4-/13-/26-ugers afkast, afstand til 40-ugers gennemsnit, gennemsnittets
hældning over 10 uger, volatilitet over 13 uger). De k mest ligne uger i SAMME aktie, som ligger så langt tilbage,
at deres udfald (afkast over h uger) var afsluttet før nu, giver scoren = gennemsnitligt udfald. Ingen fremtid:
score i uge t bruger kun kurser til og med uge t (afstandene skaleres også kun med fortiden).
Tilstand: scorens percentil i aktiens egen scorehistorik (som tpi_lite): top 20 % = oversolgt (akkumulering,
analogerne steg bagefter), bund 20 % = overkøbt. Lang trend grøn er den samme som i tpi_lite.
Screening og historisk test, IKKE en købsanbefaling.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from stockscanner.tpi_lite import LONG_WEEKS, SLOPE_WEEKS, _weekly_close

FEATURE_WEEKS = (4, 13, 26)
VOL_WEEKS = 13
HORIZON_WEEKS = {5: 1, 20: 4, 65: 13, 130: 26}  # handelsdage -> uger
SCORE_HORIZON = 20  # tilstanden bygger på fire uger frem (som tpi_lite's korte afkast)
K = 20
MIN_ANALOGS = 80
HISTORY_WEEKS = 260
MIN_SCORE_HISTORY = 52
OVERSOLD_PCT = 80   # scorepercentil >= : oversolgt (analogerne steg)
OVERBOUGHT_PCT = 20  # scorepercentil <= : overkøbt


def features(weekly: pd.Series) -> pd.DataFrame:
    """Funktionsvektor pr. uge, kun ud fra kurser til og med ugen selv."""
    f = {f"r{w}": weekly / weekly.shift(w) - 1 for w in FEATURE_WEEKS}
    sma = weekly.rolling(LONG_WEEKS, min_periods=LONG_WEEKS).mean()
    f["dist"] = weekly / sma - 1
    f["slope"] = sma / sma.shift(SLOPE_WEEKS) - 1
    f["vol"] = weekly.pct_change().rolling(VOL_WEEKS, min_periods=VOL_WEEKS).std()
    return pd.DataFrame(f)


def analog_scores_weekly(weekly: pd.Series, k: int = K, horizons=HORIZON_WEEKS) -> pd.DataFrame:
    """Score pr. uge og horisont (kolonner score_<dage>d): snit af de k nærmeste analogers afkast i %.
    Analog j til uge t kræver j + h <= t (udfaldet er afsluttet), så der er ingen fremtid i scoren."""
    close = weekly.to_numpy(dtype=float)
    feat = features(weekly).to_numpy(dtype=float)
    n = len(close)
    valid = ~np.isnan(feat).any(axis=1)
    out = {f"score_{d}d": np.full(n, np.nan) for d in horizons}
    if valid.any():
        first = int(np.argmax(valid))
        for d, h in horizons.items():
            fwd = np.full(n, np.nan)
            fwd[:n - h] = (close[h:] / close[:n - h] - 1) * 100
            col = out[f"score_{d}d"]
            for t in range(first + MIN_ANALOGS + h, n):
                pool = feat[first:t - h + 1]
                sd = pool.std(axis=0)
                sd[sd == 0] = 1.0
                dist = (((pool - feat[t]) / sd) ** 2).sum(axis=1)
                kk = min(k, len(dist))
                nearest = np.argpartition(dist, kk - 1)[:kk]
                col[t] = np.nanmean(fwd[first:t - h + 1][nearest])
    return pd.DataFrame(out, index=weekly.index)


def analog_scores(prices: pd.DataFrame, k: int = K, horizons=HORIZON_WEEKS) -> pd.DataFrame:
    return analog_scores_weekly(_weekly_close(prices), k, horizons)


def _past_percentile(series: pd.Series) -> pd.Series:
    """Percentil af hver værdi blandt de foregående (kun fortid, rullende HISTORY_WEEKS)."""
    return series.rolling(HISTORY_WEEKS, min_periods=MIN_SCORE_HISTORY).apply(
        lambda w: (w[:-1] < w[-1]).mean() * 100, raw=True)


def analog_states(prices: pd.DataFrame, k: int = K) -> pd.DataFrame:
    """Samme form som tpi_states: long_green, short_pct (her scorepercentil 0–100), score og state."""
    weekly = _weekly_close(prices)
    scores = analog_scores_weekly(weekly, k)[f"score_{SCORE_HORIZON}d"]
    sma = weekly.rolling(LONG_WEEKS, min_periods=LONG_WEEKS).mean()
    long_green = (weekly > sma) & (sma > sma.shift(SLOPE_WEEKS))
    out = pd.DataFrame({"long_green": long_green, "short_pct": _past_percentile(scores), "score": scores}).dropna()
    out["long_green"] = out["long_green"].astype(bool)
    out["state"] = np.select([out["short_pct"] >= OVERSOLD_PCT, out["short_pct"] <= OVERBOUGHT_PCT],
                             ["oversolgt", "overkøbt"], default="neutral")
    return out


def state_returns(states: pd.DataFrame, prices: pd.DataFrame, horizons=(5, 20, 65, 130),
                  cost_pct: float = 0.1) -> pd.DataFrame:
    """Afkast pr. uge og tilstandsgruppe for vilkårlige tilstande (som tpi_lite.bucket_returns): signal ved ugens
    lukning, køb næste dags åbning, salg ved lukning efter h dage. Tilføjer slutdatoen end_<h>d."""
    daily = prices[["Open", "Close"]].apply(pd.to_numeric, errors="coerce").copy()
    index = pd.DatetimeIndex(pd.to_datetime(daily.index))
    daily.index = (index.tz_localize(None) if index.tz is not None else index).normalize()
    daily = daily[~daily.index.duplicated(keep="last")].sort_index().dropna()
    position = daily.index.searchsorted(states.index, side="right")
    rows = []
    for (week, row), start in zip(states.iterrows(), position):
        if start >= len(daily):
            continue
        rec = {"week": week, "long_green": bool(row["long_green"]), "state": row["state"],
               "group": f"{'lang grøn' if row['long_green'] else 'lang rød'} / {row['state']}"}
        entry = daily["Open"].iloc[start]
        for h in horizons:
            end = start + h - 1
            ok = end < len(daily)
            rec[f"{h}d"] = (daily["Close"].iloc[end] / entry - 1) * 100 - 2 * cost_pct if ok else np.nan
            rec[f"end_{h}d"] = daily.index[end] if ok else pd.NaT
        rows.append(rec)
    return pd.DataFrame(rows)
