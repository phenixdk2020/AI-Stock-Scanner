"""Offline-kontrakt for flere brugere og automatisk Bear/Base/Bull i pluginet (kildetekst; ingen PHP lokalt).

Adfærden køres i CI af tests/wp_playbook_visibility.php.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "wordpress" / "hangar18-ai-stock-scanner"
INC = PLUGIN / "includes"
PLAYBOOK = (INC / "class-asc-playbook.php").read_text(encoding="utf-8")
ANALYSIS = (INC / "class-asc-analysis.php").read_text(encoding="utf-8")
HELP = (INC / "class-asc-help.php").read_text(encoding="utf-8")
MAIN = (PLUGIN / "hangar18-ai-stock-scanner.php").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
DOCS = (ROOT / "docs" / "PLAYBOOK-SNAPSHOT.md").read_text(encoding="utf-8")


def method_body(source: str, signature: str) -> str:
    start = source.index(signature)
    following = re.search(r"\n    (?:public |private )?(?:static )?function ", source[start + len(signature):])
    return source[start:start + len(signature) + following.start()] if following else source[start:]


class MondayListIsPerUserTests(unittest.TestCase):
    def test_visible_tickers_helper_is_pure_and_used(self):
        helper = method_body(PLAYBOOK, "public static function visible_tickers(")
        self.assertNotIn("get_user_meta", helper)
        self.assertNotIn("followed_tickers", helper)
        for part in ("$data['research']", "$data['candidates']", "$watch", "$owned", "$simulated"):
            self.assertIn(part, helper)
        monday = method_body(PLAYBOOK, "private static function tab_monday(")
        self.assertIn("self::visible_tickers(", monday)
        self.assertIn("self::user_sim_tickers(", monday)
        self.assertNotIn("followed_tickers", monday)          # andre brugeres lister bruges aldrig til visningen

    def test_followed_tickers_is_only_for_scanner_and_quotes(self):
        users = [m.start() for m in re.finditer(r"followed_tickers\(", PLAYBOOK)]
        self.assertEqual(len(users), 2)                       # definitionen og rest_tickers
        self.assertNotIn("followed_tickers", ANALYSIS)
        self.assertNotIn("followed_tickers", (INC / "class-asc-stock-page.php").read_text(encoding="utf-8"))

    def test_owned_status_is_personal_everywhere_it_is_shown(self):
        helper = method_body(PLAYBOOK, "public static function personal_stock(")
        self.assertIn("'hold øje'", helper)
        self.assertIn("ikke i din portefølje", helper)
        self.assertIn("self::OWNED_ACTIONS", helper)
        self.assertIn("% siden køb", method_body(PLAYBOOK, "private static function is_owner_reason("))
        monday = method_body(PLAYBOOK, "private static function tab_monday(")
        self.assertIn("self::personal_stock($stock, $lots_by_ticker[$ticker] ?? [])", monday)
        panel = method_body(PLAYBOOK, "public static function analysis_panel(")
        self.assertIn("self::personal_stock(", panel)         # aktiesiden og simulatorens opslag går gennem panelet
        self.assertIn("self::user_lots(get_current_user_id())", panel)

    def test_changes_are_filtered_per_user(self):
        monday = method_body(PLAYBOOK, "private static function tab_monday(")
        self.assertIn("self::visible_changes(", monday)
        self.assertNotIn("foreach ($changes as $change) {\n                if (is_string($change))", monday)
        helper = method_body(PLAYBOOK, "public static function visible_changes(")
        self.assertIn("'PAPIR '", helper)
        self.assertIn("(ejet)", helper)
        self.assertIn("isset($visible[$match[1]])", helper)

    def test_texts_say_what_is_shared(self):
        self.assertIn("Scannerens egen papirportefølje, fælles for alle brugere", method_body(
            PLAYBOOK, "private static function tab_paper("))
        monday = method_body(PLAYBOOK, "private static function tab_monday(")
        self.assertIn("din simulator og den fælles research-liste", monday)
        self.assertIn("kun for aktier i din egen portefølje", monday)
        self.assertIn("Aktien er i din egen portefølje på hjemmesiden", HELP)
        self.assertNotIn("Du ejer aktien", HELP)


class SubscriberAccessTests(unittest.TestCase):
    def test_front_end_needs_login_only(self):
        quotes = (INC / "class-asc-market-quotes.php").read_text(encoding="utf-8")
        self.assertIn("'permission_callback' => static fn() => is_user_logged_in()", quotes)
        portfolio = (INC / "class-asc-portfolio.php").read_text(encoding="utf-8")
        self.assertEqual(portfolio.count("manage_options"), 2)  # kun create_home og linket til datakilder
        for name in ("watchlist", "simulator", "stock-page", "playbook", "analysis", "help"):
            source = (INC / f"class-asc-{name}.php").read_text(encoding="utf-8")
            with self.subTest(name=name):
                self.assertNotIn("manage_options", source)    # forsidens visninger kræver aldrig admin
                self.assertNotIn("admin_post_nopriv", source)

    def test_admin_views_stay_closed(self):
        for function, capability in (("asc_admin_page", "manage_options"), ("asc_admin_connection", "manage_options"),
                                     ("asc_admin_updates", "update_plugins")):
            body = MAIN[MAIN.index(f"function {function}("):]
            body = body[:body.index("\n}\n")]
            with self.subTest(function=function):
                self.assertIn(f"current_user_can('{capability}')", body)
        self.assertIn("add_menu_page(\n        'AI Stock Scanner', 'AI Stock Scanner', 'manage_options'", MAIN.replace("\r\n", "\n"))

    def test_private_pages_are_never_cached_and_flash_is_per_user(self):
        for code in ("ai_stock_playbook", "ai_stock_watchlist", "ai_stock_analysis", "ai_stock_help", "ai_stock_scanner"):
            self.assertIn(f"'{code}'", MAIN[MAIN.index("DONOTCACHEPAGE") - 600:MAIN.index("DONOTCACHEPAGE") + 200])
        self.assertIn("nocache_headers()", MAIN)
        for name in ("portfolio", "simulator"):
            source = (INC / f"class-asc-{name}.php").read_text(encoding="utf-8")
            self.assertIn("get_current_user_id()", method_body(source, "private static function flash_key("))


class ScenarioDisplayTests(unittest.TestCase):
    def test_clean_stock_validates_scenarios(self):
        self.assertIn("$out['scenarios'] = self::clean_scenarios($raw['scenarios'] ?? null);", PLAYBOOK)
        body = method_body(PLAYBOOK, "private static function clean_scenarios(")
        for part in ("'prices'", "'pe'", "'upside_pct'", "'cagr_pct'", "'eps_horizon'", "'eps_today'", "'horizon_years'",
                     "'asymmetry_inf'", "'notes'", "array_slice(", "self::clean_number(", "return null;"):
            self.assertIn(part, body)
        self.assertIn("160", body)

    def test_cards_in_analysis_panel_with_explanation(self):
        panel = method_body(PLAYBOOK, "public static function analysis_panel(")
        self.assertIn("self::scenarios_section($ticker)", panel)
        cards = method_body(PLAYBOOK, "public static function scenario_cards_html(")
        for text in ("Kurs nu", "Upside", "årligt", "× P/E", "ikke en prognose", "historiske P/E og analytikernes estimater",
                     "Kursen nu ligger"):
            self.assertIn(text, cards)
        self.assertIn("Ikke beregnet endnu. Følg aktien, så kommer den med ved næste kørsel.",
                      method_body(PLAYBOOK, "private static function scenarios_section("))
        for field in ("price", "prices", "pe", "upside_pct", "cagr_pct"):
            self.assertIn(f"'{field}'", cards)
        # alt udskrevet fra data escapes
        self.assertNotRegex(cards, r"\.\s*\$sc\[")

    def test_analysis_page_has_picker_and_prefills_calculator(self):
        self.assertIn("asc_analysis_ticker", ANALYSIS)
        self.assertIn("[A-Z0-9^][A-Z0-9.^=-]{0,19}$/D", ANALYSIS)
        self.assertIn("ASC_Playbook::scenario_tickers()", ANALYSIS)
        self.assertIn("ASC_Playbook::scenarios_for($picked)", ANALYSIS)
        self.assertIn("ASC_Playbook::scenario_cards_html($auto)", ANALYSIS)
        self.assertIn("Ikke beregnet endnu. Følg aktien, ", ANALYSIS)
        self.assertIn("self::seed($auto['eps_horizon']", ANALYSIS)
        self.assertIn("Manuel bull / base / bear-beregner", ANALYSIS)
        self.assertIn('<input type="hidden" name="asc_analysis_ticker"', ANALYSIS)
        self.assertNotIn("seks tekniske kriterier", ANALYSIS)
        self.assertNotIn("fundamental kvalitet", ANALYSIS)
        self.assertIn("scenario_tickers", method_body(PLAYBOOK, "public static function scenario_tickers("))

    def test_help_explains_bear_base_bull_and_snapshot_doc_is_updated(self):
        self.assertIn("Bear / Base / Bull", HELP)
        self.assertIn("ikke en prognose", HELP)
        self.assertIn("`scenarios`", DOCS)
        self.assertIn("tests/wp_playbook_visibility.php", WORKFLOW)

    def test_scenarios_are_not_table_columns(self):
        tables = (PLUGIN / "assets" / "tables.js").read_text(encoding="utf-8")
        self.assertNotIn("'bear'", tables)


if __name__ == "__main__":
    unittest.main()
