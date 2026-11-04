"""Offline-kontrol af WordPress-simulatoren (virtuel handel pr. bruger)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "wordpress" / "hangar18-ai-stock-scanner"
SIM = PLUGIN / "includes" / "class-asc-simulator.php"
PLAYBOOK = PLUGIN / "includes" / "class-asc-playbook.php"
PORTFOLIO = PLUGIN / "includes" / "class-asc-portfolio.php"
MAIN = PLUGIN / "hangar18-ai-stock-scanner.php"
CSS = PLUGIN / "assets" / "dashboard.css"
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"


class SimulatorContractTests(unittest.TestCase):
    def test_registered_shortcode_menu_and_ci(self):
        sim = SIM.read_text(encoding="utf-8")
        main = MAIN.read_text(encoding="utf-8")
        portfolio = PORTFOLIO.read_text(encoding="utf-8")
        self.assertIn("final class ASC_Simulator", sim)
        self.assertIn("add_shortcode('ai_stock_simulator'", sim)
        self.assertIn("class-asc-simulator.php", main)
        self.assertIn("ASC_Simulator::register()", main)
        self.assertIn("[ai_stock_simulator]", main)
        self.assertIn("'simulator' => ['Simulator'", portfolio)
        self.assertIn("$view === 'simulator'", portfolio)
        self.assertIn("ASC_Simulator::render()", portfolio)
        self.assertIn("class-asc-simulator.php", WORKFLOW.read_text(encoding="utf-8"))
        self.assertIn("declare(strict_types=1);", sim)

    def test_per_user_storage_and_defaults(self):
        sim = SIM.read_text(encoding="utf-8")
        for expected in (
            "'asc_simulator_v1'",
            "get_user_meta($user_id, self::META, true)",
            "update_user_meta($user_id, self::META",
            "START_CASH = 1000000.0",
            "ROUND_DAYS = 30",
            "TARGET_POSITIONS = 10",
            "MAX_POSITIONS = 20",
            "FEE_RATE = 0.001",
            "benchmark_start", "start_cash_dkk", "cash_dkk", "fx_to_dkk",
            "pnl_dkk", "buy_fx", "sell_fx", "'history'",
            "rsp_return_pct", "return_pct",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, sim)

    def test_actions_are_nonce_and_login_protected(self):
        sim = SIM.read_text(encoding="utf-8")
        for action in ("asc_sim_start", "asc_sim_buy", "asc_sim_sell", "asc_sim_end"):
            with self.subTest(action=action):
                self.assertIn("add_action('admin_post_" + action + "'", sim)
                self.assertIn("guard('" + action + "')", sim)
                self.assertIn("wp_nonce_field('" + action + "'", sim)
        self.assertIn("check_admin_referer($nonce_action)", sim)
        self.assertIn("is_user_logged_in()", sim)
        self.assertIn("auth_redirect()", sim)
        self.assertIn("wp_safe_redirect(", sim)
        self.assertIn("wp_validate_redirect(", sim)
        self.assertIn("wp_generate_uuid4()", sim)
        self.assertIn("DONOTCACHEPAGE", sim)

    def test_prices_come_from_server_never_from_the_form(self):
        sim = SIM.read_text(encoding="utf-8")
        self.assertIn("ASC_Market_Quotes::get($ticker)", sim)
        self.assertIn("ASC_FX_Rates::to_dkk($currency)", sim)
        self.assertIn("self::price_for($ticker)", sim)
        for forbidden in ("asc_sim_price", "asc_price", "asc_sim_quote", "asc_buy_price"):
            self.assertNotIn(forbidden, sim)
        # kun disse felter læses fra formularer
        for key in ("asc_sim_cash", "asc_sim_ticker", "asc_sim_amount", "asc_sim_position_id"):
            self.assertIn("'" + key + "'", sim)

    def test_buy_rules(self):
        sim = SIM.read_text(encoding="utf-8")
        for expected in (
            "floor((float)$amount / $unit_dkk)",
            "$quote['price'] * (float)$fx",
            "$cost * self::FEE_RATE",
            "redirect('no_quote'", "redirect('no_fx'", "redirect('no_cash'",
            "redirect('qty_zero'", "redirect('max_positions'", "redirect('already_held'",
            "redirect('invalid_ticker')", "redirect('round_over')",
            "preg_match(self::TICKER_RE, $ticker) !== 1",
            "[A-Z0-9^][A-Z0-9.^=-]{0,19}",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, sim)

    def test_sell_closes_position_with_fees(self):
        sim = SIM.read_text(encoding="utf-8")
        for expected in (
            "$round['closed'][] = [", "unset($round['positions'][$index])",
            "$sell_fee = $proceeds * self::FEE_RATE",
            "$pnl = ($proceeds - $sell_fee) - ($quantity * $buy_price * $buy_fx + $buy_fee)",
            "redirect('notfound')",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, sim)

    def test_round_end_and_history(self):
        sim = SIM.read_text(encoding="utf-8")
        for expected in (
            "Runden er slut", "Afslut og start ny runde",
            "elapsed_days((string)$round['started']) < self::ROUND_DAYS",
            "array_unshift($state['history']",
            "$state['round'] = null",
            "Tidligere runder", "Lukkede handler", "Mine positioner",
            "Dag", "Forskel mod RSP", "RSP siden start",
            "private const BENCHMARK = 'RSP'",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, sim)

    def test_notices_footer_and_quote_handling(self):
        sim = SIM.read_text(encoding="utf-8")
        for expected in (
            "Virtuelle handler med forsinkede kurser. Ikke investeringsrådgivning.",
            "ASC_Market_Quotes::enabled()",
            "Yahoo-kurser skal aktiveres af administratoren",
            "ASC_Market_Quotes::auto_refresh_markup()",
            "gammel kurs", "kurs mangler",
            "ASC_Playbook::analysis_panel($ticker)",
            "Kurserne er forsinkede",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, sim)

    def test_playbook_helpers_and_links(self):
        playbook = PLAYBOOK.read_text(encoding="utf-8")
        for expected in (
            "public static function analysis_panel(string $ticker): string",
            "Ikke analyseret endnu – kommer med ved næste kørsel",
            "universe_index($data)", "news_summary", "eps_trend", "asymmetry_inf",
            "Køb i simulator", "ASC_Simulator::lookup_url($ticker)",
            "self::simulator_link((string)$ticker)",
            "$action === 'KØB-KANDIDAT'",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, playbook)
        self.assertIn("public static function lookup_url(string $ticker): string", SIM.read_text(encoding="utf-8"))

    def test_followed_tickers_include_simulator_positions_and_rsp(self):
        playbook = PLAYBOOK.read_text(encoding="utf-8")
        for expected in (
            "SIM_META = 'asc_simulator_v1'",
            "BENCHMARK_TICKER = 'RSP'",
            "meta_key IN (%s, %s, %s)",
            "self::SIM_META",
            "$value['round']['positions']",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, playbook)
        self.assertEqual(playbook.count("self::BENCHMARK_TICKER"), 1)
        # kun symboler fra positionerne må forlade WordPress – ingen beløb eller datoer
        body = playbook.split("public static function followed_tickers")[1].split("private static function cut")[0]
        for forbidden in ("cash_dkk", "quantity", "buy_price", "buy_date"):
            self.assertNotIn(forbidden, body)

    def test_layout_avoids_horizontal_overflow(self):
        css = CSS.read_text(encoding="utf-8")
        for expected in (".asc-sim-metrics", ".asc-simulator .asc-table-wrap table{white-space:normal",
                         "overflow-wrap:anywhere", ".asc-sim-facts", ".asc-sim-analysis"):
            with self.subTest(expected=expected):
                self.assertIn(expected, css)

    def test_php_braces_and_parens_balance(self):
        for path in (SIM, PLAYBOOK, PORTFOLIO):
            source = path.read_text(encoding="utf-8")
            # Ignorér tekststrenge og kommentarer groft, så kun kodens tegn tælles.
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
