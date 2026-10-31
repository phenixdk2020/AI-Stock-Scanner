"""Sector summary tests using synthetic data; no market-data API access."""
import unittest

from stockscanner.core import ScanResult
from stockscanner.sectors import group_sectors


def sample(ticker: str, change: float, score: int, volume: float | None, above: bool) -> ScanResult:
    return ScanResult(
        ticker=ticker, market_date="2026-10-30",
        price=120.0 if above else 80.0, currency="USD",
        change_21d_pct=change, sma50=100.0, sma200=90.0,
        rsi14=55.0, macd=1.0, macd_signal=0.5,
        relative_volume=volume, score=score,
        signal="Hold øje", checks={},
    )


class TestSectors(unittest.TestCase):
    def test_group_by_market_and_sector(self):
        summaries = group_sectors([
            sample("MSFT", 12, 80, 1.5, True),
            sample("NVDA", 6, 60, 1.3, True),
            sample("NOVO-B.CO", -12, 30, 0.6, False),
        ])
        tech = next(s for s in summaries if s.market == "USA" and s.sector == "Teknologi")
        self.assertEqual(tech.count, 2)
        self.assertEqual(tech.avg_score, 70.0)
        self.assertEqual(tech.status, "Styrke")
        health = next(s for s in summaries if s.market == "Danmark")
        self.assertEqual(health.status, "Under pres")

    def test_missing_volume_is_not_assumed(self):
        row = group_sectors([sample("OTHER.CO", 0, 40, None, False)])[0]
        self.assertIsNone(row.avg_relative_volume)
        self.assertEqual(row.sector, "Ikke kategoriseret")


if __name__ == "__main__":
    unittest.main()
