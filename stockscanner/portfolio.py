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


def valuation(positions: dict[str, Position], quotes: dict[str, tuple]) -> pd.DataFrame:
    """Kurs, værdi, gevinst siden køb og siden i går pr. ejet aktie.
    `quotes`: ticker → (seneste kurs, valuta[, gårsdagens lukkekurs])."""
    rows = []
    for ticker, position in positions.items():
        price, currency, previous = (tuple(quotes.get(ticker, ())) + (None, None, None))[:3]
        value = None if price is None else price * position.shares
        cost = position.buy_price * position.shares
        rows.append({"ticker": ticker, "valuta": currency, "antal": position.shares,
                     "koebskurs": position.buy_price, "kurs": price, "vaerdi": value,
                     "gevinst": None if value is None else value - cost,
                     "gevinst_pct": None if price is None or position.buy_price <= 0
                     else (price / position.buy_price - 1) * 100,
                     "dag": None if price is None or not previous else (price - previous) * position.shares,
                     "dag_pct": None if price is None or not previous else (price / previous - 1) * 100})
    return pd.DataFrame(rows, columns=["ticker", "valuta", "antal", "koebskurs", "kurs", "vaerdi",
                                       "gevinst", "gevinst_pct", "dag", "dag_pct"])


def fetch_quotes(tickers) -> dict[str, tuple]:
    """Seneste kurs, valuta og gårsdagens lukkekurs fra yfinance; fejl giver (None, None, None)."""
    import yfinance as yf

    quotes = {}
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).fast_info
            previous = info["previous_close"]
            quotes[ticker] = (float(info["last_price"]), info["currency"],
                              None if previous is None else float(previous))
        except Exception:
            quotes[ticker] = (None, None, None)
    return quotes
