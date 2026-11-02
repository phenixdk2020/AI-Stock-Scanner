"""Egen portefølje (byggeplan punkt 2): salgsregler gælder kun aktier, man ejer.

`data/portfolio.csv` (semikolon): ticker;antal;koebskurs;koebsdato (ÅÅÅÅ-MM-DD).
Salgsregler fra punkt 9-testen: Supertrend ×3 vender ned (mest robust), brud under SMA50 og
StockMap-salg. Screening, IKKE en salgsanbefaling.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from stockscanner.exits import exit_signals, supertrend

PORTFOLIO_FILE = Path(__file__).resolve().parent.parent / "data" / "portfolio.csv"


@dataclass(frozen=True)
class Position:
    ticker: str
    shares: float
    buy_price: float
    buy_date: date


def load_portfolio(path: Path = PORTFOLIO_FILE) -> dict[str, Position]:
    if not path.exists():
        return {}
    frame = pd.read_csv(path, sep=";", encoding="utf-8-sig", comment="#")
    positions = {}
    for _, row in frame.iterrows():
        ticker = str(row["ticker"]).strip()
        if not ticker:
            continue
        positions[ticker] = Position(ticker, float(row.get("antal", 0) or 0), float(row["koebskurs"]),
                                     pd.Timestamp(row["koebsdato"]).date())
    return positions


def exit_check(prices: pd.DataFrame, position: Position, stockmap_sell: bool) -> list[str]:
    """Aktive salgsgrunde for en ejet aktie: brud siden købsdatoen eller nuværende tilstand."""
    reasons = []
    since = pd.Timestamp(position.buy_date)
    signals = exit_signals(prices)
    recent = signals[signals.index >= since]
    up = supertrend(prices, 10, 3.0)
    if not up.empty and not bool(up.iloc[-1]):
        reasons.append("Supertrend ×3 er vendt ned")
    if not recent.empty and recent["SMA50"].any():
        reasons.append(f"brud under SMA50 ({recent.index[recent['SMA50']][-1].date()})")
    if stockmap_sell:
        reasons.append("StockMap-salg denne uge")
    return reasons


def profit_pct(prices: pd.DataFrame, position: Position) -> float | None:
    close = pd.to_numeric(prices["Close"], errors="coerce").dropna()
    if close.empty or position.buy_price <= 0:
        return None
    return float((close.iloc[-1] / position.buy_price - 1) * 100)
