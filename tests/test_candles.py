"""Offline tests af candle-detektoren med håndbyggede kurser; kræver ingen internetadgang."""
import unittest

import numpy as np
import pandas as pd

from stockscanner.candles import (
    PATTERNS, backtest, detect_patterns, eligible_signals, forward_returns, simulate_trade, trade_backtest,
    trend_context,
)


def bars(rows, volume=None):
    """rows: (open, high, low, close)."""
    frame = pd.DataFrame(rows, columns=["Open", "High", "Low", "Close"],
                         index=pd.date_range("2026-01-01", periods=len(rows), freq="B"))
    frame["Volume"] = volume if volume is not None else 1000.0
    return frame


def flat(n, price=100.0):
    return [(price, price + 1, price - 1, price)] * n


class PatternTests(unittest.TestCase):
    def test_inside_bar_breakout_fires_on_first_close_above_mother_high(self):
        rows = flat(3) + [
            (100, 110, 90, 105),   # mother bar
            (104, 108, 95, 100),   # inside bar
            (101, 109, 99, 108),   # close 108 < 110: ingen udbrud
            (108, 112, 107, 111),  # første lukning over 110
            (111, 115, 110, 114),  # stadig over, men ikke første gang
        ]
        result = detect_patterns(bars(rows))["inside_bar_breakout"]
        self.assertEqual(list(np.flatnonzero(result)), [6])

    def test_inside_bar_requires_strictly_inside_range(self):
        rows = flat(3) + [(100, 110, 90, 105), (104, 110, 95, 100), (101, 112, 99, 111)]
        self.assertFalse(detect_patterns(bars(rows))["inside_bar_breakout"].any())

    def test_inside_bar_breakout_window(self):
        rows = flat(3) + [(100, 110, 90, 105), (104, 108, 95, 100)] + [(100, 105, 95, 100)] * 2 + [(100, 112, 99, 111)]
        self.assertTrue(detect_patterns(bars(rows), breakout_window=3)["inside_bar_breakout"].iloc[-1])
        self.assertFalse(detect_patterns(bars(rows), breakout_window=2)["inside_bar_breakout"].any())

    def test_bullish_engulfing(self):
        rows = flat(2) + [(105, 106, 99, 100), (99, 108, 98, 107)]
        self.assertTrue(detect_patterns(bars(rows))["bullish_engulfing"].iloc[-1])
        rows[-1] = (101, 108, 98, 107)  # åbner over forrige lukning
        self.assertFalse(detect_patterns(bars(rows))["bullish_engulfing"].iloc[-1])

    def test_hammer(self):
        rows = flat(2) + [(100, 101, 90, 100.8)]
        self.assertTrue(detect_patterns(bars(rows))["hammer"].iloc[-1])
        rows[-1] = (100, 110, 90, 100.8)  # lang øvre væge
        self.assertFalse(detect_patterns(bars(rows))["hammer"].iloc[-1])

    def test_morning_star(self):
        rows = flat(2) + [(110, 111, 99, 100), (99, 100, 97, 98.5), (99, 107, 98, 106)]
        self.assertTrue(detect_patterns(bars(rows))["morning_star"].iloc[-1])
        rows[-1] = (99, 104, 98, 103)  # lukker under midten af den røde krop (105)
        self.assertFalse(detect_patterns(bars(rows))["morning_star"].iloc[-1])

    def test_close_above_prev_high_needs_volume(self):
        rows = flat(21) + [(100, 103, 99, 102)]
        loud = [1000.0] * 21 + [2000.0]
        quiet = [1000.0] * 21 + [1200.0]
        self.assertTrue(detect_patterns(bars(rows, loud))["close_above_prev_high_volume"].iloc[-1])
        self.assertFalse(detect_patterns(bars(rows, quiet))["close_above_prev_high_volume"].iloc[-1])

    def test_missing_ohlc_never_signals(self):
        rows = flat(2) + [(105, 106, 99, 100), (99, 108, 98, 107)]
        frame = bars(rows)
        frame.iloc[-1, frame.columns.get_loc("Open")] = np.nan
        self.assertFalse(detect_patterns(frame).iloc[-1].any())

    def test_missing_column_raises(self):
        with self.assertRaisesRegex(ValueError, "Mangler"):
            detect_patterns(pd.DataFrame({"Close": [1.0, 2.0]}))

    def test_no_look_ahead(self):
        rng = np.random.default_rng(1)
        close = 100 * np.cumprod(1 + rng.normal(0, 0.02, 300))
        opens = close * (1 + rng.normal(0, 0.005, 300))
        frame = bars(list(zip(opens, np.maximum(opens, close) * 1.01, np.minimum(opens, close) * 0.99, close)),
                     rng.uniform(500, 3000, 300))
        full = eligible_signals(frame)
        for cut in (220, 260, 299):
            partial = eligible_signals(frame.iloc[:cut])
            pd.testing.assert_frame_equal(partial, full.iloc[:cut])


