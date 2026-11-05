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

    def test_every_playbook_column_is_explained(self):
        code = (PLUGIN / "assets/tables.js").read_text(encoding="utf-8")
        for column in ("handling", "stockmap", "tpi", "mti", "kvalitet", "moat", "mss-score", "værdi", "momentum",
                       "kanal", "peg", "asymmetri", "regnskab", "størrelsesklasse", "likviditet", "nyheder"):
            with self.subTest(column=column):
                self.assertIn(f"'{column}':", code)
        self.assertIn("Hvad betyder kolonnerne?", code)

    def test_market_filter_reads_the_symbol(self):
        code = (PLUGIN / "assets/tables.js").read_text(encoding="utf-8")
        for marker in ("Alle markeder", "CO: 'Danmark'", "asc_ticker=", "':market'"):
            with self.subTest(marker=marker):
                self.assertIn(marker, code)

    def test_help_page_is_in_the_menu_and_explains_every_measure(self):
        portfolio = (PLUGIN / "includes/class-asc-portfolio.php").read_text(encoding="utf-8")
        self.assertIn("'help' => ['Hjælp'", portfolio)
        self.assertIn("echo ASC_Help::render()", portfolio)
        self.assertIn("ASC_Help::register()", (PLUGIN / "hangar18-ai-stock-scanner.php").read_text(encoding="utf-8"))
        guide = (PLUGIN / "includes/class-asc-help.php").read_text(encoding="utf-8")
        for term in ("KØB-KANDIDAT", "'Kanal'", "'TPI'", "'MTI'", "'PEG'", "'Asymmetri'", "'MSS-score'", "'StockMap'"):
            with self.subTest(term=term):
                self.assertIn(term, guide)

    def test_value_tab_covers_the_universe_and_never_invents_a_verdict(self):
        code = (PLUGIN / "includes/class-asc-playbook.php").read_text(encoding="utf-8")
        self.assertIn("'value' => 'Find aktier'", code)
        self.assertIn("'find' => ['Find aktier'", (PLUGIN / "includes/class-asc-portfolio.php").read_text(encoding="utf-8"))
        self.assertIn("$show = 'best'", code)      # Nej-aktier er skjult som standard
        self.assertIn("self::tab_value($data)", code)
        body = code[code.index("public static function entry_verdict"):code.index("private static function tab_value")]
        self.assertIn("return [0, 'Entry']", body)
        self.assertEqual(body.count("'Entry'"), 1)     # kun KØB-KANDIDAT giver Entry
        self.assertIn("'KØB-KANDIDAT'", body)
        self.assertIn("Ingen vurdering", body)

    def test_abbreviations_are_explained(self):
        guide = (PLUGIN / "includes/class-asc-help.php").read_text(encoding="utf-8")
        self.assertIn("Forkortelser og fagord", guide)
        for term in ("'MSS'", "'TPI'", "'MTI'", "'P/E'", "'EPS'", "'PEG'", "'RSP'", "'ETF'", "'ATR'", "'ECB'", "'ISIN'"):
            with self.subTest(term=term):
                self.assertIn(term, guide)

    def test_cheap_filter_does_not_change_the_entry_rule(self):
        code = (PLUGIN / "includes/class-asc-playbook.php").read_text(encoding="utf-8")
        body = code[code.index("public static function entry_verdict"):code.index("private static function value_rows")]
        self.assertNotIn("CHEAP_VALUE", body)
        self.assertNotIn("DEAR_VALUE", body)
        self.assertIn("'cheap' => 'Billig på begge mål", code)
        self.assertIn("$stock['peg'] ?? $row['peg']", code)

    def test_abbreviations_are_explained_on_every_page(self):
        code = (PLUGIN / "assets/tables.js").read_text(encoding="utf-8")
        self.assertIn("Forkortelser på denne side", code)
        self.assertIn("function addTerms()", code)
        for term in ("'TPI':", "'MTI':", "'PEG':", "'P/E':", "'EPS':", "'RSP':", "'ETF':", "'ATR':"):
            with self.subTest(term=term):
                self.assertIn(term, code)

    def test_watchlist_shows_entry_and_nothing_is_bought_automatically(self):
        watch = (PLUGIN / "includes/class-asc-watchlist.php").read_text(encoding="utf-8")
        code = (PLUGIN / "includes/class-asc-playbook.php").read_text(encoding="utf-8")
        self.assertIn("ASC_Playbook::entry_for((string)$ticker)", watch)
        self.assertIn("colspan=\"6\"", watch)
        self.assertIn('value="asc_watch_add"', code)
        self.assertNotIn("asc_sim_buy", code[code.index("public static function entry_for"):code.index("private static function tab_scores")])

    def test_total_score_never_guesses_and_is_not_a_buy_rule(self):
        code = (PLUGIN / "includes/class-asc-playbook.php").read_text(encoding="utf-8")
        body = code[code.index("public static function total_score"):code.index("private static function value_rows")]
        self.assertIn("return null", body)
        verdict = code[code.index("public static function entry_verdict"):code.index("public static function entry_for")]
        self.assertNotIn("total", verdict)

    def test_sort_buttons_do_not_get_the_dark_button_style(self):
        css = (PLUGIN / "assets/dashboard.css").read_text(encoding="utf-8")
        self.assertIn(".asc-portfolio th button.asc-sort", css)


if __name__ == "__main__":
    unittest.main()
