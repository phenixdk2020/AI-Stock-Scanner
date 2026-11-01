"""Regression checks for the WordPress-only personal portfolio feature."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "wordpress" / "hangar18-ai-stock-scanner"
PORTFOLIO = PLUGIN / "includes" / "class-asc-portfolio.php"
QUOTES = PLUGIN / "includes" / "class-asc-market-quotes.php"
MAIN = PLUGIN / "hangar18-ai-stock-scanner.php"


class PortfolioContractTests(unittest.TestCase):
    def test_per_user_storage_and_nonce_protected_actions(self):
        source = PORTFOLIO.read_text(encoding="utf-8")
        for expected in (
            "get_user_meta($user_id, self::USER_META, true)",
            "update_user_meta(get_current_user_id(), self::USER_META",
            "update_user_meta($user_id, self::USER_META",
            "get_current_user_id()",
            "check_admin_referer('asc_portfolio_add')",
            "check_admin_referer('asc_portfolio_delete')",
            "check_admin_referer('asc_portfolio_price')",
            "check_admin_referer('asc_create_home')",
            "current_user_can('manage_options')",
            "auth_redirect()",
            "wp_generate_uuid4()",
            "wp_safe_redirect(",
            "wp_validate_redirect(",
            "is_user_logged_in()",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)

    def test_homepage_explicitly_opted_in(self):
        source = PORTFOLIO.read_text(encoding="utf-8")
        main = MAIN.read_text(encoding="utf-8")
        self.assertIn("update_option('page_on_front', $id)", source)
        self.assertIn("update_option('show_on_front', 'page')", source)
        self.assertIn("admin_post_asc_create_home", source)
        self.assertIn("wp_login_form(", source)
        self.assertIn("wp_logout_url(", source)
        self.assertIn("Opret porteføljeside og sæt som forside", main)
        self.assertIn("[ai_stock_home]", main)
        self.assertIn("ASC_Portfolio::register()", main)

    def test_profit_math_currencies_and_source_display(self):
        source = PORTFOLIO.read_text(encoding="utf-8")
        for required in (
            "$basis = $quantity * $cost",
            "$value = $quantity * $price",
            "$pnl = $value - $basis",
            "100 * ($price / $cost - 1)",
            "$totals[$currency]",
            "Kursvaluta matcher ikke købsvaluta",
            "Manuel kurs",
            "Nordnet",
            "HARB-B.CO",
            "NOBI.ST",
            "wp_date('d-m-Y H:i'",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)
        self.assertNotIn("file_get_contents('https://www.nordnet", source)

    def test_yahoo_is_optional_and_rate_limited(self):
        source = QUOTES.read_text(encoding="utf-8")
        for required in (
            "get_option(self::OPTION, 'no') === 'yes'",
            "private const AGE = 900",
            "get_transient($cooldown)",
            "wp_safe_remote_get(",
            "'redirection' => 0",
            "'limit_response_size' => self::MAX_RESPONSE",
            "data['chart']" if False else "$payload['chart']['result'][0]",
            "update_option('asc_last_quote_'",
            "wp_remote_retrieve_response_code",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)
        self.assertIn("ASC_Market_Quotes::register()", MAIN.read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
