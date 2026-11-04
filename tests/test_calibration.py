"""Offline tests af B-15-hjælperne (stockscanner/calibration.py)."""
import unittest
from datetime import date

import pandas as pd

from stockscanner import calibration as c


class DateTests(unittest.TestCase):
    def test_video_date_formats(self):
        self.assertEqual(c.video_date("Investeringswebinar for begyndere - 13-6-24"), date(2024, 6, 13))
        self.assertEqual(c.video_date("MyStockScanner LIVE Webinar (Danish) 21-01-2026"), date(2026, 1, 21))
        self.assertEqual(c.video_date("MyStockScanner begynder-webinar 4-3-26"), date(2026, 3, 4))
        self.assertIsNone(c.video_date("Webinar MTCI"))
        self.assertIsNone(c.video_date("Dato 31-2-24"))

    def test_resolve_exact_month_and_video(self):
        self.assertEqual(c.resolve_date("2024-06-13", ""), (date(2024, 6, 13), c.EXACT, False))
        self.assertEqual(c.resolve_date("2024-10-29 (usikkert)", ""), (date(2024, 10, 29), c.EXACT, True))
        self.assertEqual(c.resolve_date("2024-10", ""), (date(2024, 10, 15), c.MONTH, False))
        self.assertEqual(c.resolve_date("optagelsesdato", "Webinar 5-3-24"), (date(2024, 3, 5), c.VIDEO, True))
        self.assertEqual(c.resolve_date("ukendt", "Webinar 5-3-24")[1], c.VIDEO)

    def test_resolve_rejects_vague(self):
        for raw in ("2024 (usikkert)", "2019-2026 (backtest)", "ukendt (i dag)", "31. maj (år ukendt)", "ukendt"):
            self.assertIsNone(c.resolve_date(raw, "Webinar uden dato"), raw)
        self.assertIsNone(c.resolve_date("ukendt (i dag)", "Webinar 5-3-24"))

    def test_candidate_dates(self):
        self.assertEqual(c.candidate_dates(date(2024, 6, 13), c.EXACT), [date(2024, 6, 13)])
        many = c.candidate_dates(date(2024, 6, 15), c.MONTH)
        self.assertEqual(many[0], date(2024, 6, 15))
        self.assertEqual(len(many), 7)


class NameTests(unittest.TestCase):
    def test_normalize_and_clean(self):
        self.assertEqual(c.normalize_name("Ørsted"), "orsted")
        self.assertEqual(c.normalize_name("Mærsk"), "maersk")
        self.assertEqual(c.clean_name("Micron (MU)"), ("Micron", "MU"))
        self.assertEqual(c.clean_name("Ambu (Ambo, usikkert)"), ("Ambu", ""))

    def test_is_company(self):
        self.assertTrue(c.is_company("Novo Nordisk"))
        self.assertTrue(c.is_company("Micron (MU)"))
        for name in ("TPI Plus (portefoelje)", "Sverige (land)", "S&P 500 (indeks)", "(ingen aktie)",
                     "Value Momentum (strategi)", "RSP"):
            self.assertFalse(c.is_company(name), name)


class ToolAndParseTests(unittest.TestCase):
    def test_tool_group(self):
        self.assertEqual(c.tool_group("TPI lang trend"), "tpi")
        self.assertEqual(c.tool_group("TPI+quality"), "andet")
        self.assertEqual(c.tool_group("TPI Swing screener"), "andet")
        self.assertEqual(c.tool_group("stockmap aktie"), "stockmap")
        self.assertEqual(c.tool_group("MTI"), "mti")
        self.assertEqual(c.tool_group("value graf"), "valuekanal")
        self.assertEqual(c.tool_group("kvalitetsscore"), "quality")
        self.assertEqual(c.tool_group("price earning gennemsnit"), "pe_gennemsnit")
        self.assertEqual(c.tool_group("200-dages glidende gennemsnit"), "sma200")
        self.assertEqual(c.tool_group("regressionskanal"), "regression")

    def test_numbers(self):
        self.assertEqual(c.parse_number("78,5"), 78.5)
        self.assertIsNone(c.parse_number("okay, ingen tal"))
        self.assertEqual(c.first_number("100 (top 1 pct. i Danmark)"), 100)
        self.assertEqual(c.first_number("29 til 42"), 35.5)
        self.assertEqual(c.first_number("31-33"), 32)
        self.assertEqual(c.first_number("ca. 40 ved salg"), 40)
        self.assertIsNone(c.first_number("høj"))
        self.assertEqual(c.parse_years("3 aar"), 3)
        self.assertIsNone(c.parse_years("nu"))

    def test_quadrant_and_arrow(self):
        self.assertEqual(c.parse_quadrant("grøn zone, pil peger nedad"), "leading")
        self.assertEqual(c.parse_quadrant("gul, pil peger nedad"), "weakening")
        self.assertEqual(c.parse_quadrant("rød zone, begynder at tippe op"), "lagging")
        self.assertIsNone(c.parse_quadrant("begyndt at tippe op"))
        self.assertEqual(c.parse_arrow("grøn zone, pil peger nedad"), "ned")
        self.assertEqual(c.parse_arrow("svagt begyndt at tippe op i grøn"), "op")
        self.assertIsNone(c.parse_arrow("simpelt købsignal"))

    def test_tpi_states(self):
        self.assertEqual(c.parse_tpi_long("grøn"), "gron")
        self.assertEqual(c.parse_tpi_long("roed"), "rod")
        self.assertEqual(c.parse_tpi_long("groen opadgaaende trend"), "gron")
        self.assertIsNone(c.parse_tpi_long("grøn optrend, men rød dag"))
        self.assertEqual(c.parse_tpi_short("oversolgt akkumulering"), "oversolgt")
        self.assertEqual(c.parse_tpi_short("overkøbt akkumulering (grå)"), "overkobt")
        self.assertEqual(c.parse_tpi_short("overkoebt"), "overkobt")
        self.assertIsNone(c.parse_tpi_short("grøn"))

    def test_mti_sma_regression(self):
        self.assertEqual(c.parse_mti("dobbelt grøn, køb"), "dobbelt_gron")
        self.assertEqual(c.parse_mti("dobbelt groen"), "dobbelt_gron")
        self.assertEqual(c.parse_mti("dobbelt rød"), "ikke_dobbelt")
        self.assertEqual(c.parse_mti("roed"), "ikke_dobbelt")
        self.assertIsNone(c.parse_mti("lidt af hvert"))
        self.assertEqual(c.parse_sma_side("over (opnaaet)"), "over")
        self.assertEqual(c.parse_sma_side("under, no-go"), "under")
        self.assertIsNone(c.parse_sma_side("brudt"))
        self.assertEqual(c.parse_regression_class("skudt ud af nederste kanal"), "under")
        self.assertEqual(c.parse_regression_class("brud ned under nederste kanallinje"), "under")
        self.assertEqual(c.parse_regression_class("stærkt skud op uden for 2 standardafvigelser"), "over")
        self.assertEqual(c.parse_regression_class("tilbage i kanal, holdes"), "inde")
        self.assertIsNone(c.parse_regression_class("ikke brugbar"))

    def test_cheap_expensive(self):
        self.assertEqual(c.classify_cheap_expensive("blå zone = billig"), "billig")
        self.assertEqual(c.classify_cheap_expensive("dyrt omraade"), "dyr")
        self.assertEqual(c.classify_cheap_expensive("P/E over 50, solgt"), "dyr")
        self.assertEqual(c.classify_cheap_expensive("nederste halvdel af kanalen = billig zone"), "billig")
        self.assertIsNone(c.classify_cheap_expensive("naesten sidelaens"))
        self.assertIsNone(c.classify_cheap_expensive("billig men dyr"))


