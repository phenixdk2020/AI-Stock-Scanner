"""Offline-kontrol af WordPress-administrationsmenuen i AI Stock Scanner."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN = ROOT / "wordpress/hangar18-ai-stock-scanner/hangar18-ai-stock-scanner.php"
UPDATER = ROOT / "wordpress/hangar18-ai-stock-scanner/includes/class-asc-github-updater.php"


class AdminMenuTests(unittest.TestCase):
    def test_visible_menu_and_submenus(self):
        source = MAIN.read_text(encoding="utf-8")
        for required in (
            "add_menu_page(",
            "'dashicons-chart-area'",
            "'asc-dashboard'",
            "'asc-updates'",
            "'asc-connection'",
            "'asc_admin_updates'",
            "'asc_admin_connection'",
            "plugin_action_links_",
            "ASC_GitHub_Updater::render_panel()",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)
        self.assertNotIn("add_management_page(", source)
        self.assertNotIn("GitHub-opdatering bruger en læsebegrænset token", source)

    def test_update_redirect_points_to_new_menu(self):
        source = UPDATER.read_text(encoding="utf-8")
        self.assertIn("admin.php?page=asc-updates", source)
        self.assertNotIn("tools.php?page=hangar18-ai-stock-scanner", source)

    def test_plugin_version_consistent(self):
        source = MAIN.read_text(encoding="utf-8")
        self.assertIn("* Version: 0.4.0", source)
        self.assertIn("define('ASC_PLUGIN_VERSION', '0.4.0')", source)


if __name__ == "__main__":
    unittest.main()
