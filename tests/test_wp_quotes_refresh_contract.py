"""Kontrakt for kursopdateringen: sidevisning henter alle forældede kurser, og 15-minutters kørslen springer ingen over."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUOTES = ROOT / "wordpress/hangar18-ai-stock-scanner/includes/class-asc-market-quotes.php"


class QuotesRefreshContractTests(unittest.TestCase):
    def setUp(self):
        self.code = QUOTES.read_text(encoding="utf-8")

    def constant(self, name):
        return int(re.search(rf"private const {name} = (\d+);", self.code).group(1))

    def test_cache_expires_before_next_cron_run(self):
        self.assertLess(self.constant("CACHE_AGE"), self.constant("AGE"))
        self.assertIn("set_transient($key, $quote, self::CACHE_AGE)", self.code)

    def test_failed_fetch_is_retried_soon(self):
        self.assertLess(self.constant("RETRY_AFTER"), self.constant("CACHE_AGE"))
        self.assertIn("set_transient($cooldown, 1, self::RETRY_AFTER)", self.code)

    def test_page_refresh_needs_login_and_runs_outside_the_page_budget(self):
        self.assertIn("'/quotes/refresh'", self.code)
        self.assertIn("static fn() => is_user_logged_in()", self.code)
        self.assertIn("'X-WP-Nonce'".replace("'", '"'), self.code)
        self.assertIn("array_slice($due, 0, self::REFRESH_BATCH)", self.code)

    def test_reload_only_when_new_quotes_arrived(self):
        self.assertIn('function e(c){if(c>0&&!b()){location.reload();}}', self.code)
        self.assertIn('addEventListener("visibilitychange",t)', self.code)
        self.assertIn("wp_create_nonce('wp_rest')", self.code)


if __name__ == "__main__":
    unittest.main()
