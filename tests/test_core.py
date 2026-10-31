"""Offline tests med syntetiske kursdata; kræver ingen internetadgang."""
import unittest

import numpy as np
import pandas as pd

from stockscanner.core import analyze_prices, parse_tickers, WEIGHTS


class ScannerTests(unittest.TestCase):
    def test_weights_sum_to_100(self):
        self.assertEqual(sum(WEIGHTS.values()), 100)

    def test_symbols_unique_and_uppercase(self):
        self.assertEqual(
            parse_tickers("novo-b.co, msft\nMSFT; aapl"),
            ["NOVO-B.CO", "MSFT", "AAPL"],
        )

    def test_ticker_validation_and_limit(self):
        with self.assertRaises(ValueError):
            parse_tickers("MSFT,foo/bar")
        with self.assertRaises(ValueError):
            parse_tickers("")
        with self.assertRaises(ValueError):
            parse_tickers("A B C", max_count=2)

    def test_insufficient_history(self):
        frame = pd.DataFrame({"Close": [100.0] * 199})
        with self.assertRaisesRegex(ValueError, "mindst 200"):
            analyze_prices(frame, "TEST")

    def test_uptrend(self):
        index = pd.date_range("2024-01-01", periods=260, freq="B")
        frame = pd.DataFrame(
            {"Close": np.linspace(100, 180, len(index)), "Volume": 1000},
            index=index,
        )
        result = analyze_prices(frame, "TEST", "DKK")
        self.assertEqual(result.market_date, str(index[-1].date()))
        self.assertGreater(result.price, result.sma50)
        self.assertGreater(result.sma50, result.sma200)
        self.assertEqual(result.currency, "DKK")
        self.assertTrue(0 <= result.score <= 100)
        self.assertEqual(result.score, sum(WEIGHTS[k] for k, v in result.checks.items() if v))

    def test_flat_price_rsi_50(self):
        index = pd.date_range("2024-01-01", periods=220, freq="B")
        frame = pd.DataFrame({"Close": 100.0, "Volume": 0}, index=index)
        result = analyze_prices(frame, "FLAT")
        self.assertAlmostEqual(result.rsi14, 50.0)
        self.assertIsNone(result.relative_volume)


if __name__ == "__main__":
    unittest.main()
