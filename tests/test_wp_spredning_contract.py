"""Kontrakt for sektor pr. aktie, spredningsadvarsel og papirporteføljens stilling (plugin 0.8.4)."""
import re
import unittest
from pathlib import Path

from stockscanner.playbook import UNIVERSE_COLUMNS

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "wordpress/hangar18-ai-stock-scanner"


def read(path: str) -> str:
    return (PLUGIN / path).read_text(encoding="utf-8")


class SpreadContractTests(unittest.TestCase):
    def test_php_universe_columns_match_python(self):
        php = read("includes/class-asc-playbook.php")
        block = re.search(r"private const UNIVERSE_COLUMNS = \[(.*?)\];", php, re.DOTALL)
        self.assertIsNotNone(block)
        self.assertEqual(re.findall(r"'([a-z_]+)'", block.group(1)), UNIVERSE_COLUMNS)
        self.assertEqual(UNIVERSE_COLUMNS[-3:], ["size", "liquidity", "sector"])   # sektor sidst, som størrelse og likviditet

    def test_sector_is_cleaned_and_shown(self):
        php = read("includes/class-asc-playbook.php")
        self.assertIn("'liquidity' => 20, 'sector' => 40,", php)                      # aktier i snapshottet
        self.assertIn("['region', 'size', 'liquidity', 'sector']", php)                # universets tekstkolonner
        self.assertIn("'paper_score' => self::clean_paper_score(", php)
        for head in ("['Aktie', 'Sektor', 'Handling',", "['Aktie', 'Samlet', 'Sektor', 'Entry',"):
            with self.subTest(head=head):
                self.assertIn(head, php)
        self.assertIn('<td colspan="20">', php)                                        # mandagslisten har en kolonne mere

    def test_warning_is_wired_into_every_page(self):
        php = read("includes/class-asc-playbook.php")
        self.assertIn("entry_concentration_html($entry_sectors)", php)                 # Find aktier og Overblik
        self.assertIn("sector_count_line($entry_sectors)", php)
        self.assertIn("'købskandidater'", php)                                         # mandagslisten
        self.assertIn("ASC_Playbook::own_sector_warning(", read("includes/class-asc-simulator.php"))
        self.assertIn("ASC_Playbook::own_sector_warning(", read("includes/class-asc-portfolio.php"))
        self.assertIn("ASC_Playbook::paper_brief(", read("includes/class-asc-portfolio.php"))
        self.assertIn("paper_score_html(", php)

    def test_rules_are_unchanged_by_the_warning(self):
        php = read("includes/class-asc-playbook.php")
        verdict = php[php.index("public static function entry_verdict"):php.index("private static function value_rows")]
        self.assertNotIn("sector", verdict)                                            # blokerer og ændrer intet
        self.assertIn("SECTOR_MAX_ENTRIES = 3", php)
        self.assertIn("SECTOR_SHARE = 0.4", php)
        self.assertIn("SECTOR_MIN_TOTAL = 4", php)
        self.assertIn("Under 3 måneder siger tallene ikke noget.", php)

    def test_new_columns_and_terms_are_explained(self):
        self.assertIn("'sektor':", read("assets/tables.js"))
        help_page = read("includes/class-asc-help.php")
        for term in ("['Sektor',", "['Spredningsadvarsel',", "['Stilling mod RSP',"):
            with self.subTest(term=term):
                self.assertIn(term, help_page)

    def test_ci_runs_the_php_test(self):
        ci = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
        self.assertIn("php tests/wp_sector_spread.php", ci)
        self.assertTrue((ROOT / "tests/wp_sector_spread.php").is_file())


if __name__ == "__main__":
    unittest.main()
