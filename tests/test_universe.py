"""Offline tests af percentiler mod et univers."""
import unittest

import pandas as pd

from stockscanner import universe


def row(roce, roa, pe, ps, ret):
    return {"q_roce": roce, "qs_roce": roce * 100, "q_roa": roa, "qs_roa": roa * 100,
            "v_pe": pe, "v_ps": ps, "v_pb": pe / 10, "m_ret_3m": ret, "m_ret_12m": ret * 2, "m_ret_1m": ret / 3}


class UniverseTests(unittest.TestCase):
    def setUp(self):
        self.universe = pd.DataFrame({f"U{i}": row(0.05 * i, 0.02 * i, 40 - 3 * i, 8 - 0.6 * i, 0.02 * i)
                                      for i in range(1, 11)}).T

    def test_target_is_ranked_against_universe_not_only_itself(self):
        targets = pd.DataFrame({"T": row(0.6, 0.25, 5, 0.5, 0.3)}).T  # bedre end hele universet
        result = universe.percentiles(targets, self.universe)
        self.assertAlmostEqual(result.loc["T", "quality"], 100.0)
        self.assertAlmostEqual(result.loc["T", "value"], 100.0)
        self.assertAlmostEqual(result.loc["T", "momentum"], 100.0)
        self.assertIn("moat", result.columns)

    def test_breadth(self):
        frame = pd.DataFrame({"b_above_50": [True, True, False, True], "b_above_200": ["True", "False", "False", None]})
        result = universe.breadth(frame)
        self.assertAlmostEqual(result[50], 75.0)
        self.assertAlmostEqual(result[200], 100 / 3)
        self.assertEqual(universe.breadth(None), {})

    def test_mss_score_is_mean_with_clipped_channel(self):
        from stockscanner.quality_rank import mss_score
        self.assertAlmostEqual(mss_score(60, 150, 90), (60 + 100 + 90) / 3)
        self.assertIsNone(mss_score(60, None, 90))

    def test_weak_target_ranks_low(self):
        targets = pd.DataFrame({"W": row(0.01, 0.001, 60, 12, -0.2)}).T
        result = universe.percentiles(targets, self.universe)
        self.assertLess(result.loc["W", "quality"], 15)

    def test_without_universe_ranks_within_targets(self):
        targets = pd.DataFrame({"A": row(0.3, 0.1, 10, 1, 0.1), "B": row(0.1, 0.05, 30, 5, -0.1),
                                "C": row(0.2, 0.08, 20, 3, 0.0)}).T
        self.assertEqual(universe.percentiles(targets, None)["quality"].idxmax(), "A")


if __name__ == "__main__":
    unittest.main()
