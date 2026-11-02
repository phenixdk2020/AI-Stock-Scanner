"""Screenere over universet (B-04–B-06), bygget efter MSS' tragte i videoerne (dok. 9.6).

Triple Green [TRG]: TPI lang + uge + dag grønne (uge ikke overkøbt), kurs over 50-dages snit, markedsværdi ≥ 2 mia. USD.
TPI-trend [TPK/LTP]: lang grøn + uge oversolgt, Norden, markedsværdi ≥ 3 mia. USD (≈ 20–25 mia. DKK/SEK).
Stock of the Day [SS24/W24]: USA, lang grøn + uge oversolgt, Quality og Value ≥ 60, PEG < 3,
  mindst 10 % op til analytikernes kursmål, markedsværdi ≥ 10 mia. USD; sorteret efter stock score.
"Grøn" for uge og dag er vores tilnærmelse (se universe.trend_flags); MSS' egne formler er hemmelige.
Screening, IKKE købsanbefalinger.
"""
from __future__ import annotations

import pandas as pd

SCREENERS = {
    "triple-green": "Triple Green: lang + uge + dag grøn, over SMA50, ≥ 2 mia. USD",
    "tpi-trend": "TPI-trend: lang grøn + uge oversolgt, Norden, ≥ 3 mia. USD",
    "stock-of-the-day": "Stock of the Day: USA, lang grøn + uge oversolgt, Q/V ≥ 60, PEG < 3, upside ≥ 10 %, ≥ 10 mia. USD",
}


def _flag(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index)
    return frame[column].astype(str).str.lower().eq("true")


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(float("nan"), index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce")


def screen(name: str, factors: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    """Hits for én screener. `factors`: universets faktorer (index = ticker); `scores`: percentiler
    (quality/value/momentum/moat) for samme tickers. Returnerer de relevante kolonner, bedste først."""
    if name not in SCREENERS:
        raise ValueError(f"ukendt screener: {name}")
    frame = factors.join(scores, how="left")
    cap = _num(frame, "x_mcap_usd")
    long_green = _flag(frame, "t_long_green")
    week_state = frame.get("t_week_state", pd.Series("", index=frame.index)).astype(str)
    oversold, overbought = week_state.eq("oversolgt"), week_state.eq("overkøbt")
    regions = frame.get("region", pd.Series("", index=frame.index)).astype(str)
    if name == "triple-green":
        # grå (overkøbt) tæller ikke som grøn hos MSS
        mask = long_green & _flag(frame, "t_week_green") & _flag(frame, "t_day_green") \
            & _flag(frame, "t_above_sma50") & ~overbought & (cap >= 2e9)
    elif name == "tpi-trend":
        mask = long_green & oversold & regions.eq("Norden") & (cap >= 3e9)
    else:
        peg = _num(frame, "x_peg")
        mask = (long_green & oversold & regions.eq("USA") & (cap >= 10e9)
                & (_num(frame, "quality") >= 60) & (_num(frame, "value") >= 60)
                & (_num(frame, "x_upside") >= 10) & (peg.isna() | (peg < 3)))
    hits = frame[mask].copy()
    hits["stock_score"] = hits[[c for c in ("quality", "value", "momentum") if c in hits.columns]].mean(axis=1)
    hits["mcap_mia_usd"] = _num(hits, "x_mcap_usd") / 1e9
    columns = [c for c in ("region", "stock_score", "quality", "value", "momentum", "moat", "x_upside", "x_peg",
                           "mcap_mia_usd", "t_week_state") if c in hits.columns]
    return hits.sort_values("stock_score", ascending=False)[columns]
