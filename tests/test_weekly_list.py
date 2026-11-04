"""Offline tests af mandagslistens klassifikation."""
import unittest

from stockscanner.weekly_list import classify


class ClassifyTests(unittest.TestCase):
    def test_sell_signal_not_owned_is_only_arrow_down(self):
        self.assertEqual(classify("salg 2026-10-30", True, 90, 80, 1.0)[0], "pil ned")

    def test_owned_stock_uses_exit_reasons(self):
        self.assertEqual(classify("", False, 90, 80, 1.0, ["Supertrend ×3 er vendt ned"])[0], "SÆLG (ejet)")
        self.assertEqual(classify("køb 2026-10-30", False, 90, 80, 1.0, [])[0], "BEHOLD (ejet)")

    def test_buy_candidate_when_all_filters_pass(self):
        action, reasons = classify("køb 2026-10-30", False, 75, 60, 1.2)
        self.assertEqual(action, "KØB-KANDIDAT")
        self.assertEqual(reasons, ["alle krav opfyldt"])

    def test_buy_signal_but_low_quality_or_expensive(self):
        action, reasons = classify("køb 2026-10-30", False, 40, 30, 3.0)
        self.assertEqual(action, "hold øje")
        self.assertEqual(len(reasons), 3)

    def test_unknown_peg_does_not_block(self):
        self.assertEqual(classify("køb 2026-10-30", False, 70, 55, None)[0], "KØB-KANDIDAT")

    def test_no_signal(self):
        self.assertEqual(classify("", False, 99, 99, 0.5)[0], "hold øje")

    def test_low_asymmetry_blocks_buy(self):
        action, reasons = classify("køb 2026-10-30", False, 75, 60, 1.2, asymmetry=2.0)
        self.assertEqual(action, "hold øje")
        self.assertIn("asymmetri 2.0 < 3", reasons)
        self.assertEqual(classify("køb 2026-10-30", False, 75, 60, 1.2, asymmetry=float("inf"))[0], "KØB-KANDIDAT")

    def test_earnings_within_a_week_blocks_buy(self):
        self.assertEqual(classify("køb 2026-10-30", False, 75, 60, 1.2, earnings_days=2)[1], ["regnskab om 2 d"])
        self.assertEqual(classify("køb 2026-10-30", False, 75, 60, 1.2, earnings_days=8)[0], "KØB-KANDIDAT")
        self.assertEqual(classify("køb 2026-10-30", False, 75, 60, 1.2, earnings_days=-1)[0], "KØB-KANDIDAT")

    def test_value_trap_blocks_buy_and_is_shown_for_owned(self):
        trap = "value trap: EPS +1y -6.0 % på 90 d"
        self.assertEqual(classify("køb 2026-10-30", False, 75, 60, 1.2, trap=trap), ("hold øje", [trap]))
        self.assertIn(trap, classify("", False, 90, 80, 1.0, [], trap=trap)[1])


class AsymmetryOfTests(unittest.TestCase):
    def test_below_bear_line_is_infinite(self):
        from types import SimpleNamespace
        from stockscanner.weekly_list import asymmetry_of
        below = SimpleNamespace(score=120, asymmetry=None, upside_pct={"bear": 5.0})
        self.assertEqual(asymmetry_of(below), float("inf"))
        self.assertIsNone(asymmetry_of(SimpleNamespace(score=None, asymmetry=None, upside_pct={})))
        self.assertEqual(asymmetry_of(SimpleNamespace(score=60, asymmetry=2.5, upside_pct={"bear": -4})), 2.5)


if __name__ == "__main__":
    unittest.main()


class LiquidityTests(unittest.TestCase):
    def test_thin_trading_blocks_buy(self):
        action, reasons = classify("køb 2026-10-30", False, 75, 60, 1.2, liquidity="Lav")
        self.assertEqual(action, "hold øje")
        self.assertEqual(reasons, ["for lidt handel"])

    def test_other_liquidity_values_do_not_block(self):
        for value in (None, "ukendt", "Middel", "Høj"):
            self.assertEqual(classify("køb 2026-10-30", False, 75, 60, 1.2, liquidity=value)[0], "KØB-KANDIDAT")

    def test_owned_stock_is_not_affected(self):
        self.assertEqual(classify("", False, 90, 80, 1.0, [], liquidity="Lav")[0], "BEHOLD (ejet)")
        self.assertEqual(classify("", False, 90, 80, 1.0, ["x"], liquidity="Lav")[0], "SÆLG (ejet)")

    def test_row_has_size_and_liquidity_defaults(self):
        from stockscanner.weekly_list import WeeklyRow

        row = WeeklyRow("A", "hold øje", "–", None, None, None, 1.0, 1.0, 1.0, 1.0, 1.0, "")
        self.assertIsNone(row.size)
        self.assertIsNone(row.liquidity)
