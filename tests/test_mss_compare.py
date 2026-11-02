"""Offline tests af sammenligningen med MSS-observationer."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from stockscanner.mss_compare import (
    angle_difference, compare, load_observations, spearman, stockmap_angle, summary, trend_state,
)


def frame(close, start="2025-01-01"):
    index = pd.date_range(start, periods=len(close), freq="B", tz="Europe/Copenhagen")
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"Open": close, "High": close * 1.01, "Low": close * 0.99, "Close": close,
                         "Volume": 1000.0}, index=index)


class AngleTests(unittest.TestCase):
    def test_angle_difference_wraps(self):
        self.assertEqual(angle_difference(350, 10), 20)
        self.assertEqual(angle_difference(0, 180), 180)

    def test_new_outperformer_points_up_right(self):
        bench = frame(np.full(200, 100.0))
        stock = frame(np.concatenate([np.full(150, 100.0), 100 * 1.01 ** np.arange(1, 51)]))  # flad, så stigning
        angle = stockmap_angle(stock, bench, str(bench.index[158].date()))
        self.assertTrue(0 < angle < 90, angle)

    def test_falling_underperformer_points_down_left(self):
        bench = frame(np.full(200, 100.0))
        stock = frame(100 * np.exp(-np.linspace(0, 1, 200) ** 2))
        angle = stockmap_angle(stock, bench, str(bench.index[-1].date()))
        self.assertTrue(180 < angle < 270, angle)

    def test_angle_uses_only_data_until_date(self):
        bench = frame(np.full(200, 100.0))
        close = 100 * np.exp(np.linspace(0, 1, 200) ** 2)
        date = str(bench.index[150].date())
        changed = close.copy()
        changed[151:] = 1.0
        self.assertEqual(stockmap_angle(frame(close), bench, date), stockmap_angle(frame(changed), bench, date))


class CompareTests(unittest.TestCase):
    def test_load_compare_and_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "obs.csv"
            path.write_text(
                "date;mss_ticker;yf_ticker;quality;value;moat;mss_score;timing_zone;stockmap_angle;source\n"
                "2025-12-15;A;A;90;50;50;80;Købszone;45;x\n"
                "2025-12-15;B;B;60;50;50;60;Neutral;200;x\n"
                "2025-12-15;C;C;75;50;50;70;Behold;;x\n", encoding="utf-8")
            observations = load_observations(path)
        prices = {"A": frame(np.linspace(100, 200, 260)), "B": frame(np.linspace(200, 100, 260)),
                  "C": frame(np.full(260, 100.0))}
        quality = {"A": 85.0, "B": 40.0, "C": 70.0}
        rows = compare(observations, prices.__getitem__, quality.get, frame(np.full(260, 100.0)))
        self.assertEqual([r.ticker for r in rows], ["A", "B", "C"])
        self.assertEqual(rows[0].our_trend, "Optrend")
        self.assertEqual(rows[1].our_trend, "Ingen optrend")
        self.assertIsNone(rows[2].angle_diff)  # MSS-vinkel mangler
        result = summary(rows)
        self.assertAlmostEqual(result["quality_spearman"], 1.0)
        self.assertAlmostEqual(result["quality_mean_abs_diff"], (5 + 20 + 5) / 3)

    def test_trend_state_before_history(self):
        self.assertEqual(trend_state(frame(np.full(10, 1.0)), "2020-01-01"), "–")

    def test_spearman_needs_three_pairs(self):
        self.assertIsNone(spearman([1, 2], [1, 2]))


if __name__ == "__main__":
    unittest.main()
