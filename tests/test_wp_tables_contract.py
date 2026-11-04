"""Kontrakt for sortering og søgning: gælder alle tabeller og følger grafrækker med deres aktie."""
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent / "wordpress/hangar18-ai-stock-scanner"


class TablesContractTests(unittest.TestCase):
    def test_script_is_enqueued_on_the_site(self):
        main = (PLUGIN / "hangar18-ai-stock-scanner.php").read_text(encoding="utf-8")
        self.assertIn("plugins_url('assets/tables.js', __FILE__)", main)

    def test_works_on_every_table_and_keeps_detail_rows(self):
        code = (PLUGIN / "assets/tables.js").read_text(encoding="utf-8")
        self.assertIn("querySelectorAll('.asc-table-wrap')", code)
        for marker in ("asc-chart-row", "asc-rule-row", "aria-sort", "sessionStorage"):
            with self.subTest(marker=marker):
                self.assertIn(marker, code)

    def test_sort_buttons_do_not_get_the_dark_button_style(self):
        css = (PLUGIN / "assets/dashboard.css").read_text(encoding="utf-8")
        self.assertIn(".asc-portfolio th button.asc-sort", css)


if __name__ == "__main__":
    unittest.main()
