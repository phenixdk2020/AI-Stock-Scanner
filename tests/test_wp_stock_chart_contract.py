"""Offline-kontrol af aktiesidens interaktive graf (ASC_Stock_Chart, assets/stock-chart.js, intradag-ruten og biblioteket)."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "wordpress" / "hangar18-ai-stock-scanner"
INC = PLUGIN / "includes"
CHART = INC / "class-asc-stock-chart.php"
PAGE = INC / "class-asc-stock-page.php"
QUOTES = INC / "class-asc-market-quotes.php"
PLAYBOOK = INC / "class-asc-playbook.php"
HELP = INC / "class-asc-help.php"
MAIN = PLUGIN / "hangar18-ai-stock-scanner.php"
SCRIPT = PLUGIN / "assets" / "stock-chart.js"
CSS = PLUGIN / "assets" / "dashboard.css"
VENDOR = PLUGIN / "assets" / "vendor" / "lightweight-charts"
LIBRARY = VENDOR / "lightweight-charts.standalone.production.js"
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"
TICKER_RE = "'/^[A-Z0-9^][A-Z0-9.^=-]{0,19}$/D'"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def method_body(source: str, signature: str) -> str:
    start = source.index(signature)
    following = re.search(r"\n    (?:public |private )?(?:static )?function ", source[start + len(signature):])
    end = start + len(signature) + following.start() if following else len(source)
    return source[start:end]


class VendorLibraryTests(unittest.TestCase):
    def test_library_is_bundled_and_pinned(self):
        self.assertTrue(LIBRARY.is_file())
        self.assertTrue((VENDOR / "LICENSE").is_file())
        self.assertIn("Apache License", read(VENDOR / "LICENSE"))
        readme = read(VENDOR / "README.md")
        version = re.search(r"Version: (\d+\.\d+\.\d+)", readme).group(1)
        self.assertTrue(version.startswith("5."), version)
        head = LIBRARY.read_bytes()[:400].decode("utf-8", "replace")
        self.assertIn("TradingView Lightweight Charts", head)
        self.assertIn("v" + version, head)
        self.assertIn("Apache License 2.0", head)
        self.assertIn("LIBRARY_VERSION = '" + version + "'", read(CHART))
        self.assertIn("Apache-2.0", readme)

    def test_only_the_standalone_production_build_is_shipped(self):
        names = sorted(p.name for p in VENDOR.iterdir())
        self.assertEqual(names, ["LICENSE", "README.md", "lightweight-charts.standalone.production.js"])
        self.assertLess(LIBRARY.stat().st_size, 400_000)


class EnqueueTests(unittest.TestCase):
    def test_scripts_are_local_and_only_enqueued_by_the_chart(self):
        chart = read(CHART)
        enqueue = method_body(chart, "private static function enqueue(): void")
        self.assertIn("assets/vendor/lightweight-charts/lightweight-charts.standalone.production.js", enqueue)
        self.assertIn("assets/stock-chart.js", enqueue)
        self.assertIn("['hangar18-asc-lwc']", enqueue)
        self.assertEqual(enqueue.count("plugins_url("), 2)
        self.assertNotIn("http", enqueue)
        # Aktiesiden tegner grafen; hovedfilen og andre sider indlæser hverken script eller bibliotek.
        for other in (MAIN, PAGE, QUOTES, PLAYBOOK):
            with self.subTest(other=other.name):
                self.assertNotIn("lightweight-charts", read(other))
                self.assertNotIn("stock-chart.js", read(other))
        self.assertIn("self::enqueue();", method_body(chart, "public static function render("))
        self.assertIn("ASC_Stock_Chart::render(", read(PAGE))
        self.assertIn("class-asc-stock-chart.php", read(MAIN))
        self.assertLess(read(MAIN).index("class-asc-stock-chart.php"), read(MAIN).index("class-asc-stock-page.php"))

    def test_no_external_loading_in_script_or_class(self):
        script = read(SCRIPT)
        self.assertNotIn("http://", script)
        self.assertNotIn("https://", script)
        self.assertNotRegex(script, r"importScripts|\bimport\s*\(|createElement\(['\"]script|XMLHttpRequest|\bsrc\s*=")
        self.assertEqual(script.count("fetch("), 1)
        self.assertIn("info.url", script)  # intradag-adressen kommer fra serveren (rest_url), ikke fra scriptet
        chart = read(CHART)
        urls = re.findall(r"https?://[^\s'\"<>]+", chart)
        self.assertEqual(urls, ["https://www.tradingview.com/"])
        self.assertNotRegex(chart, r"(?:src|href)=\"https?://(?!www\.tradingview\.com/)")
        self.assertNotIn("<script src", chart)
        css = read(CSS)
        self.assertNotRegex(css[css.index("Interaktiv aktiegraf"):], r"url\(|@import")


class AttributionTests(unittest.TestCase):
    def test_tradingview_attribution_is_kept(self):
        self.assertIn("attributionLogo: true", read(SCRIPT))
        chart = read(CHART)
        self.assertIn('href="https://www.tradingview.com/"', chart)
        self.assertIn('rel="noopener noreferrer"', chart)
        self.assertIn("TradingView Lightweight Charts", chart)


class DataSafetyTests(unittest.TestCase):
    def test_json_is_inert_and_escaped(self):
        chart = read(CHART)
        self.assertIn('<script type="application/json" id="asc-chart-data">', chart)
        self.assertIn("wp_json_encode($payload, JSON_HEX_TAG | JSON_HEX_AMP)", chart)
        self.assertEqual(chart.count("'<script"), 1)
        self.assertIn("JSON.parse(", read(SCRIPT))
        self.assertNotRegex(read(SCRIPT), r"\beval\(|new Function\(")
        for expected in ("esc_html(", "esc_attr(", "esc_url_raw("):
            self.assertIn(expected, chart)
        self.assertIn("preg_match('/^\\d{4}-\\d\\d-\\d\\d$/D', $date)", chart)

    def test_script_writes_text_not_markup_except_the_server_fallback(self):
        script = read(SCRIPT)
        self.assertEqual(script.count("innerHTML"), 1)
        self.assertIn("inner.innerHTML = holder.textContent", script)

    def test_chart_is_read_only(self):
        chart = read(CHART)
        for forbidden in ("update_user_meta(", "update_option(", "set_transient(", "wp_remote_", "add_action("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, chart)


class IntradayRouteTests(unittest.TestCase):
    def test_route_requires_login_and_is_get(self):
        quotes = read(QUOTES)
        routes = method_body(quotes, "public static function register_routes(): void")
        block = routes[routes.index("'/quotes/intraday'"):]
        self.assertIn("'methods'             => 'GET'", block)
        self.assertIn("[self::class, 'rest_intraday']", block)
        self.assertIn("'permission_callback' => static fn() => is_user_logged_in()", block)
        self.assertIn("'enum' => ['1d', '5d']", block)
        self.assertIn("'required' => true", block)
        # Den eksisterende refresh-rute er uændret (POST, login).
        refresh = routes[:routes.index("'/quotes/intraday'")]
        self.assertIn("'methods'             => 'POST'", refresh)

    def test_ticker_and_range_are_validated(self):
        quotes = read(QUOTES)
        for name in ("public static function rest_intraday(", "public static function intraday("):
            with self.subTest(name=name):
                self.assertIn(TICKER_RE, method_body(quotes, name))
        rest = method_body(quotes, "public static function rest_intraday(")
        self.assertIn("'status' => 400", rest)
        self.assertIn("'status' => 503", rest)
        self.assertIn("private, no-store", rest)
        self.assertIn("INTRADAY_RANGES = ['1d' => '5m', '5d' => '15m']", quotes)
        self.assertIn("isset(self::INTRADAY_RANGES[$range])", method_body(quotes, "public static function intraday("))

    def test_intraday_fetch_is_cached_throttled_and_validated_like_history(self):
        quotes = read(QUOTES)
        body = method_body(quotes, "public static function intraday(")
        self.assertIn("private const INTRADAY_AGE = 600;", quotes)
        for expected in ("get_transient($key)", "set_transient($key, $data, self::INTRADAY_AGE)",
                         "get_transient($cooldown) !== false", "set_transient($cooldown, 1, self::INTRADAY_RETRY_AFTER)",
                         "'interval=' . self::INTRADAY_RANGES[$range]".replace("'interval=' . ", "'&interval=' . "),
                         "'redirection' => 0", "'limit_response_size' => self::INTRADAY_MAX_RESPONSE",
                         "wp_safe_remote_get($url", "self::enabled()", "!preg_match('/^[A-Z]{3}$/D', $currency)",
                         "(int)$market_time < 1577836800", "(float)$price <= 0", "count($bars) < 2",
                         "self::parse_history($result, self::INTRADAY_MAX_BARS, self::INTRADAY_MAX_BARS)"):
            with self.subTest(expected=expected):
                self.assertIn(expected, body)
        self.assertNotIn("update_option(", body)

    def test_existing_quote_contract_is_untouched(self):
        quotes = read(QUOTES)
        self.assertIn("private const MAX_FETCH_PER_PAGE = 1;", quotes)
        self.assertEqual(quotes.count("'timeout' => 3,"), 1)
        get = method_body(quotes, "public static function get(string $ticker): ?array")
        self.assertIn("'timeout' => 3,", get)
        self.assertIn("self::$fetches_this_page >= self::MAX_FETCH_PER_PAGE", get)
        self.assertNotIn("intraday", get)

    def test_script_calls_the_route_with_cookie_and_nonce(self):
        script = read(SCRIPT)
        for expected in ("credentials: 'same-origin'", "'X-WP-Nonce'", "'&range=' + key", "encodeURIComponent(cfg.ticker)"):
            with self.subTest(expected=expected):
                self.assertIn(expected, script)
        chart = read(CHART)
        self.assertIn("rest_url('ai-stock-scanner/v1/quotes/intraday')", chart)
        self.assertIn("wp_create_nonce('wp_rest')", chart)


class ChartBehaviourContractTests(unittest.TestCase):
    def test_periods_defaults_and_options(self):
        script = read(SCRIPT)
        for label in ("'1 D'", "'1 U'", "'1 M'", "'3 M'", "'6 M'", "'ÅTD'", "'1 Å'", "'5 Å'"):
            with self.subTest(label=label):
                self.assertIn(label, script)
        for expected in ("DEFAULT_PERIOD = '6m'", "locale: 'da-DK'", "autoSize: true", "vertTouchDrag: false",
                         "LW.AreaSeries", "LW.CandlestickSeries", "LW.HistogramSeries", "LW.LineSeries",
                         "createSeriesMarkers", "subscribeCrosshairMove", "sessionStorage.getItem", "sessionStorage.setItem",
                         "sim_sell: 'S'", "buy: 'K'", "sim_buy: 'V'", "Intradagskurser kan ikke hentes", "'Vis 1 M'",
                         "Der vises ingen gættede kurser"):
            with self.subTest(expected=expected):
                self.assertIn(expected, script)
        # sessionStorage bruges kun i try/catch.
        for match in re.finditer(r"sessionStorage\.(?:get|set)Item", script):
            before = script[max(0, match.start() - 160):match.start()]
            self.assertIn("try {", before)
        # Ingen SMA på intradag.
        self.assertIn("setSeries(bars, false)", script)
        self.assertIn("clearMarkers();", script)

    def test_fallback_keeps_the_svg_chart(self):
        page, chart, script = read(PAGE), read(CHART), read(SCRIPT)
        self.assertIn("ASC_Market_Quotes::stock_chart($ticker, $bars, $currency, $period, $markers)", page)
        self.assertIn('<noscript data-asc-chart-fallback>', chart)
        self.assertIn("useFallback();", script)
        self.assertIn("noscript[data-asc-chart-fallback]", script)
        self.assertIn("!LW || typeof LW.createChart !== 'function'", script)
        self.assertNotIn("console.", script)
        self.assertIn("public static function stock_chart(", read(QUOTES))

    def test_key_figures_and_help(self):
        chart, help_text = read(CHART), read(HELP)
        for label in ("Åbning", "Høj", "Lav", "Volumen", "52 ugers høj", "52 ugers lav", "P/E", "Markedsværdi"):
            with self.subTest(label=label):
                self.assertIn("'" + label + "'", chart)
                self.assertIn(label.replace(" lav", ""), help_text)
        self.assertIn("'–'", chart)
        self.assertIn("ASC_Playbook::key_figures($ticker)", read(PAGE))
        figures = method_body(read(PLAYBOOK), "public static function key_figures(")
        self.assertIn("mcap_usd_bn", figures)
        self.assertIn("eps_today", figures)
        self.assertIn("Aktiesidens graf og nøgletal", help_text)
        self.assertIn("Bear/Base/Bull", read(PAGE) + read(PLAYBOOK))  # uændret

    def test_php_braces_and_parens_balance(self):
        for path in (CHART, PAGE, QUOTES, PLAYBOOK, HELP):
            source = read(path)
            depth = {"{": 0, "(": 0, "[": 0}
            pairs = {"}": "{", ")": "(", "]": "["}
            i, n = 0, len(source)
            while i < n:
                c = source[i]
                if source.startswith("//", i) or c == "#":
                    while i < n and source[i] != "\n":
                        i += 1
                    continue
                if source.startswith("/*", i):
                    i = source.index("*/", i) + 2
                    continue
                if c in "'\"":
                    quote = c
                    i += 1
                    while i < n and source[i] != quote:
                        i += 2 if source[i] == "\\" else 1
                    i += 1
                    continue
                if c in depth:
                    depth[c] += 1
                elif c in pairs:
                    depth[pairs[c]] -= 1
                    self.assertGreaterEqual(depth[pairs[c]], 0, path.name)
                i += 1
            with self.subTest(path=path.name):
                self.assertEqual(depth, {"{": 0, "(": 0, "[": 0})

    def test_ci_checks_the_new_class(self):
        self.assertIn("includes/class-asc-stock-chart.php", read(WORKFLOW))
        self.assertIn("declare(strict_types=1);", read(CHART))
        self.assertIn("final class ASC_Stock_Chart", read(CHART))

    def test_plugin_version_is_0_8_2(self):
        main = read(MAIN)
        self.assertIn("* Version: 0.8.11", main)
        self.assertIn("define('ASC_PLUGIN_VERSION', '0.8.11')", main)
        self.assertIn("<strong>v0.8.11:</strong>", main)


if __name__ == "__main__":
    unittest.main()
