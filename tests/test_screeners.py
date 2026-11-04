"""Offline tests af screenerne og regionsfunktionerne."""
import unittest

import pandas as pd

from stockscanner import universe
from stockscanner.screeners import screen


def factor(region, cap, long=True, week="neutral", week_green=True, day=True, sma50=True, upside=15, peg=1.5):
    return {"region": region, "x_mcap_usd": cap, "t_long_green": long, "t_week_state": week,
            "t_week_green": week_green, "t_day_green": day, "t_above_sma50": sma50, "x_upside": upside, "x_peg": peg}


class ScreenerTests(unittest.TestCase):
    def setUp(self):
        self.factors = pd.DataFrame({
            "BIG": factor("USA", 50e9, week="oversolgt"),
            "SMALL": factor("USA", 1e9),
            "RED": factor("USA", 50e9, long=False, week="oversolgt"),
            "NOVO-B.CO": factor("Norden", 300e9, week="oversolgt", day=False),
            "SAP.DE": factor("Europa", 200e9, week="oversolgt"),
        }).T
        self.scores = pd.DataFrame({"quality": [80, 90, 90, 70, 75], "value": [70, 90, 90, 60, 40],
                                    "momentum": [50, 50, 50, 50, 50]}, index=self.factors.index)

    def test_triple_green_needs_all_three_and_size(self):
        self.assertEqual(sorted(screen("triple-green", self.factors, self.scores).index), ["BIG", "SAP.DE"])

    def test_tpi_trend_is_nordic_oversold(self):
        self.assertEqual(list(screen("tpi-trend", self.factors, self.scores).index), ["NOVO-B.CO"])

    def test_stock_of_the_day(self):
        self.assertEqual(list(screen("stock-of-the-day", self.factors, self.scores).index), ["BIG"])
        expensive = self.factors.copy()
        expensive.loc["BIG", "x_peg"] = 3.5
        self.assertTrue(screen("stock-of-the-day", expensive, self.scores).empty)

    def test_unknown_screener(self):
        with self.assertRaises(ValueError):
            screen("nope", self.factors, self.scores)


class RegionTests(unittest.TestCase):
    def test_region(self):
        self.assertEqual(universe.region("MSFT"), "USA")
        self.assertEqual(universe.region("NOVO-B.CO"), "Norden")
        self.assertEqual(universe.region("ASML.AS"), "Europa")

    def test_info_extras_converts_to_usd(self):
        extras = universe.info_extras({"marketCap": 1e12, "currency": "DKK", "currentPrice": 100,
                                       "targetMeanPrice": 120, "trailingPegRatio": 1.4})
        self.assertAlmostEqual(extras["x_mcap_usd"], 1e12 * universe.FX_TO_USD["DKK"])
        self.assertAlmostEqual(extras["x_upside"], 20)
        self.assertEqual(extras["x_peg"], 1.4)

    def test_buy_funnel_needs_stockmap_buy_and_quality(self):
        factors = pd.DataFrame({"t_stockmap": ["køb 2026-10-30", "køb 2026-10-30", "salg 2026-10-30", None]},
                               index=["GOOD", "WEAK", "SOLD", "NONE"])
        scores = pd.DataFrame({"quality": [80, 40, 90, 95]}, index=factors.index)
        self.assertEqual(universe.buy_funnel(factors, scores), ["GOOD"])
        self.assertEqual(universe.buy_funnel(factors.drop(columns="t_stockmap"), scores), [])
        self.assertEqual(universe.buy_funnel(None, None), [])

    def test_percentiles_by_region_rank_within_region(self):
        rows = {"US1": 0.1, "US2": 0.2, "US3": 0.15, "A.CO": 0.05, "B.CO": 0.06, "C.CO": 0.04}
        frame = pd.DataFrame({t: {"q_roce": v, "qs_roce": v * 100, "q_roa": v, "qs_roa": v * 100, "v_pe": 10,
                                  "m_ret_3m": v} for t, v in rows.items()}).T
        result = universe.percentiles(frame, None, by_region=True)
        self.assertEqual(result.loc["B.CO", "quality"], result.loc["US2", "quality"])   # bedst i hver sin region
        self.assertGreater(universe.percentiles(frame, None).loc["US2", "quality"],
                           universe.percentiles(frame, None).loc["B.CO", "quality"])


if __name__ == "__main__":
    unittest.main()


def volume_history(volumes, close=10.0):
    index = pd.bdate_range(end="2026-10-30", periods=len(volumes))
    return pd.DataFrame({"Close": float(close), "Volume": volumes}, index=index, dtype=float)


