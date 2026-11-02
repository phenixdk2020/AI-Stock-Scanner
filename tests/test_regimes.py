"""Offline tests af regime-backtesten (fase 5, A–C) med syntetiske kurser."""
import unittest

import numpy as np
import pandas as pd

from stockscanner.regimes import REGIMES, regime_backtest, regime_masks, relative_strength


def frame_from_close(close, start="2020-01-01", tz=None):
    index = pd.date_range(start, periods=len(close), freq="B", tz=tz)
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"Open": close, "High": close * 1.01, "Low": close * 0.99, "Close": close,
                         "Volume": 1000.0}, index=index)


class RelativeStrengthTests(unittest.TestCase):
    def test_outperformer_is_strong_and_underperformer_is_not(self):
        bench = frame_from_close(np.full(120, 100.0))
        strong = frame_from_close(np.linspace(100, 160, 120))
        weak = frame_from_close(np.linspace(100, 60, 120))
        self.assertTrue(relative_strength(strong, bench).iloc[-1])
        self.assertFalse(relative_strength(weak, bench).iloc[-1])
        self.assertFalse(relative_strength(strong, bench).iloc[:50].any())  # for lidt historik

    def test_benchmark_uses_previous_day_only(self):
        bench_close = np.full(80, 100.0)
        stock = frame_from_close(np.full(80, 100.0))
        rs_before = relative_strength(stock, frame_from_close(bench_close))
        bench_close[-1] = 1.0  # benchmarkens sidste dag må ikke påvirke samme dag
        rs_after = relative_strength(stock, frame_from_close(bench_close))
        pd.testing.assert_series_equal(rs_before, rs_after)

    def test_timezone_aware_stock_index_aligns_with_naive_benchmark(self):
        bench = frame_from_close(np.full(120, 100.0))
        stock = frame_from_close(np.linspace(100, 160, 120), tz="Europe/Copenhagen")
        self.assertTrue(relative_strength(stock, bench).iloc[-1])


class RegimeTests(unittest.TestCase):
    def test_masks_are_consistent(self):
        rng = np.random.default_rng(5)
        frame = frame_from_close(100 * np.cumprod(1 + rng.normal(0.0005, 0.02, 500)))
        masks = regime_masks(frame, frame_from_close(np.full(500, 100.0)))
        self.assertTrue((masks["B_trend_rs"] <= masks["A_trend"]).all())
        pd.testing.assert_series_equal(masks["C_trend_rekyl"] | masks["C_trend_uden_rekyl"], masks["A_trend"],
                                       check_names=False)
        self.assertFalse((masks["C_trend_rekyl"] & masks["C_trend_uden_rekyl"]).any())

    def test_no_look_ahead(self):
        rng = np.random.default_rng(9)
        frame = frame_from_close(100 * np.cumprod(1 + rng.normal(0.0005, 0.02, 400)))
        bench = frame_from_close(100 * np.cumprod(1 + rng.normal(0.0003, 0.01, 400)))
        full = regime_masks(frame, bench)
        pd.testing.assert_frame_equal(regime_masks(frame.iloc[:300], bench.iloc[:300]), full.iloc[:300])

    def test_backtest_periods_and_edge(self):
        rng = np.random.default_rng(2)
        frame = frame_from_close(100 * np.cumprod(1 + rng.normal(0.0005, 0.02, 700)))
        rows = regime_backtest({"X": frame}, frame_from_close(np.full(700, 100.0)), horizons=(20,),
                               holdout_start="2022-06-01")
        self.assertEqual({row.period for row in rows}, {"udvikling", "urørt"})
        self.assertEqual(len(rows), 2 * len(REGIMES))
        for row in rows:
            if row.regime == "alle":
                self.assertAlmostEqual(row.edge_pct, 0.0)

    def test_backtest_without_benchmark_skips_b(self):
        frame = frame_from_close(np.linspace(100, 200, 300))
        rows = regime_backtest({"X": frame}, None, horizons=(5,))
        self.assertNotIn("B_trend_rs", {row.regime for row in rows})


if __name__ == "__main__":
    unittest.main()
