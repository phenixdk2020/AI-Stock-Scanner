"""Kvalitet som percentil mod et univers (byggeplan punkt 3), som MSS' Quality-score.

MSS rangerer hvert delmål 1–100 inden for land/region med lige vægt (webinar "Stock Scores").
Vi rangerer vores egne nøgletal fra `quality.score_quality` på samme måde. Kalibreret 02-11-2026
mod 115 høstede danske MSS-scorer: rangkorrelation 0,73 (begge halvdele 0,72), gns. afvigelse 16 point.
Screening, IKKE en købsanbefaling.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from stockscanner.quality import QualityResult

# Delmål der minder om MSS' Quality-områder; current ratio, bruttomargin, driftsmargin og
# omsætningsvækst ramte MSS dårligt (rangkorr 0,21 eller lavere) og indgår ikke.
MSS_LIKE_METRICS = (
    "roce", "roic", "interest_coverage", "roa", "piotroski", "fcf_margin", "roe",
    "margin_stability", "cash_conversion", "altman_z", "net_debt_ebitda",
)


# Moat-tilnærmelse: delmål der bedst rangerer som MSS' Moat-score (131 høstede danske aktier,
# 02-11-2026: rangkorrelation 0,70; MSS' egen Quality mod Moat er kun 0,48).
MOAT_METRICS = ("fcf_margin", "roe", "operating_margin", "interest_coverage", "revenue_cagr")


def mss_score(quality: float | None, channel_score: float | None, moat: float | None) -> float | None:
    """MSS-score = gennemsnit af Quality, værdiansættelse (kanalscore afskåret til 0–100) og Moat
    (bekræftet på 109 høstede aktier). None hvis noget mangler."""
    if quality is None or channel_score is None or moat is None:
        return None
    return (quality + min(max(channel_score, 0.0), 100.0) + moat) / 3


def quality_percentiles(results: list[QualityResult], metrics=MSS_LIKE_METRICS,
                        min_share: float = 0.5) -> dict[str, float]:
    """Percentil 0–100 pr. ticker: gennemsnit af delmålenes percentiler, rangeret igen.

    Retningen (højere = bedre) tages fra vores egen pointgivning for delmålet. Aktier med
    færre end `min_share` af delmålene får ingen score.
    """
    values = pd.DataFrame({r.ticker: {m.key: m.value for m in r.metrics if m.key in metrics} for r in results}).T
    scores = pd.DataFrame({r.ticker: {m.key: m.score for m in r.metrics if m.key in metrics} for r in results}).T
    return percentiles_from_tables(values, scores, min_share)


def percentiles_from_tables(values: pd.DataFrame, scores: pd.DataFrame, min_share: float = 0.5) -> dict[str, float]:
    """Som `quality_percentiles`, men på tabeller (række = ticker, kolonne = delmål), fx et cachet univers."""
    if values.empty:
        return {}
    ranks = {}
    for key in values.columns:
        value = pd.to_numeric(values[key], errors="coerce")
        score = pd.to_numeric(scores.get(key), errors="coerce")
        both = value.notna() & score.notna()
        if both.sum() < 3:
            continue
        direction = np.sign(value[both].rank().corr(score[both].rank()))
        ranks[key] = ((direction if direction != 0 and not np.isnan(direction) else 1) * value).rank(pct=True) * 100
    if not ranks:
        return {}
    table = pd.DataFrame(ranks)
    enough = table.notna().sum(axis=1) >= max(1, int(np.ceil(min_share * len(table.columns))))
    combined = table.mean(axis=1).where(enough).rank(pct=True) * 100
    return {ticker: float(value) for ticker, value in combined.dropna().items()}
