"""Gennemsigtig teknisk scoring af daglige OHLCV-kurser.

Score er et teknisk screeningssignal, IKKE en købsanbefaling.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re

import pandas as pd


DEFAULT_TICKERS = ["NOVO-B.CO", "DSV.CO", "VWS.CO", "MSFT", "NVDA", "AAPL"]

WEIGHTS = {
    "Kurs over SMA50": 20,
    "SMA50 over SMA200": 20,
    "RSI mellem 45 og 70": 20,
    "MACD over signallinje": 20,
    "Positivt 21-dages afkast": 10,
    "Volumen mindst 20-dages gennemsnit": 10,
}


@dataclass(frozen=True)
class ScanResult:
    ticker: str
    market_date: str
    price: float
    currency: str
    change_21d_pct: float
    sma50: float
    sma200: float
    rsi14: float
    macd: float
    macd_signal: float
    relative_volume: float | None
    score: int
    signal: str
    checks: dict[str, bool]


def parse_tickers(raw: str, max_count: int = 50) -> list[str]:
    """Accepter komma, semikolon, linjeskift eller mellemrum og fjern dubletter."""
    tickers: list[str] = []
    for symbol in re.split(r"[\s,;]+", raw.upper().strip()):
        if not symbol:
            continue
        if not re.fullmatch(r"[A-Z0-9^][A-Z0-9.^=-]{0,19}", symbol):
            raise ValueError(f"Ugyldigt aktiesymbol: {symbol}")
        if symbol not in tickers:
            tickers.append(symbol)
    if not tickers:
        raise ValueError("Angiv mindst ét aktiesymbol.")
    if len(tickers) > max_count:
        raise ValueError(f"Maksimalt {max_count} aktier pr. scanning.")
    return tickers


def analyze_prices(prices: pd.DataFrame, ticker: str, currency: str = "") -> ScanResult:
    """Beregn indikatorer uden fremadskuende data (kun historiske dagskurser).

    Kræver mindst 200 valide lukkekurser. Manglende volumen giver ikke bonuspoint.
    """
    if "Close" not in prices.columns:
        raise ValueError(f"{ticker}: mangler Close-kolonne.")
    close = pd.to_numeric(prices["Close"], errors="coerce")
    close = close.replace([float("inf"), float("-inf")], float("nan")).dropna()
    if len(close) < 200:
        raise ValueError(f"{ticker}: kun {len(close)} handelsdage; mindst 200 kræves.")
    if bool((close <= 0).any()):
        raise ValueError(f"{ticker}: ugyldige lukkekurser.")

    volume_source = prices["Volume"] if "Volume" in prices.columns else pd.Series(0, index=prices.index)
    volume = pd.to_numeric(volume_source, errors="coerce").reindex(close.index).fillna(0).clip(lower=0)

    sma50 = float(close.rolling(50).mean().iloc[-1])
    sma200 = float(close.rolling(200).mean().iloc[-1])
    delta = close.diff()
    avg_gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    avg_loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    gain, loss = float(avg_gain.iloc[-1]), float(avg_loss.iloc[-1])
    if loss == 0:
        rsi = 50.0 if gain == 0 else 100.0
    else:
        rsi = 100 - 100 / (1 + gain / loss)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_series = ema12 - ema26
    signal_series = macd_series.ewm(span=9, adjust=False).mean()
    macd = float(macd_series.iloc[-1])
    macd_signal = float(signal_series.iloc[-1])

    last_price = float(close.iloc[-1])
    change_21d_pct = (last_price / float(close.iloc[-22]) - 1) * 100
    average_volume = float(volume.tail(20).mean())
    relative_volume = float(volume.iloc[-1] / average_volume) if average_volume > 0 else None

    checks = {
        "Kurs over SMA50": last_price > sma50,
        "SMA50 over SMA200": sma50 > sma200,
        "RSI mellem 45 og 70": 45 <= rsi <= 70,
        "MACD over signallinje": macd > macd_signal,
        "Positivt 21-dages afkast": change_21d_pct > 0,
        "Volumen mindst 20-dages gennemsnit": relative_volume is not None and relative_volume >= 1,
    }
    score = sum(weight for name, weight in WEIGHTS.items() if checks[name])
    signal = "Interessant" if score >= 80 else "Hold øje" if score >= 60 else "Afvent"
    market_date = str(pd.to_datetime(close.index[-1]).date())
    metrics = [last_price, change_21d_pct, sma50, sma200, rsi, macd, macd_signal]
    if not all(math.isfinite(x) for x in metrics):
        raise ValueError(f"{ticker}: ufuldstændige indikatorer.")
    return ScanResult(
        ticker=ticker,
        market_date=market_date,
        price=last_price,
        currency=currency,
        change_21d_pct=change_21d_pct,
        sma50=sma50,
        sma200=sma200,
        rsi14=rsi,
        macd=macd,
        macd_signal=macd_signal,
        relative_volume=relative_volume,
        score=score,
        signal=signal,
        checks=checks,
    )
