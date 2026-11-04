"""Kildetjek af pluginets regnskabsnedtælling og regnskabsrisiko (ingen PHP lokalt, derfor kun tekstkontrol)."""
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent / "wordpress" / "hangar18-ai-stock-scanner"
PLAYBOOK = PLUGIN / "includes" / "class-asc-playbook.php"
PORTFOLIO = PLUGIN / "includes" / "class-asc-portfolio.php"


class EarningsContractTests(unittest.TestCase):
    def setUp(self):
        self.playbook = PLAYBOOK.read_text(encoding="utf-8")
        self.portfolio = PORTFOLIO.read_text(encoding="utf-8")

    def test_countdown_texts_and_block_label(self):
        for text in ("Dato ukendt", "'om 1 dag'", "'i dag'", "afholdt for ", "spærret: regnskab",
                     "wp_date('Y-m-d')", "EARNINGS_BLOCK_DAYS = 7"):
            self.assertIn(text, self.playbook)
        start = self.playbook.index("function earnings_block_badge")
        self.assertIn("KØB-KANDIDAT", self.playbook[start:start + 300])

    def test_old_plain_earnings_cell_is_gone(self):
        self.assertNotIn("self::s($stock['earnings'] ?? null)", self.playbook)
        self.assertEqual(self.playbook.count("self::earnings_html($stock['earnings'] ?? null)"), 3)

    def test_risk_is_sanitized_by_name_and_level_is_whitelisted(self):
        self.assertIn("$out['earnings_risk'] = self::clean_earnings_risk($raw['earnings_risk'] ?? null);", self.playbook)
        self.assertIn("RISK_LEVELS = ['Lav', 'Middel', 'Høj']", self.playbook)
        start = self.playbook.index("function clean_earnings_risk")
        block = self.playbook[start:start + 1600]
        for field in ("'reasons'", "'avg_move_pct'", "'down_share_pct'", "'count'",
                      "clean_string($reason, 160)", "array_slice("):
            self.assertIn(field, block)

    def test_every_rendering_carries_the_disclaimer_and_escapes(self):
        self.assertIn("RISK_DISCLAIMER = 'Risikomål, ikke et salgssignal.'", self.playbook)
        start = self.playbook.index("function risk_html")
        block = self.playbook[start:start + 2400]
        self.assertIn("esc_html(self::RISK_DISCLAIMER)", block)
        self.assertIn("return '';", block)       # ingen payload-data = intet vist
        self.assertEqual(self.playbook.count("self::risk_html($stock"), 3)      # mandagsliste, analyse, portefølje

    def test_portfolio_shows_money_amount_on_owned_row(self):
        self.assertIn("ASC_Playbook::earnings_risk_row($ticker, $risk_value, $risk_value_dkk, $currency, 8)",
                      self.portfolio)
        self.assertIn("på din position", self.playbook)


if __name__ == "__main__":
    unittest.main()
