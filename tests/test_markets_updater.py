"""Unit tests for country selectors and secure update access."""
import os
import unittest
from unittest.mock import patch

from stockscanner.markets import SAMPLES, ETF_SAMPLES, example_tickers, market_of, instrument_type_of
from stockscanner.updater import trusted_origin, authorized


class TestUpdaterAndMarkets(unittest.TestCase):
    def test_markets(self):
        self.assertEqual(len(SAMPLES), 9)
        self.assertEqual(len(example_tickers(list(SAMPLES))), 36)
        self.assertEqual(market_of("NOVO-B.CO"), "Danmark")
        self.assertEqual(market_of("SAP.DE"), "Tyskland")
        self.assertEqual(market_of("VOLV-B.ST"), "Sverige")
        self.assertEqual(market_of("EQNR.OL"), "Norge")
        self.assertEqual(market_of("AAPL"), "USA")
        self.assertEqual(market_of("MC.PA"), "Frankrig")
        self.assertEqual(market_of("ASML.AS"), "Holland")
        self.assertEqual(market_of("SAN.MC"), "Spanien")
        self.assertEqual(market_of("NOKIA.HE"), "Finland")
        self.assertEqual(len(ETF_SAMPLES), 4)
        self.assertEqual(instrument_type_of("VWCE.DE"), "ETF")
        self.assertEqual(instrument_type_of("MSFT"), "Aktie")
        self.assertEqual(instrument_type_of("UNKNOWN.PA"), "Ukendt")
        self.assertEqual(len(example_tickers(["Tyskland"], include_etfs=True)), 8)

    def test_trusted_git_remote(self):
        self.assertTrue(trusted_origin("https://github.com/phenixdk2020/AI-Stock-Scanner.git"))
        self.assertTrue(trusted_origin("git@github.com:phenixdk2020/AI-Stock-Scanner.git"))
        self.assertFalse(trusted_origin("https://example.com/phenixdk2020/AI-Stock-Scanner.git"))
        self.assertFalse(trusted_origin("https://user:password@github.com/phenixdk2020/AI-Stock-Scanner.git"))

    def test_token(self):
        with patch.dict(os.environ, {"STOCKSCANNER_ADMIN_TOKEN": "this-is-a-long-secret-token"}):
            self.assertTrue(authorized("this-is-a-long-secret-token"))
            self.assertFalse(authorized("incorrect"))
        with patch.dict(os.environ, {"STOCKSCANNER_ADMIN_TOKEN": "short"}):
            self.assertFalse(authorized("short"))


if __name__ == "__main__":
    unittest.main()
