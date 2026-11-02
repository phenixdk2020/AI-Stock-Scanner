"""Offline tests af positionsstørrelse."""
import unittest

import pandas as pd

from stockscanner.sizing import DEFAULTS, atr, fx_rate, position_size


class SizingTests(unittest.TestCase):
    def test_risk_limits_shares(self):
        settings = dict(DEFAULTS, kapital=100000, risiko_pct=1.0, max_pct=50.0)
        size = position_size(100.0, 2.0, settings)          # stop 94, risiko 6 pr. aktie → 1000 / 6
        self.assertEqual(size.shares, 166)
        self.assertAlmostEqual(size.stop, 94.0)
        self.assertLessEqual(size.risk, 1000)

    def test_cap_limits_shares(self):
        size = position_size(100.0, 0.1, dict(DEFAULTS, kapital=100000, max_pct=3.0))
        self.assertEqual(size.shares, 30)

    def test_currency_conversion(self):
        settings = dict(DEFAULTS, kapital=100000, max_pct=3.0)
        size = position_size(100.0, 0.1, settings, fx=fx_rate("USD", "DKK"))
        self.assertAlmostEqual(size.amount, size.shares * 100 * fx_rate("USD", "DKK"))
        self.assertLessEqual(size.amount, 3000)

    def test_missing_data(self):
        self.assertIsNone(position_size(100.0, None, DEFAULTS))
        self.assertIsNone(fx_rate(None, "DKK"))

    def test_atr(self):
        prices = pd.DataFrame({"High": [11.0] * 20, "Low": [9.0] * 20, "Close": [10.0] * 20})
        self.assertAlmostEqual(atr(prices), 2.0)


if __name__ == "__main__":
    unittest.main()
