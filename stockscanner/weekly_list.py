"""Mandagsliste: ugentlig gennemgang i MSS' rækkefølge (kvalitet → værdi → timing).

Køb-kandidat: StockMap-købssignal inden for de seneste `signal_weeks` uger, Quality-percentil ≥ 60,
kurs i nederste halvdel af værdikanalen (værdiscore i dag ≥ 50) og PEG < 2 når den kendes.
Salg: StockMap-salgssignal i den seneste uge. Alt andet: hold øje.
Bygget ud fra MSS' mandagsmail 02-11-2026 og videoerne. Screening, IKKE en købsanbefaling.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from stockscanner.stockmap import rotation, signals
from stockscanner.tpi_lite import tpi_states

MIN_QUALITY = 60.0
MIN_VALUE_SCORE = 50.0
MAX_PEG = 2.0


@dataclass(frozen=True)
class WeeklyRow:
    ticker: str
    action: str                 # "KØB-KANDIDAT", "SALG", "hold øje"
    stockmap: str               # seneste signal og uge
    quadrant: str | None
    angle: float | None
    tpi: str | None
    quality: float | None
    value_pct: float | None
    momentum: float | None
    channel_score: float | None
    peg: float | None
    reasons: str


def latest_signal(prices: pd.DataFrame, benchmark: pd.DataFrame, weeks: int) -> tuple[str, str | None, float | None]:
    """('køb 2026-10-30' / 'salg …' / '', kvadrant, vinkel) for de seneste `weeks` uger."""
    rot = rotation(prices, benchmark)
    if rot.empty:
        return "", None, None
    sig = signals(rot).tail(weeks)
    last = rot.iloc[-1]
    hits = sig[sig != ""]
    text = f"{hits.iloc[-1]} {hits.index[-1].date()}" if not hits.empty else ""
    return text, str(last["quadrant"]), None if pd.isna(last["angle"]) else float(last["angle"])


def classify(signal: str, last_week_sell: bool, quality, channel_score, peg) -> tuple[str, list[str]]:
    reasons = []
    if last_week_sell:
        return "SALG", ["StockMap-salg denne uge (gælder kun hvis ejet)"]
    if not signal.startswith("køb"):
        return "hold øje", ["intet StockMap-køb"]
    ok = True
    if quality is None or quality < MIN_QUALITY:
        ok = False; reasons.append(f"Quality {'–' if quality is None else round(quality)} < {MIN_QUALITY:.0f}")
    if channel_score is None or channel_score < MIN_VALUE_SCORE:
        ok = False; reasons.append(f"værdikanal {'–' if channel_score is None else round(channel_score)} < {MIN_VALUE_SCORE:.0f}")
    if peg is not None and peg >= MAX_PEG:
        ok = False; reasons.append(f"PEG {peg:.1f} ≥ {MAX_PEG:.0f}")
    return ("KØB-KANDIDAT" if ok else "hold øje"), (reasons or ["alle krav opfyldt"])


def build_rows(tickers, histories, benchmark, quality_pct, value_pct, momentum_pct, channels,
               signal_weeks: int = 2) -> list[WeeklyRow]:
    """Saml rækker; alle input er forudberegnede (dict/Series pr. ticker), så funktionen kan testes offline."""
    rows = []
    for ticker in tickers:
        prices = histories.get(ticker)
        if prices is None or prices.empty:
            continue
        signal, quadrant, angle = latest_signal(prices, benchmark, signal_weeks)
        recent, _, _ = latest_signal(prices, benchmark, 1)
        states = tpi_states(prices)
        tpi = None if states.empty else (f"{'grøn' if states['long_green'].iloc[-1] else 'rød'}/"
                                         f"{states['state'].iloc[-1]}")
        channel = channels.get(ticker)
        channel_score = None if channel is None else channel.score_today
        peg = None if channel is None else channel.peg
        quality = quality_pct.get(ticker)
        action, reasons = classify(signal, recent.startswith("salg"), quality, channel_score, peg)
        rows.append(WeeklyRow(ticker, action, signal or "–", quadrant, angle, tpi, quality,
                              value_pct.get(ticker), momentum_pct.get(ticker), channel_score, peg, "; ".join(reasons)))
    order = {"KØB-KANDIDAT": 0, "SALG": 1, "hold øje": 2}
    return sorted(rows, key=lambda r: (order[r.action], -(r.quality or 0)))
