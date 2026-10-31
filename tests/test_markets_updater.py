"""Unit tests for country selectors and secure update access."""
import os
import unittest
from unittest.mock import patch

from stockscanner.markets import SAMPLES, example_tickers, market_of
from stockscanner.updater import trusted_origin, authorized


class TestUpdaterAndMarkets(unittest.TestCase):
    def test_markets(self):
        self.assertEqual(len(SAMPLES), 5)
        self.assertEqual(len(example_tickers(list(SAMPLES))), 20)
        self.assertEqual(market_of("NOVO-B.CO"), "Danmark")
        self.assertEqual(market_of("SAP.DE"), "Tyskland")
        self.assertEqual(market_of("VOLV-B.ST"), "Sverige")
        self.assertEqual(market_of("EQNR.OL"), "Norge")
        self.assertEqual(market_of("AAPL"), "USA")

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
