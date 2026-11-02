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


if __name__ == "__main__":
    unittest.main()
