"""Kursdata fra yfinance (uofficiel Yahoo Finance-integration)."""
from __future__ import annotations

import pandas as pd
import yfinance as yf


def fetch_history(symbol: str, period: str = "2y") -> tuple[pd.DataFrame, str]:
    """Hent justerede dagskurser (standard to år). Ingen betalt API-nøgle."""
    ticker = yf.Ticker(symbol)
    history = ticker.history(period=period, interval="1d", auto_adjust=True, actions=False)
    if history is None or history.empty:
        raise ValueError(f"{symbol}: ingen kursdata fra udbyderen.")
    # Defensiv understøttelse, hvis udbyderen ændrer kolonneformat.
    if isinstance(history.columns, pd.MultiIndex):
        history.columns = history.columns.get_level_values(0)
    currency = ""
    try:
        currency = str(ticker.fast_info.get("currency") or "")
    except Exception:
        pass
    return history, currency