class ContextAndBacktestTests(unittest.TestCase):
    def test_trend_context_uptrend_and_pullback(self):
        close = np.concatenate([np.linspace(50, 150, 250), [140.0] * 3])
        frame = bars([(x, x + 1, x - 1, x) for x in close])
        context = trend_context(frame)
        self.assertTrue(context["uptrend"].iloc[249])
        self.assertTrue(context["pullback"].iloc[-1])  # 140 er > 5 % under toppen 150
        self.assertFalse(context["uptrend"].iloc[100])  # for lidt historik til SMA200

    def test_forward_returns_buy_next_open_and_subtract_costs(self):
        frame = bars([(100, 101, 99, 100), (110, 111, 109, 110), (120, 121, 119, 121)])
        result = forward_returns(frame, horizons=(2,), cost_pct=0.1)
        self.assertAlmostEqual(result["2d"].iloc[0], (121 / 110 - 1) * 100 - 0.2)
        self.assertTrue(np.isnan(result["2d"].iloc[1]))

    def test_backtest_reports_every_pattern_and_horizon(self):
        rng = np.random.default_rng(7)
        close = 100 * np.cumprod(1 + rng.normal(0.001, 0.02, 600))
        opens = close * (1 + rng.normal(0, 0.005, 600))
        frame = bars(list(zip(opens, np.maximum(opens, close) * 1.01, np.minimum(opens, close) * 0.99, close)),
                     rng.uniform(500, 3000, 600))
        rows = backtest({"TEST": frame}, horizons=(5, 10))
        self.assertEqual(len(rows), len(PATTERNS) * 2)
        for row in rows:
            self.assertIsNotNone(row.baseline_mean_pct)
            if row.signals:
                self.assertAlmostEqual(row.edge_pct, row.mean_pct - row.baseline_mean_pct)


