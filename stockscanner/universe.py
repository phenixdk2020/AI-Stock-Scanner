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
NORDIC_SUFFIXES = (".CO", ".ST", ".OL", ".HE", ".IC")
# Omtrentlige kurser til USD (nov. 2026); bruges kun når en live-kurs mangler. Kun til markedsværdi-grænser.
FX_TO_USD = {"USD": 1.0, "DKK": 0.155, "SEK": 0.095, "NOK": 0.092, "EUR": 1.16, "GBP": 1.33, "GBp": 0.0133,
             "CHF": 1.25, "ISK": 0.0075, "PLN": 0.27}
FACTORS_FILE = ROOT / "data" / "universe_factors.csv"
MAX_AGE_DAYS = 14


def read_tickers(path: Path = UNIVERSE_FILE) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


def region(ticker: str) -> str:
    """"USA" (intet suffiks), "Norden" eller "Europa" ud fra yfinance-suffikset."""
    if "." not in ticker:
        return "USA"
    return "Norden" if ticker.upper().endswith(NORDIC_SUFFIXES) else "Europa"


def trend_flags(history: pd.DataFrame) -> dict:
    """TPI-lite (lang trend, uge-tilstand) og enkle grøn-tilnærmelser til screenerne (t_-kolonner).
    Uge grøn: ugelukning over 10-ugers gennemsnit. Dag grøn: lukkekurs over 20-dages EMA."""
    from stockscanner.tpi_lite import _weekly_close, tpi_states

    row = {}
    close = pd.to_numeric(history["Close"], errors="coerce").dropna()
    states = tpi_states(history)
    if not states.empty:
        row["t_long_green"] = bool(states["long_green"].iloc[-1])
        row["t_week_state"] = str(states["state"].iloc[-1])
    weekly = _weekly_close(history)
    if len(weekly) >= 10:
        row["t_week_green"] = bool(weekly.iloc[-1] > weekly.tail(10).mean())
    if len(close) >= 50:
        row["t_day_green"] = bool(close.iloc[-1] > close.ewm(span=20, adjust=False).mean().iloc[-1])
        row["t_above_sma50"] = bool(close.iloc[-1] > close.tail(50).mean())
    return row


def info_extras(info: dict, fx_to_usd=None) -> dict:
    """Markedsværdi (også i USD), analytiker-upside og PEG fra yfinance `info` (x_-kolonner)."""
    fx_to_usd = fx_to_usd or (lambda currency: FX_TO_USD.get(currency))
    row = {}
    cap, currency = info.get("marketCap"), info.get("currency")
    if cap:
        row["x_mcap"], row["x_currency"] = float(cap), currency
        rate = fx_to_usd(currency) if currency else None
        if rate:
            row["x_mcap_usd"] = float(cap) * rate
    price, target = info.get("currentPrice") or info.get("regularMarketPrice"), info.get("targetMeanPrice")
    if price and target:
        row["x_upside"] = (float(target) / float(price) - 1) * 100
    peg = info.get("trailingPegRatio")
    if peg is not None and peg == peg and peg > 0:
        row["x_peg"] = float(peg)
    return row


def factor_row(ticker: str, fundamentals_loader, info_loader, history_loader, fx_to_usd=None) -> dict:
    """Alle faktorer for én aktie: q_/qs_ (kvalitet værdi/point), v_ (værdi), m_ (momentum),
    b_ (markedsindeks), t_ (trend til screenerne), x_ (markedsværdi, upside, PEG)."""
    row: dict = {"ticker": ticker, "region": region(ticker)}
    try:
        quality = score_quality(fundamentals_loader(ticker))
        row["financial"] = quality.is_financial
        for metric in quality.metrics:
            row[f"q_{metric.key}"] = metric.value
            row[f"qs_{metric.key}"] = metric.score
    except Exception:
        pass
    try:
        info = info_loader(ticker)
        row.update({f"v_{k}": v for k, v in value_factors(info).items()})
        row.update(info_extras(info, fx_to_usd))
    except Exception:
        pass
    try:
        history = history_loader(ticker)
        row.update({f"m_{k}": v for k, v in momentum_factors(history).items()})
        close = pd.to_numeric(history["Close"], errors="coerce").dropna()
        for days in (20, 50, 200):
            if len(close) >= days:
                row[f"b_above_{days}"] = bool(close.iloc[-1] > close.tail(days).mean())
        row.update(trend_flags(history))
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


def build(tickers, fundamentals_loader, info_loader, history_loader, path: Path = FACTORS_FILE,
          fx_to_usd=None) -> pd.DataFrame:
    rows = []
    for i, ticker in enumerate(tickers, 1):
        rows.append(factor_row(ticker, fundamentals_loader, info_loader, history_loader, fx_to_usd))
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


def percentiles(targets: pd.DataFrame, universe: pd.DataFrame | None, by_region: bool = False) -> pd.DataFrame:
    """Quality/Value/Momentum/Moat-percentiler for `targets`, rangeret i targets + univers.
    `by_region`: rangér kun mod aktier fra samme region (USA/Norden/Europa), som MSS gør (B-19)."""
    combined = targets if universe is None else pd.concat([universe.drop(index=targets.index, errors="ignore"), targets])
    if not by_region:
        return _ranked(combined).reindex(targets.index)
    regions = pd.Series([region(t) for t in combined.index], index=combined.index)
    parts = [_ranked(combined[regions == name]) for name in regions.unique()]
    return pd.concat(parts).reindex(targets.index)


def _ranked(combined: pd.DataFrame) -> pd.DataFrame:
    pick = lambda prefix: combined[[c for c in combined.columns if c.startswith(prefix)]].rename(
        columns=lambda c: c[len(prefix):])
    qv, qs = pick("q_"), pick("qs_")
    keep = [k for k in MSS_LIKE_METRICS if k in qv.columns and k in qs.columns]
    quality = pd.Series(percentiles_from_tables(qv[keep], qs[keep]), dtype=float)
    moat_keys = [k for k in MOAT_METRICS if k in qv.columns and k in qs.columns]
    moat = pd.Series(percentiles_from_tables(qv[moat_keys], qs[moat_keys]), dtype=float)
    value = percentile_score(pick("v_"), LOWER_IS_CHEAPER)
    momentum = percentile_score(pick("m_"))
    return pd.DataFrame({"quality": quality, "value": value, "momentum": momentum, "moat": moat})