class SizeAndLiquidityTests(unittest.TestCase):
    def test_size_class_boundaries(self):
        cases = [(300e9, "Mega"), (200e9, "Large"), (10e9, "Large"), (9.9e9, "Mid"), (2e9, "Mid"),
                 (1.9e9, "Small"), (0.3e9, "Small"), (0.29e9, "Micro"), (1.0, "Micro")]
        for cap, expected in cases:
            self.assertEqual(universe.size_class(cap), expected, cap)

    def test_size_class_unknown(self):
        for cap in (None, float("nan"), 0, 0.0, -5e9, "abc"):
            self.assertEqual(universe.size_class(cap), "ukendt", cap)

    def test_liquidity_class(self):
        self.assertEqual(universe.liquidity_class(20e6, 0), "Høj")
        self.assertEqual(universe.liquidity_class(5e6, 0), "Middel")
        self.assertEqual(universe.liquidity_class(2e6, 2), "Middel")
        self.assertEqual(universe.liquidity_class(1.9e6, 0), "Lav")
        self.assertEqual(universe.liquidity_class(50e6, 3), "Lav")          # for mange dage uden handel
        self.assertEqual(universe.liquidity_class(50e6, None), "Høj")
        for adv in (None, float("nan")):
            self.assertEqual(universe.liquidity_class(adv, 0), "ukendt")

    def test_liquidity_facts_uses_last_21_days_and_rate(self):
        history = volume_history([1.0] * 10 + [1000.0] * 21)
        facts = universe.liquidity_facts(history, 0.5)
        self.assertAlmostEqual(facts["x_adv_usd"], 10.0 * 1000.0 * 0.5)
        self.assertEqual(facts["x_idle_days"], 0)

    def test_liquidity_facts_counts_idle_days(self):
        history = volume_history([1000.0] * 15 + [0.0, 0.0, float("nan")] + [1000.0] * 3)
        facts = universe.liquidity_facts(history, 1.0)
        self.assertEqual(facts["x_idle_days"], 3)
        self.assertAlmostEqual(facts["x_adv_usd"], 10.0 * 1000.0 * 18 / 21)

    def test_liquidity_facts_empty_or_missing_data(self):
        self.assertEqual(universe.liquidity_facts(None, 1.0), {})
        self.assertEqual(universe.liquidity_facts(pd.DataFrame(), 1.0), {})
        self.assertEqual(universe.liquidity_facts(volume_history([]), 1.0), {})
        self.assertEqual(universe.liquidity_facts(volume_history([float("nan")] * 25), 1.0), {})
        self.assertEqual(universe.liquidity_facts(volume_history([1.0] * 25).drop(columns="Volume"), 1.0), {})
        self.assertNotIn("x_adv_usd", universe.liquidity_facts(volume_history([1000.0] * 25), None))

    def test_factor_row_stores_liquidity_with_rate_from_mcap(self):
        history = volume_history([1000.0] * 30)
        row = universe.factor_row("X.CO", lambda t: {}, lambda t: {"marketCap": 1e9, "currency": "DKK"},
                                  lambda t: history)
        self.assertAlmostEqual(row["x_adv_usd"], 10.0 * 1000.0 * universe.FX_TO_USD["DKK"])
        self.assertEqual(row["x_idle_days"], 0)
        no_rate = universe.factor_row("X", lambda t: {}, lambda t: {}, lambda t: history)
        self.assertNotIn("x_adv_usd", no_rate)

    def test_buy_funnel_drops_thin_stocks_but_lets_unknown_through(self):
        factors = pd.DataFrame({"t_stockmap": ["køb 2026-10-30"] * 5,
                                "x_adv_usd": [50e6, 1e6, float("nan"), 50e6, 5e6],
                                "x_idle_days": [0, 0, float("nan"), 5, float("nan")]},
                               index=["LIQ", "THIN", "UNKNOWN", "IDLE", "MID"])
        scores = pd.DataFrame({"quality": [80, 90, 70, 95, 60]}, index=factors.index)
        self.assertEqual(universe.buy_funnel(factors, scores), ["LIQ", "UNKNOWN", "MID"])
        self.assertEqual(universe.buy_funnel(factors.drop(columns=["x_adv_usd", "x_idle_days"]), scores),
                         ["IDLE", "THIN", "LIQ", "UNKNOWN", "MID"])
        self.assertEqual(universe.buy_funnel(factors.drop(columns="x_idle_days"), scores),
                         ["IDLE", "LIQ", "UNKNOWN", "MID"])
