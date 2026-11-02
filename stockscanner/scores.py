"""Value- og Momentum-score som percentiler i et univers (byggeplan punkt 2), som MSS' Stock Scores.

MSS (webinar "Stock Scores", "Profitable strategier"): hver faktor rangeres 1–100 inden for land/region
med lige vægt. Value: P/E, P/B, P/FCF, udbytte, P/S, EV/EBITDA (billig = høj). Momentum: afkast over
1, 3, 6 og 12 måneder med vægt på stabilitet. Vi bruger samme faktorer på yfinance-data; momentum-
stabilitet = andel positive måneder det seneste år. Quality ligger i `quality_rank`.
Screening, IKKE en købsanbefaling.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

VALUE_FACTORS = ("pe", "pb", "pfcf", "dividend_yield", "ps", "ev_ebitda")
LOWER_IS_CHEAPER = {"pe", "pb", "pfcf", "ps", "ev_ebitda"}
MOMENTUM_MONTHS = (1, 3, 6, 12)


def value_factors(info: dict) -> dict[str, float | None]:
    """Værdifaktorer fra et yfinance `info`-dict. Negative eller manglende multipler bliver None."""
    def positive(value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        return value if np.isfinite(value) and value > 0 else None

    cap, fcf = positive(info.get("marketCap")), positive(info.get("freeCashflow"))
    dividend = info.get("dividendYield")
    try:
        dividend = float(dividend) if dividend is not None else 0.0
    except (TypeError, ValueError):
        dividend = None
    return {
        "pe": positive(info.get("trailingPE")),
        "pb": positive(info.get("priceToBook")),
        "pfcf": cap / fcf if cap and fcf else None,
        "dividend_yield": dividend,
        "ps": positive(info.get("priceToSalesTrailing12Months")),
        "ev_ebitda": positive(info.get("enterpriseToEbitda")),
    }


def momentum_factors(prices: pd.DataFrame) -> dict[str, float | None]:
    """Afkast over 1/3/6/12 måneder (21 handelsdage pr. måned) og andel positive måneder i et år."""
    close = pd.to_numeric(prices["Close"], errors="coerce").dropna()
    out: dict[str, float | None] = {}
    for months in MOMENTUM_MONTHS:
        days = 21 * months
        out[f"ret_{months}m"] = float(close.iloc[-1] / close.iloc[-1 - days] - 1) if len(close) > days else None
    if len(close) > 252:
        monthly = close.iloc[-253::21].pct_change().dropna()
        out["stability"] = float((monthly > 0).mean())
    else:
        out["stability"] = None
    return out


def percentile_score(table: pd.DataFrame, lower_is_better=frozenset(), min_share: float = 0.5) -> pd.Series:
    """Lige vægtet gennemsnit af faktor-percentiler, rangeret igen til 0–100."""
    ranks = {}
    for column in table.columns:
        values = pd.to_numeric(table[column], errors="coerce")
        if values.notna().sum() < 3:
            continue
        ranks[column] = (-values if column in lower_is_better else values).rank(pct=True) * 100
    if not ranks:
        return pd.Series(dtype=float)
    frame = pd.DataFrame(ranks)
    enough = frame.notna().sum(axis=1) >= max(1, int(np.ceil(min_share * frame.shape[1])))
    return (frame.mean(axis=1).where(enough).rank(pct=True) * 100).dropna()


def value_scores(infos: dict[str, dict]) -> pd.Series:
    table = pd.DataFrame({ticker: value_factors(info) for ticker, info in infos.items()}).T
    return percentile_score(table, LOWER_IS_CHEAPER)


def momentum_scores(histories: dict[str, pd.DataFrame]) -> pd.Series:
    table = pd.DataFrame({ticker: momentum_factors(prices) for ticker, prices in histories.items()}).T
    return percentile_score(table)