class TradeSimulationTests(unittest.TestCase):
    # Mother bar 90-110 på position 0, inside bar på position 1.
    BASE = [(100, 110, 90, 105), (104, 108, 95, 100)]

    def test_buy_stop_fills_at_trigger_and_exits_on_time(self):
        rows = self.BASE + [(105, 112, 104, 111), (111, 115, 110, 114)]
        pct, r, reason = simulate_trade(bars(rows), 1, 110, 90, hold_days=2, cost_pct=0)
        self.assertEqual(reason, "tid")
        self.assertAlmostEqual(pct, (114 / 110 - 1) * 100)
        self.assertAlmostEqual(r, 4 / 20)

    def test_gap_above_trigger_fills_at_open(self):
        rows = self.BASE + [(113, 116, 112, 115)]
        pct, _, _ = simulate_trade(bars(rows), 1, 110, 90, hold_days=1, cost_pct=0)
        self.assertAlmostEqual(pct, (115 / 113 - 1) * 100)

    def test_stop_hit_and_gap_through_stop(self):
        rows = self.BASE + [(105, 111, 104, 109), (100, 101, 88, 95), (95, 96, 94, 95)]
        self.assertEqual(simulate_trade(bars(rows), 1, 110, 90, hold_days=3, cost_pct=0)[1], -1)
        rows = self.BASE + [(105, 111, 104, 109), (85, 87, 80, 86), (86, 87, 85, 86)]
        pct, r, reason = simulate_trade(bars(rows), 1, 110, 90, hold_days=3, cost_pct=0)
        self.assertEqual(reason, "stop (gap)")
        self.assertAlmostEqual(r, -25 / 20)

    def test_entry_day_touching_stop_counts_as_stopped(self):
        rows = self.BASE + [(100, 111, 89, 109)]
        self.assertEqual(simulate_trade(bars(rows), 1, 110, 90, hold_days=1, cost_pct=0)[2], "stop")

    def test_no_entry_when_setup_breaks_down_or_expires(self):
        self.assertIsNone(simulate_trade(bars(self.BASE + [(95, 99, 88, 89)]), 1, 110, 90, 1))
        self.assertIsNone(simulate_trade(bars(self.BASE + [(100, 105, 95, 100)] * 3), 1, 110, 90, 1, entry_window=3))

    def test_target_in_r(self):
        rows = self.BASE + [(105, 111, 104, 109), (130, 155, 129, 150), (150, 151, 149, 150)]
        _, r, reason = simulate_trade(bars(rows), 1, 110, 90, hold_days=3, target_r=2, cost_pct=0)
        self.assertEqual(reason, "mål")
        self.assertAlmostEqual(r, 2)  # mål 110 + 2 × 20 = 150 ramt intradag
        rows[3] = (160, 165, 158, 162)  # gap over målet: salg til åbningen
        self.assertAlmostEqual(simulate_trade(bars(rows), 1, 110, 90, 3, target_r=2, cost_pct=0)[1], 2.5)

    def test_horizon_beyond_data_is_dropped_even_if_stopped(self):
        rows = self.BASE + [(105, 111, 104, 109), (100, 101, 88, 95)]
        self.assertIsNone(simulate_trade(bars(rows), 1, 110, 90, hold_days=3, cost_pct=0))

    def test_missing_low_or_close_drops_trade(self):
        rows = self.BASE + [(105, 111, 104, 109), (100, 101, np.nan, 95)]
        self.assertIsNone(simulate_trade(bars(rows), 1, 110, 90, hold_days=2, cost_pct=0))
        rows = self.BASE + [(105, 111, 104, np.nan)]
        self.assertIsNone(simulate_trade(bars(rows), 1, 110, 90, hold_days=1, cost_pct=0))

    def test_target_not_counted_on_entry_day(self):
        rows = self.BASE + [(105, 155, 104, 120)]
        self.assertEqual(simulate_trade(bars(rows), 1, 110, 90, hold_days=1, target_r=2, cost_pct=0)[2], "tid")

    def test_hold_days_must_be_positive(self):
        with self.assertRaises(ValueError):
            simulate_trade(bars(self.BASE + [(105, 111, 104, 109)]), 1, 110, 90, hold_days=0)

    def test_trade_backtest_runs_on_random_walk(self):
        rng = np.random.default_rng(3)
        close = 100 * np.cumprod(1 + rng.normal(0.001, 0.02, 600))
        opens = close * (1 + rng.normal(0, 0.005, 600))
        frame = bars(list(zip(opens, np.maximum(opens, close) * 1.01, np.minimum(opens, close) * 0.99, close)),
                     rng.uniform(500, 3000, 600))
        rows = trade_backtest({"TEST": frame}, hold_days=(1, 5))
        self.assertEqual(len(rows), len(PATTERNS) * 2)
        self.assertTrue(any(row.trades for row in rows))


if __name__ == "__main__":

    unittest.main()
