"""Offline tests af de fire algostrategier (B-10) og papirsporingen."""
import importlib.util
import sys
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from stockscanner import strategies

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "strategies_monthly.py"
spec = importlib.util.spec_from_file_location("strategies_monthly", SCRIPT)
monthly = importlib.util.module_from_spec(spec)
sys.modules["strategies_monthly"] = monthly
spec.loader.exec_module(monthly)


def table():
    return pd.DataFrame({
        "quality": [90, 80, 20, 70, None],
        "value": [10, 90, 95, 80, 50],
        "momentum": [95, 20, 30, 85, 60],
        "tpi_state": ["neutral", "oversolgt", "oversolgt", "oversolgt", "neutral"],
        "long_green": [True, True, True, False, True],
    }, index=["A", "B", "C", "D", "E"])


class StrategyTests(unittest.TestCase):
    def test_quality_momentum_needs_both_and_orders(self):
        picks = strategies.quality_momentum(table(), 2)
        self.assertEqual(list(picks.index), ["A", "D"])  # E mangler quality
        self.assertAlmostEqual(picks.loc["A", "score"], 92.5)

    def test_value_momentum_is_inverse_value(self):
        # A: lav value + høj momentum vinder; C (billig, svag momentum) er ikke øverst
        self.assertEqual(strategies.value_momentum(table(), 1).index[0], "A")

    def test_value_quality(self):
        self.assertEqual(list(strategies.value_quality(table(), 2).index), ["B", "D"])

    def test_tpi_plus_requires_oversold_green_and_quality(self):
        picks = strategies.tpi_plus(table(), 15)
        self.assertEqual(list(picks.index), ["B"])  # C for lav quality, D ikke lang grøn

    def test_top_n_limits_and_rank_all(self):
        big = pd.DataFrame({"quality": range(40), "value": range(40), "momentum": range(40),
                            "tpi_state": "neutral", "long_green": True}, index=[f"T{i}" for i in range(40)])
        self.assertEqual(len(strategies.quality_momentum(big, 5)), 5)
        self.assertEqual(len(strategies.quality_momentum(big)), 15)

    def test_missing_columns_give_empty(self):
        self.assertTrue(strategies.tpi_plus(pd.DataFrame({"quality": [90]}, index=["A"])).empty)
        self.assertTrue(strategies.value_quality(pd.DataFrame(index=["A"])).empty)


class MonthlyTests(unittest.TestCase):
    def test_append_is_idempotent_per_month(self):
        picks = strategies.quality_momentum(table(), 2)
        log = monthly.append_month(monthly.load_log("findes_ikke", Path("ikke-en-mappe")), picks,
                                   {"A": 10.0, "D": 20.0}, date(2026, 11, 3))
        self.assertEqual(list(log["ticker"]), ["A", "D"])
        again = monthly.append_month(log, picks, {"A": 11.0, "D": 21.0}, date(2026, 11, 20))
        self.assertEqual(len(again), 2)
        later = monthly.append_month(log, picks, {"A": 11.0, "D": 21.0}, date(2026, 12, 1))
        self.assertEqual(len(later), 4)

    def test_missing_price_is_skipped(self):
        picks = strategies.quality_momentum(table(), 2)
        log = monthly.append_month(monthly.load_log("x", Path("ikke-en-mappe")), picks, {"A": 10.0}, date(2026, 11, 3))
        self.assertEqual(list(log["ticker"]), ["A"])

    def test_returns_vs_benchmark(self):
        log = pd.DataFrame({"maaned": ["2026-11", "2026-11"], "dato": "2026-11-03", "ticker": ["A", "D"],
                            "rang": [1, 2], "score": 1.0, "indgangskurs": [10.0, 20.0]})
        out = monthly.returns_by_month(log, {"A": 11.0, "D": 20.0}, {"2026-11": 100.0}, 102.0)
        self.assertAlmostEqual(out.loc[0, "afkast_pct"], 5.0)
        self.assertAlmostEqual(out.loc[0, "rsp_pct"], 2.0)


if __name__ == "__main__":
    unittest.main()


class StudyStatsTests(unittest.TestCase):
    """CAGR skal regnes på periodens eget udsnit (to perioder af en kendt serie giver forskellige tal)."""

    def test_cagr_differs_between_periods(self):
        spec2 = importlib.util.spec_from_file_location("study_b10", SCRIPT.with_name("study_b10.py"))
        study = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(study)
        index = pd.date_range("2020-01-01", periods=24, freq="MS")
        m = pd.Series([0.01] * 12 + [0.02] * 12, index=index)
        bench = pd.Series(0.0, index=index)
        first, second, both = (study.stats(m.iloc[:12], bench.iloc[:12]), study.stats(m.iloc[12:], bench.iloc[12:]),
                               study.stats(m, bench))
        self.assertAlmostEqual(first["cagr"], (1.01 ** 12 - 1) * 100, places=6)
        self.assertAlmostEqual(second["cagr"], (1.02 ** 12 - 1) * 100, places=6)
        self.assertAlmostEqual(both["cagr"], ((1.01 ** 12 * 1.02 ** 12) ** 0.5 - 1) * 100, places=6)
        self.assertEqual(len({round(first["cagr"], 3), round(second["cagr"], 3), round(both["cagr"], 3)}), 3)
        self.assertAlmostEqual(first["bench_cagr"], 0.0)
