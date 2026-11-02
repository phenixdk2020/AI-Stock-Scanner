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
