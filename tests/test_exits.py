"""Offline tests af salgsreglerne (punkt 9)."""
import unittest

import numpy as np
import pandas as pd

from stockscanner.exits import (
    ALL_RULES, exit_signals, simulate, summarize, supertrend, trend_entries,
)


def daily(close, start="2020-01-01", spread=0.01):
    index = pd.bdate_range(start, periods=len(close))
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"Open": close, "High": close * (1 + spread), "Low": close * (1 - spread),
                         "Close": close}, index=index)


class SupertrendTests(unittest.TestCase):
    def test_up_then_down(self):
        path = np.concatenate([np.linspace(100, 200, 150), np.linspace(200, 120, 100)])
        trend = supertrend(daily(path), 10, 3.0)
        self.assertTrue(trend.iloc[140])
        self.assertFalse(trend.iloc[-1])
        flip = trend.index[~trend & (trend.index > trend.index[150])][0]
        self.assertGreater(flip, trend.index[150])  # vender først efter toppen

    def test_wider_multiplier_flips_later(self):
        path = np.concatenate([np.linspace(100, 200, 150), np.linspace(200, 120, 100)])
        first = lambda m: supertrend(daily(path), 10, m).iloc[150:].idxmin()
        self.assertLess(first(3.0), first(5.0))


class ExitTests(unittest.TestCase):
    def setUp(self):
        # 250 dages stigning, kort dyk, ny stigning, langt fald
        self.path = np.concatenate([np.linspace(100, 200, 250), np.linspace(200, 185, 10),
                                    np.linspace(185, 260, 120), np.linspace(260, 150, 150)])
        self.prices = daily(self.path)

    def test_trend_entry_needs_close_above_sma200(self):
        entries = trend_entries(self.prices)
        close = self.prices["Close"]
        for day in entries:
            self.assertGreater(close[day], close.rolling(200).mean()[day])

    def test_sma20_exits_before_sma200_and_entry_is_next_open(self):
        signals = exit_signals(self.prices)
        entry_day = self.prices.index[255]
        fast = simulate(self.prices, [entry_day], "SMA20", signals)[0]
        slow = simulate(self.prices, [entry_day], "SMA200", signals)[0]
        self.assertEqual(fast.entry_day, self.prices.index[256])
        self.assertLess(fast.exit_day, slow.exit_day)
        self.assertLessEqual(fast.worst_pct, fast.best_pct)

    def test_entry_below_average_waits_for_next_break(self):
        # køb mens kursen er under SMA50: ikke salg dagen efter, først ved næste brud nedad
        path = np.concatenate([np.linspace(200, 150, 120), np.linspace(150, 210, 100), np.linspace(210, 170, 60)])
        prices = daily(path)
        signals = exit_signals(prices)
        trade = simulate(prices, [prices.index[120]], "SMA50", signals)[0]
        self.assertGreater(trade.days, 50)

    def test_fixed_days_and_open_trades_dropped(self):
        signals = exit_signals(self.prices)
        trade = simulate(self.prices, [self.prices.index[100]], "Fast 60 dage", signals)[0]
        self.assertEqual(trade.days, 60)
        self.assertEqual(simulate(self.prices, [self.prices.index[-5]], "Fast 60 dage", signals), [])

    def test_summary_fields(self):
        signals = exit_signals(self.prices)
        trades = simulate(self.prices, trend_entries(self.prices) + [self.prices.index[255]], "SMA50", signals)
        stats = summarize(trades)
        self.assertEqual(stats["trades"], len(trades))
        self.assertIn("capture", stats)
        self.assertEqual(summarize([]), {"trades": 0})

    def test_all_rules_listed(self):
        self.assertEqual(len(ALL_RULES), 8)


if __name__ == "__main__":
    unittest.main()
