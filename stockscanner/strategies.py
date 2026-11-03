"""De fire MSS-algostrategier (B-10): Quality Momentum, TPI Plus, Value Momentum og Value Quality.

MSS (månedsvideo): hver måned (første handelsdag) købes de 15 øverste efter strategiens rang, lige vægt,
og hvad der falder ud sælges; man kan vælge 5 i stedet for 15. Benchmark RSP, ca. 1,5 %/år i handelsomkostninger.
Her kun rene rangeringsfunktioner (ingen netværk) fra en faktortabel: percentilerne quality/value/momentum
fra `universe.percentiles` og TPI-lite-tilstanden `t_week_state` (+ `t_long_green`) fra univers-cachen.
  Quality Momentum : høj quality OG høj momentum (gennemsnit af de to percentiler)
  TPI Plus         : høj quality (≥ 60) OG TPI-lite oversolgt i lang optrend; rangeret efter quality
  Value Momentum   : LAV value-score og høj momentum ("omvendt value": dyre vindere), (100 − value + momentum)/2
  Value Quality    : høj value OG høj quality (gennemsnit)
Mangler en af de nødvendige faktorer, er aktien ikke med. Quality/Value kan IKKE bagtestes ærligt (ingen
point-in-time-regnskaber); modulet bruges til fremadrettet papirsporing (scripts/strategies_monthly.py).
Reglerne er vores tolkning af MSS' korte beskrivelse, IKKE deres formel. Screening, IKKE en købsanbefaling.
"""
from __future__ import annotations

import pandas as pd

TOP_N = 15
MIN_QUALITY_TPI = 60.0
STRATEGIES = ("quality_momentum", "tpi_plus", "value_momentum", "value_quality")
LABELS = {"quality_momentum": "Quality Momentum", "tpi_plus": "TPI Plus",
          "value_momentum": "Value Momentum", "value_quality": "Value Quality"}


def factor_table(universe: pd.DataFrame) -> pd.DataFrame:
    """Percentiler (quality, value, momentum) rangeret i hele universet + TPI-kolonner (tpi_state, long_green)."""
    from stockscanner.universe import percentiles

    table = percentiles(universe, None).copy()
    table["tpi_state"] = universe["t_week_state"] if "t_week_state" in universe.columns else None
    table["long_green"] = (universe["t_long_green"].astype(str).str.lower() == "true"
                           if "t_long_green" in universe.columns else False)
    return table


def _num(table: pd.DataFrame, column: str) -> pd.Series:
    if column in table.columns:
        return pd.to_numeric(table[column], errors="coerce")
    return pd.Series(float("nan"), index=table.index)


def _top(score: pd.Series, top_n: int) -> pd.DataFrame:
    ranked = score.dropna().sort_values(ascending=False, kind="mergesort")
    return ranked.head(top_n).rename("score").to_frame().rename_axis("ticker")


def quality_momentum(table: pd.DataFrame, top_n: int = TOP_N) -> pd.DataFrame:
    return _top((_num(table, "quality") + _num(table, "momentum")) / 2, top_n)


def tpi_plus(table: pd.DataFrame, top_n: int = TOP_N, min_quality: float = MIN_QUALITY_TPI) -> pd.DataFrame:
    """Kan give færre end `top_n`: kun aktier med quality ≥ grænsen, oversolgt og lang trend grøn."""
    state = table["tpi_state"].astype(str) if "tpi_state" in table.columns else pd.Series("", index=table.index)
    green = table["long_green"].astype(bool) if "long_green" in table.columns else pd.Series(False, index=table.index)
    quality = _num(table, "quality")
    return _top(quality.where((state == "oversolgt") & green & (quality >= min_quality)), top_n)


def value_momentum(table: pd.DataFrame, top_n: int = TOP_N) -> pd.DataFrame:
    return _top(((100 - _num(table, "value")) + _num(table, "momentum")) / 2, top_n)


def value_quality(table: pd.DataFrame, top_n: int = TOP_N) -> pd.DataFrame:
    return _top((_num(table, "value") + _num(table, "quality")) / 2, top_n)


RANKERS = {"quality_momentum": quality_momentum, "tpi_plus": tpi_plus,
           "value_momentum": value_momentum, "value_quality": value_quality}


def rank_all(universe: pd.DataFrame, top_n: int = TOP_N) -> dict[str, pd.DataFrame]:
    """Alle fire strategiers valg fra univers-cachen (`universe.load()`)."""
    table = factor_table(universe)
    return {name: RANKERS[name](table, top_n) for name in STRATEGIES}
