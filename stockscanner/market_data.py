"""Kursdata fra yfinance (uofficiel Yahoo Finance-integration)."""
from __future__ import annotations

import time

import pandas as pd
import yfinance as yf


RETRY_WAITS = (10, 30)   # sekunder; Yahoo svarer tomt ved midlertidig begrænsning (HTTP 429)


def fetch_history(symbol: str, period: str = "2y") -> tuple[pd.DataFrame, str]:
    """Hent justerede dagskurser (standard to år). Ingen betalt API-nøgle.
    Et tomt svar prøves igen med pause, så en midlertidig begrænsning ikke stopper mandagslisten."""
    ticker = yf.Ticker(symbol)
    for wait in (*RETRY_WAITS, None):
        history = ticker.history(period=period, interval="1d", auto_adjust=True, actions=False)
        if history is not None and not history.empty:
            break
        if wait is None:
            raise ValueError(f"{symbol}: ingen kursdata fra udbyderen.")
        time.sleep(wait)
    # Defensiv understøttelse, hvis udbyderen ændrer kolonneformat.
    if isinstance(history.columns, pd.MultiIndex):
        history.columns = history.columns.get_level_values(0)
    currency = ""
    try:
        currency = str(ticker.fast_info.get("currency") or "")
    except Exception:
        pass
    return history, currency
