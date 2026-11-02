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


def quality_percentiles(results: list[QualityResult], metrics=MSS_LIKE_METRICS,
                        min_share: float = 0.5) -> dict[str, float]:
    """Percentil 0–100 pr. ticker: gennemsnit af delmålenes percentiler, rangeret igen.

    Retningen (højere = bedre) tages fra vores egen pointgivning for delmålet. Aktier med
    færre end `min_share` af delmålene får ingen score.
    """
    values = pd.DataFrame({r.ticker: {m.key: m.value for m in r.metrics if m.key in metrics} for r in results}).T
    scores = pd.DataFrame({r.ticker: {m.key: m.score for m in r.metrics if m.key in metrics} for r in results}).T
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
