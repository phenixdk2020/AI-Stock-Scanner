"""Offline tests af TPI-lite."""
import unittest

import numpy as np
import pandas as pd

from stockscanner.tpi_lite import bucket_returns, tpi_states


def daily(close, start="2015-01-05"):
    index = pd.bdate_range(start, periods=len(close))
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"Open": close, "Close": close}, index=index)


class TpiLiteTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(3)
        self.prices = daily(100 * np.cumprod(1 + rng.normal(0.0004, 0.015, 2500)))

    def test_states_have_expected_columns_and_values(self):
        states = tpi_states(self.prices)
        self.assertTrue({"long_green", "short_pct", "state"} <= set(states.columns))
        self.assertTrue(set(states["state"]) <= {"oversolgt", "neutral", "overkøbt"})
        self.assertTrue(states["short_pct"].between(0, 100).all())

    def test_uptrend_is_green(self):
        states = tpi_states(daily(100 * 1.001 ** np.arange(1500)))
        self.assertTrue(states["long_green"].iloc[-1])

    def test_no_look_ahead(self):
        full = tpi_states(self.prices)
        cut = tpi_states(self.prices.iloc[:2000])
        common = cut.index[:-1]
        pd.testing.assert_frame_equal(cut.loc[common], full.loc[common])

    def test_bucket_returns(self):
        result = bucket_returns(self.prices, horizons=(5,))
        self.assertIn("5d", result.columns)
        self.assertTrue(result["group"].str.contains("/").all())


if __name__ == "__main__":
    unittest.main()
