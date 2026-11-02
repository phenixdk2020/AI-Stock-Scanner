"""Positionsstørrelse (B-09) efter MSS/MarketTimer "Styr din risiko":
risiko pr. handel 0,5–1 % af kapitalen, stop = kurs − 3 × ATR(14), højst ca. 3 % af kapitalen i én aktie.
Indstillinger i `data/indstillinger.json` (rettes på Streamlit-siden). Screening, IKKE rådgivning.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from stockscanner.universe import FX_TO_USD

SETTINGS_FILE = Path(__file__).resolve().parent.parent / "data" / "indstillinger.json"
DEFAULTS = {"kapital": 100000.0, "valuta": "DKK", "risiko_pct": 0.75, "max_pct": 3.0, "atr_gange": 3.0}


@dataclass(frozen=True)
class Size:
    shares: int
    stop: float
    amount: float          # købsbeløb i kapitalens valuta
    risk: float            # tab ved stop i kapitalens valuta


def load_settings(path: Path = SETTINGS_FILE) -> dict:
    settings = dict(DEFAULTS)
    if path.exists():
        try:
            settings.update(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return settings


def save_settings(settings: dict, path: Path = SETTINGS_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def atr(prices: pd.DataFrame, days: int = 14) -> float | None:
    high, low, close = (pd.to_numeric(prices[c], errors="coerce") for c in ("High", "Low", "Close"))
    true_range = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    value = true_range.rolling(days).mean().iloc[-1] if len(true_range) > days else None
    return None if value is None or pd.isna(value) else float(value)


def position_size(price: float, atr_value: float | None, settings: dict, fx: float = 1.0) -> Size | None:
    """Antal aktier ud fra risiko og loft. `fx`: kapitalvaluta pr. enhed af aktiens valuta."""
    if not price or not atr_value or price <= 0 or atr_value <= 0:
        return None
    stop = price - settings["atr_gange"] * atr_value
    if stop <= 0:
        return None
    capital = float(settings["kapital"])
    by_risk = capital * settings["risiko_pct"] / 100 / ((price - stop) * fx)
    by_cap = capital * settings["max_pct"] / 100 / (price * fx)
    shares = int(math.floor(min(by_risk, by_cap)))
    return Size(shares, stop, shares * price * fx, shares * (price - stop) * fx)


def fx_rate(from_currency: str | None, to_currency: str) -> float | None:
    """Omregning via de omtrentlige USD-kurser i universe.FX_TO_USD."""
    if not from_currency:
        return None
    a, b = FX_TO_USD.get(from_currency), FX_TO_USD.get(to_currency)
    return None if not a or not b else a / b
