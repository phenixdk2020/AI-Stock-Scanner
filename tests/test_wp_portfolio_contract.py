"""Regression checks for the WordPress-only personal portfolio feature."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "wordpress" / "hangar18-ai-stock-scanner"
PORTFOLIO = PLUGIN / "includes" / "class-asc-portfolio.php"
QUOTES = PLUGIN / "includes" / "class-asc-market-quotes.php"
MAIN = PLUGIN / "hangar18-ai-stock-scanner.php"
WATCHLIST = PLUGIN / "includes" / "class-asc-watchlist.php"
FX = PLUGIN / "includes" / "class-asc-fx-rates.php"
ANALYSIS = PLUGIN / "includes" / "class-asc-analysis.php"


class PortfolioContractTests(unittest.TestCase):
    def test_per_user_storage_and_nonce_protected_actions(self):
        source = PORTFOLIO.read_text(encoding="utf-8")
        for expected in (
            "get_user_meta($user_id, self::USER_META, true)",
            "update_user_meta(get_current_user_id(), self::USER_META",
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


    def test_manual_quote_and_csv_export(self):
        source = PORTFOLIO.read_text(encoding="utf-8")
        for expected in (
            "asc_initial_price", "asc_portfolio_edit", "asc_portfolio_export",
            "check_admin_referer('asc_portfolio_export')",
            "check_admin_referer('asc_portfolio_edit')",
            "Content-Type: text/csv", "get_current_user_id()",
            "asc-demo-overview", "ASC_Watchlist::render()", "position_counts",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)

    def test_private_watchlist_and_secure_post_actions(self):
        source = WATCHLIST.read_text(encoding="utf-8")
        main = MAIN.read_text(encoding="utf-8")
        for expected in (
            "get_user_meta(get_current_user_id()",
            "update_user_meta(get_current_user_id()",
            "check_admin_referer('asc_watch_add')",
            "check_admin_referer('asc_watch_remove')",
            "is_user_logged_in()", "wp_safe_redirect(",
            "ASC_Market_Quotes::chart_markup", "MAX = 50",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)
        self.assertIn("ASC_Watchlist::register()", main)

    def test_historical_candles_and_volume_math(self):
        source = QUOTES.read_text(encoding="utf-8")
        for expected in (
            "range=6mo&interval=1d", "parse_history(",
            "shares_per_day", "value_per_day",
            "daily_stats($bars, 5)", "daily_stats($bars, 21)",
            "chart_markup(", "<svg", "close'] * (float)$bar['volume']",
            "sharesOutstanding",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)

    def test_one_time_status_messages_are_not_replayed(self):
        code = PORTFOLIO.read_text(encoding="utf-8")
        self.assertIn("set_transient(self::flash_key(), $status, 180)", code)
        self.assertIn("get_transient(self::flash_key())", code)
        self.assertIn("delete_transient(self::flash_key())", code)
        self.assertIn("remove_query_arg('asc_portfolio_status', $url)", code)
        self.assertIn("wp_safe_redirect($url . '#asc-portfolio')", code)
        self.assertNotIn("$_GET['asc_portfolio_status']", code)
        self.assertNotIn("add_query_arg('asc_portfolio_status', $status", code)

    def test_three_purchase_diagnostics_and_bounded_quote_requests(self):
        portfolio = PORTFOLIO.read_text(encoding="utf-8")
        quotes = QUOTES.read_text(encoding="utf-8")
        for expected in (
            "private const MAX_POSITIONS = 100",
            "asc-saved-count", "invalid_ticker", "invalid_currency",
            "invalid_quantity", "invalid_current_price", "save_failed",
            "self::positions($user_id)", "if ($written === false || !$stored)",
            "private_page_no_cache", "DONOTCACHEPAGE", "nocache_headers()",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, portfolio)
        self.assertIn("private const MAX_FETCH_PER_PAGE = 1", quotes)
        self.assertIn("'timeout' => 3", quotes)
        self.assertTrue((ROOT / "tests/wp_portfolio_three_purchases.php").exists())

    def test_share_count_is_integer_not_currency(self):
        code = PORTFOLIO.read_text(encoding="utf-8")
        self.assertIn("private static function integer_quantity(string $raw): ?int", code)
        self.assertEqual(code.count("self::integer_quantity(self::field('asc_quantity'))"), 2)
        self.assertNotIn("self::decimal(self::field('asc_quantity'))", code)
        self.assertIn("self::share_count($quantity) . ' stk.", code)
        self.assertIn("type=\"number\" name=\"asc_quantity\"", code)
        self.assertIn("type=\"number\" inputmode=\"numeric\"", code)
        self.assertIn("step=\"1\"", code)
        self.assertIn("self::redirect('invalid_quantity')", code)
        self.assertIn("self::redirect('invalid_buy_price')", code)
        self.assertIn("self::redirect('invalid_current_price')", code)

    def test_paid_dkk_field_converts_invested_value_and_profit(self):
        portfolio = PORTFOLIO.read_text(encoding="utf-8")
        fx = FX.read_text(encoding="utf-8")
        main = MAIN.read_text(encoding="utf-8")
        for needle in (
            "asc_paid_dkk", "invalid_paid_dkk", "calculate_dkk_values(",
            "Betalt i alt (DKK)", "Faktisk betalt beløb", "Effektiv kurs ved køb",
            "DKK afkast", "value_dkk", "invested_dkk", "profit_dkk",
            "used_purchase_fx_fallback", "estimated_invested_dkk",
            "Betalt i alt DKK", "asc-dkk-summary",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, portfolio)
        self.assertIn("ASC_FX_Rates::to_dkk($currency)", portfolio)
        self.assertIn("rate_from_snapshot(", fx)
        self.assertIn("eurofxref-daily.xml", fx)
        self.assertIn("class-asc-fx-rates.php", main)
        self.assertTrue((ROOT / "tests/wp_portfolio_dkk.php").exists())

    def test_sidebar_etf_analytics_and_market_filters(self):
        portfolio = PORTFOLIO.read_text(encoding="utf-8")
        main = MAIN.read_text(encoding="utf-8")
        analysis = ANALYSIS.read_text(encoding="utf-8")
        css = (PLUGIN / "assets/dashboard.css").read_text(encoding="utf-8")
        for value in ("asc-app-sidebar", "asc-app-mobile-menu", "asc_view", "overview",
                      "portfolio", "watchlist", "scanner", "analysis", "settings"):
            self.assertIn(value, portfolio)
        self.assertIn("asc_instrument_type", portfolio)
        self.assertIn("instrument_type", main)
        self.assertIn("asc_market", main)
        self.assertIn("asc_score_min", main)
        self.assertIn("asc_signal", main)
        self.assertIn("ASC_Analysis::register()", main)
        self.assertIn("ai_stock_analysis", analysis)
        self.assertIn("EPS", analysis)
        self.assertIn("asc-analysis-grid", css)

    def test_danish_catalog_search_and_safe_portfolio_prefill(self):
        code = PORTFOLIO.read_text(encoding="utf-8")
        main = MAIN.read_text(encoding="utf-8")
        catalog = (PLUGIN / "includes/class-asc-danish-catalog.php").read_text(encoding="utf-8")
        self.assertIn("'stocks' => ['Danske aktier'", code)
        self.assertIn("ASC_Danish_Catalog::render()", code)
        self.assertIn("esc_attr($suggested_ticker)", code)
        self.assertIn("esc_attr($suggested_name)", code)
        self.assertIn("ASC_Danish_Catalog::register()", main)
        for token in ("parse_csv(", "asc_query", "asc_sector", "asc_catalog_page",
                      "asc_watch_add", "asc_catalog_import", "asc_catalog_refresh",
                      "current_user_can('manage_options')", "check_admin_referer(",
                      "MAX_BYTES = 100000", "danish-stocks-snapshot.csv"):
            self.assertIn(token, catalog)
        self.assertTrue((PLUGIN / "assets/danish-stocks-snapshot.csv").exists())

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
