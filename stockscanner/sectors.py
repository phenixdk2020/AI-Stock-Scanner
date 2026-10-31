"""Watchlist-only sector rotation overview, inspired by sector-first screening.

This is NOT a full-market sector index or net institutional money flow.
All metrics derive from the user's scanned symbols.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from stockscanner.core import ScanResult
from stockscanner.markets import market_of

SECTORS = {
    "NOVO-B.CO": "Sundhed", "DSV.CO": "Transport", "VWS.CO": "Industri",
    "MAERSK-B.CO": "Transport",
    "SAP.DE": "Teknologi", "SIE.DE": "Industri",
    "ALV.DE": "Finans", "BMW.DE": "Biler",
    "VOLV-B.ST": "Industri", "ATCO-A.ST": "Industri",
    "ERIC-B.ST": "Teknologi", "INVE-B.ST": "Finans",
    "EQNR.OL": "Energi", "DNB.OL": "Finans",
    "NHY.OL": "Materialer", "MOWI.OL": "Fødevarer",
    "MSFT": "Teknologi", "NVDA": "Teknologi",
    "AAPL": "Teknologi", "GOOGL": "Teknologi",
}


@dataclass(frozen=True)
class SectorSignal:
    market: str
    sector: str
    symbols: str
    count: int
    avg_score: float
    avg_21d_pct: float
    avg_relative_volume: float | None
    uptrend_percent: float
    status: str


def group_sectors(results: list[ScanResult]) -> list[SectorSignal]:
    groups: dict[tuple[str, str], list[ScanResult]] = defaultdict(list)
    for item in results:
        groups[market_of(item.ticker), SECTORS.get(item.ticker.upper(), "Ikke kategoriseret")].append(item)

    summaries = []
    for (market, sector), records in groups.items():
        count = len(records)
        mean_score = sum(r.score for r in records) / count
        mean_change = sum(r.change_21d_pct for r in records) / count
        usable_volumes = [r.relative_volume for r in records if r.relative_volume is not None]
        mean_volume = sum(usable_volumes) / len(usable_volumes) if usable_volumes else None
        uptrend_share = sum(r.price > r.sma50 for r in records) / count
        if mean_change >= 35:
            status = "Muligt overophedet"
        elif mean_change > 5 and uptrend_share >= 0.6 and mean_volume is not None and mean_volume >= 1.1:
            status = "Styrke"
        elif mean_change < -5 and uptrend_share <= 0.4:
            status = "Under pres"
        else:
            status = "Blandet"
        summaries.append(SectorSignal(
            market=market, sector=sector,
            symbols=", ".join(sorted(r.ticker for r in records)),
            count=count, avg_score=round(mean_score, 1),
            avg_21d_pct=round(mean_change, 2),
            avg_relative_volume=round(mean_volume, 2) if mean_volume is not None else None,
            uptrend_percent=round(uptrend_share * 100, 1),
            status=status,
        ))
    return sorted(summaries, key=lambda s: (-s.avg_score, s.market, s.sector))
