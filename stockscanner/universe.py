"""Sammenligningsunivers til percentiler (byggeplan punkt 1).

MSS rangerer mod hele regionen; vi rangerer mod et cachet univers (`data/universe.txt`, ca. 300 aktier)
i stedet for kun mod den liste, der scannes. Faktorerne caches i `data/universe_factors.csv`.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

from stockscanner.quality import score_quality
from stockscanner.quality_rank import MOAT_METRICS, MSS_LIKE_METRICS, percentiles_from_tables
from stockscanner.scores import LOWER_IS_CHEAPER, momentum_factors, percentile_score, value_factors

ROOT = Path(__file__).resolve().parent.parent
UNIVERSE_FILE = ROOT / "data" / "universe.txt"
FACTORS_FILE = ROOT / "data" / "universe_factors.csv"
MAX_AGE_DAYS = 14


def read_tickers(path: Path = UNIVERSE_FILE) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


def factor_row(ticker: str, fundamentals_loader, info_loader, history_loader) -> dict:
    """Alle faktorer for én aktie: q_/qs_ (kvalitet værdi/point), v_ (værdi), m_ (momentum)."""
    row: dict = {"ticker": ticker}
    try:
        quality = score_quality(fundamentals_loader(ticker))
        row["financial"] = quality.is_financial
        for metric in quality.metrics:
            row[f"q_{metric.key}"] = metric.value
            row[f"qs_{metric.key}"] = metric.score
    except Exception:
        pass
    try:
        row.update({f"v_{k}": v for k, v in value_factors(info_loader(ticker)).items()})
    except Exception:
        pass
    try:
        history = history_loader(ticker)
        row.update({f"m_{k}": v for k, v in momentum_factors(history).items()})
        close = pd.to_numeric(history["Close"], errors="coerce").dropna()
        for days in (20, 50, 200):
            if len(close) >= days:
                row[f"b_above_{days}"] = bool(close.iloc[-1] > close.tail(days).mean())
    except Exception:
        pass
    return row


def breadth(universe: pd.DataFrame | None) -> dict[int, float]:
    """Markedsindeks: andel (%) af universet over SMA20/50/200. MSS/MarketTimer: over 50 = bull."""
    if universe is None:
        return {}
    out = {}
    for days in (20, 50, 200):
        column = f"b_above_{days}"
        if column in universe.columns:
            values = universe[column].dropna().astype(str).str.lower().map({"true": 1.0, "false": 0.0}).dropna()
            if len(values):
                out[days] = float(values.mean() * 100)
    return out


def build(tickers, fundamentals_loader, info_loader, history_loader, path: Path = FACTORS_FILE) -> pd.DataFrame:
    rows = []
    for i, ticker in enumerate(tickers, 1):
        rows.append(factor_row(ticker, fundamentals_loader, info_loader, history_loader))
        print(f"{i}/{len(tickers)} {ticker}", file=sys.stderr, flush=True)
    frame = pd.DataFrame(rows).set_index("ticker")
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, sep=";", encoding="utf-8-sig")
    return frame


def load(path: Path = FACTORS_FILE, max_age_days: int = MAX_AGE_DAYS) -> pd.DataFrame | None:
    """Cachet univers, eller None hvis det mangler eller er for gammelt."""
    if not path.exists() or (time.time() - path.stat().st_mtime) > max_age_days * 86400:
        return None
    return pd.read_csv(path, sep=";", encoding="utf-8-sig", index_col="ticker")


def percentiles(targets: pd.DataFrame, universe: pd.DataFrame | None) -> pd.DataFrame:
    """Quality/Value/Momentum-percentiler for `targets`, rangeret i targets + univers."""
    combined = targets if universe is None else pd.concat([universe.drop(index=targets.index, errors="ignore"), targets])
    pick = lambda prefix: combined[[c for c in combined.columns if c.startswith(prefix)]].rename(
        columns=lambda c: c[len(prefix):])
    qv, qs = pick("q_"), pick("qs_")
    keep = [k for k in MSS_LIKE_METRICS if k in qv.columns and k in qs.columns]
    quality = pd.Series(percentiles_from_tables(qv[keep], qs[keep]), dtype=float)
    moat_keys = [k for k in MOAT_METRICS if k in qv.columns and k in qs.columns]
    moat = pd.Series(percentiles_from_tables(qv[moat_keys], qs[moat_keys]), dtype=float)
    value = percentile_score(pick("v_"), LOWER_IS_CHEAPER)
    momentum = percentile_score(pick("m_"))
    out = pd.DataFrame({"quality": quality, "value": value, "momentum": momentum, "moat": moat})
    return out.reindex(targets.index)
