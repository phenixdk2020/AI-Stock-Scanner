"""Offline-kontrol af den samlede aktieside (ASC_Stock_Page), aktielinks i alle tabeller og den lange historik."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "wordpress" / "hangar18-ai-stock-scanner"
INC = PLUGIN / "includes"
PAGE = INC / "class-asc-stock-page.php"
QUOTES = INC / "class-asc-market-quotes.php"
SIM = INC / "class-asc-simulator.php"
PLAYBOOK = INC / "class-asc-playbook.php"
PORTFOLIO = INC / "class-asc-portfolio.php"
WATCHLIST = INC / "class-asc-watchlist.php"
CATALOG = INC / "class-asc-danish-catalog.php"
MAIN = PLUGIN / "hangar18-ai-stock-scanner.php"
CSS = PLUGIN / "assets" / "dashboard.css"
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"
TICKER_RE = "/^[A-Z0-9^][A-Z0-9.^=-]{0,19}$/D"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def method_body(source: str, signature: str) -> str:
    """Teksten fra en metodes signatur til den næste metode på samme niveau."""
    start = source.index(signature)
    following = re.search(r"\n    (?:public |private )?(?:static )?function ", source[start + len(signature):])
    end = start + len(signature) + following.start() if following else len(source)
    return source[start:end]


class StockPageRegistrationTests(unittest.TestCase):
    def test_class_shortcode_menu_and_ci(self):
        page, main, portfolio = read(PAGE), read(MAIN), read(PORTFOLIO)
        self.assertIn("final class ASC_Stock_Page", page)
        self.assertIn("declare(strict_types=1);", page)
        self.assertIn("add_shortcode('ai_stock_page'", page)
        self.assertIn("class-asc-stock-page.php", main)
        self.assertIn("ASC_Stock_Page::register()", main)
        self.assertIn("[ai_stock_page]", main)
        self.assertIn("'stock' => ['Aktie'", portfolio)
        self.assertIn("$view === 'stock'", portfolio)
        self.assertIn("ASC_Stock_Page::render()", portfolio)
        workflow = read(WORKFLOW)
        self.assertIn("class-asc-stock-page.php", workflow)
        self.assertIn("tests/wp_stock_chart.php", workflow)
        self.assertTrue((ROOT / "tests" / "wp_stock_chart.php").is_file())

    def test_login_required_and_never_cached(self):
        page = read(PAGE)
        render = method_body(page, "public static function render(): string")
        self.assertLess(render.index("is_user_logged_in()"), render.index("wp_enqueue_style"))
        self.assertIn("Log ind for at se aktiesiden", render)
        for expected in ("add_action('template_redirect', [self::class, 'private_page_no_cache'], 0)",
                         "has_shortcode($content, 'ai_stock_page')", "DONOTCACHEPAGE", "nocache_headers()"):
            with self.subTest(expected=expected):
                self.assertIn(expected, page)

    def test_menu_view_and_url_use_the_same_parameters_as_the_simulator(self):
        page = read(PAGE)
        self.assertIn("'asc_view' => 'stock', 'asc_ticker' => $ticker", page)
        self.assertIn("public static function url(string $ticker): string", page)
        self.assertIn("public static function link(string $ticker, ?string $text = null): string", page)
        # url() bygges som ASC_Simulator::lookup_url: permalink, startside uden asc_view, add_query_arg.
        base = method_body(page, "private static function base_url(): string")
        self.assertIn("get_permalink(get_queried_object_id())", base)
        self.assertIn("asc_home_page_id", base)
        self.assertIn("!isset($_GET['asc_view'])", base)
        self.assertIn("get_post_type($home_id) === 'page'", base)
        self.assertIn("home_url('/')", base)


class StockPageSafetyTests(unittest.TestCase):
    def test_ticker_validation_uses_the_shared_regex_everywhere(self):
        page = read(PAGE)
        self.assertIn("TICKER_RE = '" + TICKER_RE + "'", page)
        self.assertIn("TICKER_RE = '" + TICKER_RE + "'", read(SIM))
        self.assertIn("TICKER_RE = '" + TICKER_RE + "'", read(PLAYBOOK))
        # Linket, søgningen og selve siden afviser ugyldige symboler.
        self.assertGreaterEqual(page.count("preg_match(self::TICKER_RE"), 3)
        self.assertIn("Aktiesymbolet er ugyldigt", page)
        self.assertIn("Ingen aktie fundet", page)
        self.assertIn("'/^[A-Z0-9^][A-Z0-9.^=-]{0,19}$/D'", method_body(read(QUOTES), "public static function history("))

    def test_inputs_are_sanitized_and_output_is_escaped(self):
        page = read(PAGE)
        self.assertIn("sanitize_text_field(wp_unslash($_GET[$key]))", page)
        reads = [m.start() for m in re.finditer(r"\$_GET\[", page)]
        allowed = page.index("sanitize_text_field(wp_unslash($_GET[$key]))")
        for position in reads:
            line = page[page.rfind("\n", 0, position):page.find("\n", position)]
            with self.subTest(line=line.strip()):
                self.assertTrue("wp_unslash($_GET[$key])" in line or "isset($_GET[" in line, line)
        self.assertGreater(allowed, 0)
        self.assertNotRegex(page, r"href=\"' \. \$")
        self.assertNotRegex(page, r"value=\"' \. \$")
        self.assertNotRegex(page, r"echo \$_(GET|POST|REQUEST)")
        for escaper in ("esc_html(", "esc_attr(", "esc_url("):
            with self.subTest(escaper=escaper):
                self.assertIn(escaper, page)
        self.assertNotIn("<script", page)
        self.assertNotIn("innerHTML", page)

    def test_page_is_read_only_and_reuses_existing_actions(self):
        page = read(PAGE)
        for forbidden in ("update_user_meta(", "update_option(", "add_action('admin_post", "set_transient(", "wp_remote_"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, page)
        for expected in ("asc_watch_add", "asc_watch_remove", "wp_nonce_field(",
                         "ASC_Simulator::lookup_url($ticker)", "'asc_view' => 'portfolio'",
                         "#asc-add-position", "ASC_Watchlist::is_followed($ticker)"):
            with self.subTest(expected=expected):
                self.assertIn(expected, page)
        self.assertIn("asc_currency", read(PORTFOLIO))
        self.assertIn('id="asc-add-position"', read(PORTFOLIO))

    def test_texts_and_search(self):
        page = read(PAGE)
        for expected in ("Forsinkede kurser. Ikke investeringsrådgivning.", "Følg", "Køb i simulator", "Registrér køb",
                         "asc_stock_q", "ASC_Danish_Catalog::search(", "ASC_Playbook::known_tickers()",
                         "Flere aktier passer", "kurstidspunkt", "siden forrige lukkekurs",
                         "ASC_Playbook::size_liquidity_html($ticker)", "ASC_Playbook::stock_page_analysis($ticker, $owned)",
                         "ASC_Market_Quotes::history($ticker)", "ASC_Market_Quotes::stock_chart(",
                         "kunne ikke hentes lige nu", "Der vises aldrig gættede kurser"):
            with self.subTest(expected=expected):
                self.assertIn(expected, page)
        playbook = read(PLAYBOOK)
        self.assertIn("Ikke analyseret endnu. Følg aktien, så kommer den med ved næste kørsel.", playbook)
        self.assertIn("public static function stock_page_analysis(string $ticker, array $owned = []): string", playbook)
        self.assertIn("self::analysis_panel($ticker)", method_body(playbook, "public static function stock_page_analysis"))
        self.assertIn("self::render_news([$ticker => $stock])", playbook)
        self.assertIn("public static function search(string $query, int $limit = 12): array", read(CATALOG))

    def test_markers_cover_portfolio_simulator_buys_and_simulator_sells(self):
        page = read(PAGE)
        for expected in ("'kind' => 'buy'", "'kind' => 'sim_buy'", "'kind' => 'sim_sell'",
                         "ASC_Portfolio::lots_for($user_id, $ticker)", "ASC_Simulator::trades_for($user_id, $ticker)",
                         "$trade['sell_date']"):
            with self.subTest(expected=expected):
                self.assertIn(expected, page)
        self.assertIn("public static function lots_for(int $user_id, string $ticker): array", read(PORTFOLIO))
        self.assertIn("public static function trades_for(int $user_id, string $ticker): array", read(SIM))


class LongHistoryContractTests(unittest.TestCase):
    def test_history_is_separate_and_bounded(self):
        quotes = read(QUOTES)
        history = method_body(quotes, "public static function history(string $ticker): ?array")
        for expected in ("if (!self::enabled()) { return null; }", "range=5y&interval=1d", "HISTORY_AGE",
                         "'timeout' => 6", "'limit_response_size' => self::HISTORY_MAX_RESPONSE",
                         "'redirection' => 0", "get_transient($cooldown) !== false", "set_transient($cooldown",
                         "wp_safe_remote_get(", "regularMarketPrice", "regularMarketTime",
                         "preg_match('/^[A-Z]{3}$/D', $currency)", "count($bars) < 20"):
            with self.subTest(expected=expected):
                self.assertIn(expected, history)
        self.assertLess(history.index("self::enabled()"), history.index("wp_safe_remote_get("))
        self.assertIn("HISTORY_AGE = 21600", quotes)
        self.assertIn("HISTORY_MAX_RESPONSE = 1572864", quotes)
        # Mislykket hentning giver null, aldrig en gættet pris eller kurs fra et andet sted.
        self.assertNotIn("last_known", history)
        self.assertNotIn("fetches_this_page", history)

    def test_existing_quote_contract_is_untouched(self):
        quotes = read(QUOTES)
        self.assertIn("private const MAX_FETCH_PER_PAGE = 1;", quotes)
        self.assertEqual(quotes.count("'timeout' => 3,"), 1)
        self.assertIn("public static function get(string $ticker): ?array", quotes)
        self.assertIn("rawurlencode($ticker) . '?range=6mo&interval=1d'", quotes)
        self.assertIn("private const MAX_RESPONSE = 262144;", quotes)
        self.assertIn("private static function parse_history(array $result, int $limit = 160, int $keep = 130): array", quotes)
        get = method_body(quotes, "public static function get(string $ticker): ?array")
        self.assertIn("$history = self::parse_history($result);", get)
        self.assertNotIn("history(", get.replace("parse_history(", ""))

    def test_sma_uses_all_fetched_history_before_the_period_is_cut(self):
        chart = method_body(read(QUOTES), "public static function stock_chart(")
        self.assertLess(chart.index("self::with_sma($bars)"), chart.index("$last_time - $days * 86400"))
        self.assertIn("'sma' . $n", read(QUOTES))
        self.assertIn("[50, 200]", read(QUOTES))
        self.assertIn("'5y' => null", read(QUOTES))
        self.assertIn("self::weekly($view)", chart)
        for period in ("'1m' => 31", "'6m' => 183", "'1y' => 366"):
            self.assertIn(period, read(QUOTES))
        self.assertIn("DEFAULT_PERIOD = '6m'", read(PAGE))
        self.assertIn("'asc_period' => $key", read(PAGE))


class ChartMarkupTests(unittest.TestCase):
    def test_server_rendered_svg_without_external_code(self):
        quotes = read(QUOTES)
        start = quotes.index("// ------------------------------------------------------------ Aktiesidens graf")
        end = quotes.index("private static function last_known")
        code = quotes[start:end]
        self.assertIn("<svg", code)
        self.assertIn("polyline", code)
        for forbidden in ("<script", "<image", "xlink:href", "foreignObject", "onclick", "onload", "<iframe",
                          "https://", "<link", "javascript:"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code)
        # Eneste adresse er SVG-navnerummet.
        self.assertEqual(len(re.findall(r"http://", code)), 1)
        self.assertIn("http://www.w3.org/2000/svg", code)
        self.assertIn("esc_html(", code)
        self.assertIn("esc_attr(", code)
        self.assertIn("viewBox", code)

    def test_legend_markers_and_mobile_layout(self):
        quotes, css = read(QUOTES), read(CSS)
        for expected in ("asc-chart-legend", "SMA50 (50 dages gennemsnit)", "SMA200 (200 dages gennemsnit)",
                         "'Køb (portefølje)'", "'Køb (simulator)'", "'Salg (simulator)'", "for lidt historik",
                         "Datoer uden for perioden springes over", "$date < $first || $date > $last_end"):
            with self.subTest(expected=expected):
                self.assertIn(expected, quotes)
        for expected in ("a.asc-stock-link", ".asc-stock-chart-scroll", "overflow-x:auto", ".asc-chart-legend",
                         ".asc-leg-sma50", ".asc-leg-sma200", "a.asc-stock-btn", "@media(max-width:600px)"):
            with self.subTest(expected=expected):
                self.assertIn(expected, css)

    def test_existing_chart_markup_is_unchanged_for_portfolio_and_watchlist(self):
        quotes = read(QUOTES)
        chart = method_body(quotes, "public static function chart_markup(string $ticker, array $quote): string")
        for expected in ("array_slice($bars, -55)", "viewBox=\"0 0 ' . $width . ' ' . $height . '\"", "$width = 960; $height = 345;",
                         "Volumenadvarsel"):
            with self.subTest(expected=expected):
                self.assertIn(expected, chart)
        self.assertIn("ASC_Market_Quotes::chart_markup($ticker, $quote)", read(PORTFOLIO))
        self.assertIn("ASC_Market_Quotes::chart_markup($ticker, $quote)", read(WATCHLIST))


class StockLinksInTablesTests(unittest.TestCase):
    def test_symbol_is_a_link_in_every_table_and_keeps_first_text(self):
        expectations = {
            PLAYBOOK: (4, ("<tr><th scope=\"row\">' . ASC_Stock_Page::link((string)$ticker)",
                           "ASC_Stock_Page::link((string)($trade['ticker'] ?? ''))")),
            SIM: (2, ("ASC_Stock_Page::link((string)$row['ticker'])",
                      "ASC_Stock_Page::link((string)($trade['ticker'] ?? ''))")),
            PORTFOLIO: (2, ("<th scope=\"row\">' . ASC_Stock_Page::link($ticker, (string)($p['label'] ?: $ticker))",)),
            WATCHLIST: (1, ("<th scope=\"row\">' . ASC_Stock_Page::link((string)$ticker)",)),
            CATALOG: (1, ("<strong>' . ASC_Stock_Page::link((string)$r['ticker'])",)),
            MAIN: (1, ("<th scope=\"row\">' . ASC_Stock_Page::link((string)$row['ticker'])",)),
        }
        for path, (count, snippets) in expectations.items():
            source = read(path)
            with self.subTest(file=path.name):
                self.assertGreaterEqual(source.count("ASC_Stock_Page::link("), count)
                for snippet in snippets:
                    self.assertIn(snippet, source)

    def test_no_plain_symbol_cells_remain(self):
        playbook = read(PLAYBOOK)
        self.assertNotIn("<th scope=\"row\">' . esc_html((string)$ticker)", playbook)
        self.assertNotIn("<th scope=\"row\">' . esc_html((string)($trade['ticker']", playbook)
        self.assertNotIn("<th scope=\"row\">' . esc_html($row['ticker'])", read(SIM))
        self.assertNotIn("<th scope=\"row\">' . esc_html($ticker) . '</th>'", read(WATCHLIST))
        self.assertNotIn("<th scope=\"row\">' . esc_html($row['ticker'])", read(MAIN))

    def test_tables_script_still_reads_first_cell_text(self):
        script = read(PLUGIN / "assets" / "tables.js")
        # Linket er cellens første indhold, så textContent af første node stadig er symbolet.
        self.assertIn("cell.childNodes[i].textContent.trim()", script)


class VersionTests(unittest.TestCase):
    def test_plugin_version_is_0_8_0(self):
        main = read(MAIN)
        self.assertIn("* Version: 0.8.1", main)
        self.assertIn("define('ASC_PLUGIN_VERSION', '0.8.1')", main)
        self.assertIn("<strong>v0.8.0:</strong>", main)

    def test_php_braces_and_parens_balance(self):
        for path in (PAGE, QUOTES, MAIN, PORTFOLIO, WATCHLIST, CATALOG):
            source = read(path)
            code = []
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
                code.append(c)
                i += 1
            code = "".join(code)
            for open_c, close_c in ("{}", "()", "[]"):
                with self.subTest(file=path.name, pair=open_c + close_c):
                    self.assertEqual(code.count(open_c), code.count(close_c))


if __name__ == "__main__":
    unittest.main()