class StatTests(unittest.TestCase):
    def test_hit_rate_and_confusion(self):
        pairs = [("a", "a"), ("a", "b"), ("b", "b"), ("b", "b")]
        self.assertEqual(c.hit_rate(pairs), {"n": 4, "hits": 3, "rate": 75.0})
        self.assertEqual(c.hit_rate([])["rate"], None)
        table = c.confusion(pairs)
        self.assertEqual(table.loc["a", "b"], 1)
        self.assertEqual(table.loc["b", "b"], 2)
        self.assertEqual(table.loc["b", "a"] if "a" in table.columns and "b" in table.index else 0, 0)

    def test_majority_rate(self):
        self.assertEqual(c.majority_rate(["g", "g", "r", "g"]), 75.0)
        self.assertIsNone(c.majority_rate([]))

    def test_spearman(self):
        self.assertAlmostEqual(c.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertAlmostEqual(c.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)
        self.assertIsNone(c.spearman([1, 2], [1, 2]))
        self.assertIsNone(c.spearman([1, 2, 3], [5, 5, 5]))
        self.assertIsNone(c.spearman([1, None, 3], [1, 2, None]))

    def test_binomial_p(self):
        self.assertAlmostEqual(c.binomial_p(5, 5, 0.5), 1 / 32)
        self.assertAlmostEqual(c.binomial_p(0, 5, 0.5), 1.0)
        self.assertIsNone(c.binomial_p(0, 0, 0.5))

    def test_percentile_and_channel(self):
        series = pd.Series([10, 20, 30, 40])
        self.assertEqual(c.percentile_of(25, series), 50.0)
        self.assertEqual(c.percentile_of(40, series), 87.5)
        self.assertIsNone(c.percentile_of(1, pd.Series([], dtype=float)))
        self.assertEqual(c.channel_position(15, [10, 20, 15]), 0.5)
        self.assertIsNone(c.channel_position(15, [10]))
        self.assertIsNone(c.channel_position(15, [12, 12]))


class ExtraTests(unittest.TestCase):
    def test_quality_percentile(self):
        self.assertEqual(c.parse_quality_percentile("99"), 99)
        self.assertEqual(c.parse_quality_percentile("100 (top 1 pct. i Danmark)"), 100)
        self.assertEqual(c.parse_quality_percentile("85 (bedre end ca. 84 % af US-aktier)"), 85)
        self.assertEqual(c.parse_quality_percentile("top femtedel (top 20 procent)"), 80)
        self.assertIsNone(c.parse_quality_percentile("7,6"))
        self.assertIsNone(c.parse_quality_percentile("okay, ingen tal"))
        self.assertEqual(c.parse_quality_percentile("78,5"), 78.5)

    def test_refers_to_past(self):
        self.assertTrue(c.refers_to_past("ca. 40 ved salg"))
        self.assertTrue(c.refers_to_past("P/E højt ca. 45 (sidste år), solgt"))
        self.assertTrue(c.refers_to_past("billig", "købt"))
        self.assertFalse(c.refers_to_past("blå zone = billig"))
        self.assertTrue(c.refers_to_past("P/E omkring 40 ved toppen, dyr zone"))
        self.assertFalse(c.refers_to_past("dyrt omraade"))

    def test_chance_rate(self):
        self.assertEqual(c.chance_rate([("a", "a"), ("a", "a")]), 100.0)
        self.assertAlmostEqual(c.chance_rate([("a", "a"), ("b", "b"), ("a", "b"), ("b", "a")]), 50.0)
        self.assertIsNone(c.chance_rate([]))


if __name__ == "__main__":
    unittest.main()
