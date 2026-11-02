"""Offline tests af den egne StockMap (ugebarer, kvadranter, signaler, handler)."""
import unittest

import numpy as np
import pandas as pd

from stockscanner.stockmap import (
    StockMapParams, angle_on, points_up, rotation, signals, trade_stats, trades, weekly,
)


def daily(close, start="2022-01-03"):
    index = pd.date_range(start, periods=len(close), freq="B")
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close}, index=index)


class WeeklyTests(unittest.TestCase):
    def test_weekly_bars_end_friday_with_first_open_last_close(self):
        frame = daily(np.arange(1, 11))  # to hele uger, mandag 3. jan 2022
        bars = weekly(frame)
        self.assertEqual(list(bars.index.dayofweek), [4, 4])
        self.assertEqual(list(bars["Open"]), [1, 6])
        self.assertEqual(list(bars["Close"]), [5, 10])


class RotationTests(unittest.TestCase):
    def setUp(self):
        self.bench = daily(np.full(600, 100.0))

    def test_outperformer_is_leading_and_underperformer_lagging(self):
        up = rotation(daily(100 * 1.002 ** np.arange(600)), self.bench)
        down = rotation(daily(100 * 0.998 ** np.arange(600)), self.bench)
        self.assertEqual(up["quadrant"].iloc[-1], "leading")
        self.assertEqual(down["quadrant"].iloc[-1], "lagging")

    def test_points_up(self):
        self.assertTrue(points_up(300) and points_up(10))
        self.assertFalse(points_up(200) or points_up(120))

    def test_cycling_relative_strength_gives_buys_and_sells(self):
        # relativ styrke der svinger i cyklusser får pilen til at køre rundt i kortet
        days = np.arange(1500)
        stock = daily(100 * np.exp(0.25 * np.sin(2 * np.pi * days / 260)))
        bench = daily(np.full(1500, 100.0))
        sig = signals(rotation(stock, bench))
        self.assertIn("køb", set(sig))
        self.assertIn("salg", set(sig))
        found = trades(stock, bench)
        self.assertTrue(found)
        self.assertEqual(trade_stats(found)["trades"], len(found))
        self.assertTrue(all(t.weeks > 0 for t in found))

    def test_no_look_ahead(self):
        rng = np.random.default_rng(4)
        stock = daily(100 * np.cumprod(1 + rng.normal(0, 0.015, 600)))
        bench = daily(100 * np.cumprod(1 + rng.normal(0, 0.01, 600)))
        full = rotation(stock, bench)
        cut = rotation(stock.iloc[:400], bench.iloc[:400])
        common = cut.index[:-1]  # sidste uge kan være ufuldstændig i det afkortede datasæt
        pd.testing.assert_frame_equal(cut.loc[common], full.loc[common])

    def test_angle_on_date_and_sma_variant(self):
        stock = daily(100 * 1.002 ** np.arange(600))
        self.assertIsNotNone(angle_on(stock, self.bench, "2023-06-30"))
        self.assertIsNotNone(angle_on(stock, self.bench, "2023-06-30", StockMapParams(ema=False)))
        self.assertIsNone(angle_on(stock, self.bench, "2021-01-01"))

    def test_empty_trade_stats(self):
        self.assertEqual(trade_stats([])["trades"], 0)


if __name__ == "__main__":
    unittest.main()
