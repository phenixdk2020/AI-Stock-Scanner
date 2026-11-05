"""Tjeklisten på hjemmesiden skal bruge samme grænser som købsreglen i Python."""
import re
import unittest
from pathlib import Path

from stockscanner import playbook, sizing, weekly_list

PLUGIN = Path(__file__).resolve().parent.parent / "wordpress" / "hangar18-ai-stock-scanner"
CODE = (PLUGIN / "includes/class-asc-entry-check.php").read_text(encoding="utf-8")


def constant(name):
    return float(re.search(rf"const {name} = ([0-9.]+);", CODE).group(1))


class EntryCheckContract(unittest.TestCase):
    def test_limits_match_the_buy_rule(self):
        self.assertEqual(constant("MIN_QUALITY"), weekly_list.MIN_QUALITY)
        self.assertEqual(constant("MIN_VALUE_SCORE"), weekly_list.MIN_VALUE_SCORE)
        self.assertEqual(constant("MAX_PEG"), weekly_list.MAX_PEG)
        self.assertEqual(constant("MIN_ASYMMETRY"), weekly_list.MIN_ASYMMETRY)
        self.assertEqual(constant("ATR_MULTIPLE"), sizing.DEFAULTS["atr_gange"])

    def test_loaded_after_playbook_and_used_on_the_stock_page(self):
        main = (PLUGIN / "hangar18-ai-stock-scanner.php").read_text(encoding="utf-8")
        self.assertIn("class-asc-entry-check.php", main)
        code = (PLUGIN / "includes/class-asc-playbook.php").read_text(encoding="utf-8")
        self.assertIn("ASC_Entry_Check::render($ticker", code)

    def test_extra_fields_pass_the_sanitizer(self):
        code = (PLUGIN / "includes/class-asc-playbook.php").read_text(encoding="utf-8")
        for field in ("'eps_rising'", "earnings_estimate", "clean_insiders", "clean_why_cheap"):
            self.assertIn(field, code)

    def test_estimated_earnings_keeps_a_stock_out_of_top_but_is_no_requirement(self):
        code = (PLUGIN / "includes/class-asc-playbook.php").read_text(encoding="utf-8")
        body = code[code.index("public static function top_candidates"):code.index("public static function render_find")]
        self.assertIn("earnings_estimate", body)
        self.assertIn("spærrer ikke", CODE)


class PayloadTests(unittest.TestCase):
    def test_extras_are_display_only_and_shortened(self):
        self.assertEqual(playbook.insiders_entry({"buyers": 2, "buys": 3, "value_usd": 1234.5, "last_buy": "2026-10-01"}),
                         {"buyers": 2, "buys": 3, "sells": 0, "value_usd": 1234.0,
                          "last_buy": "2026-10-01", "days": 90})
        answer = playbook.why_cheap_entry({"hvorfor_billig": "x" * 900, "risici": ["a", "b", "c", "d"], "dato": "2026-11-05"})
        self.assertEqual(len(answer["hvorfor_billig"]), 400)
        self.assertEqual(answer["risici"], ["a", "b", "c"])
        self.assertEqual(answer["vaerdifaelde"], "ukendt")


if __name__ == "__main__":
    unittest.main()
