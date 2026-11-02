"""Offline tests af regressionskanal og ADX (B-08, B-12)."""
import unittest

import numpy as np
import pandas as pd

from stockscanner.regression import adx, regression_break, regression_channel


def frame(close, spread=0.01):
    index = pd.bdate_range("2020-01-01", periods=len(close))
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"Open": close, "High": close * (1 + spread), "Low": close * (1 - spread),
                         "Close": close}, index=index)


class ChannelTests(unittest.TestCase):
    def test_perfect_exponential_trend(self):
        close = pd.Series(100 * np.exp(0.002 * np.arange(300)), index=pd.bdate_range("2020-01-01", periods=300))
        ch = regression_channel(close, 126)
        self.assertTrue(ch["mid"].iloc[:125].isna().all())
        self.assertAlmostEqual(ch["r"].iloc[-1], 1.0, places=6)
        self.assertAlmostEqual(ch["slope"].iloc[-1], 0.002, places=8)
        self.assertAlmostEqual(ch["mid"].iloc[-1], close.iloc[-1], places=4)

    def test_no_lookahead(self):
        rng = np.random.default_rng(1)
        close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.001, 0.01, 400))), index=pd.bdate_range("2020-01-01", periods=400))
        full = regression_break(close, 126)
        cut = regression_break(close.iloc[:300], 126)
        pd.testing.assert_series_equal(full.iloc[:300], cut)

    def test_break_fires_once_after_clean_uptrend(self):
        rng = np.random.default_rng(2)
        up = 100 * np.exp(np.cumsum(rng.normal(0.004, 0.004, 200)))
        crash = up[-1] * np.exp(np.cumsum(np.full(30, -0.03)))
        close = pd.Series(np.concatenate([up, crash]), index=pd.bdate_range("2020-01-01", periods=230))
        fire = regression_break(close, 126)
        self.assertEqual(int(fire.iloc[200:].sum()), 1)  # ét brud i faldet (støj kan give enkelte før)
        self.assertLess(fire.iloc[200:].values.argmax(), 8)

    def test_no_break_when_r_low(self):
        rng = np.random.default_rng(3)
        close = pd.Series(100 + np.cumsum(rng.normal(0, 1, 300)).clip(-50, 50) * 0 + rng.normal(0, 3, 300),
                          index=pd.bdate_range("2020-01-01", periods=300))
        self.assertEqual(int(regression_break(close, 126, min_r=0.9).sum()), 0)


class AdxTests(unittest.TestCase):
    def test_strong_trend_high_adx_sideways_low(self):
        trend = adx(frame(np.linspace(100, 300, 200)))
        rng = np.random.default_rng(4)
        side = adx(frame(100 + rng.normal(0, 1, 200)))
        self.assertGreater(trend.iloc[-1], 40)
        self.assertLess(side.iloc[-1], 25)
        self.assertTrue(trend.iloc[:13].isna().all())
        self.assertTrue(((trend.dropna() >= 0) & (trend.dropna() <= 100)).all())


if __name__ == "__main__":
    unittest.main()
