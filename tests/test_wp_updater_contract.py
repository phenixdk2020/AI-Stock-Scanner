"""Offline-kontraktkontrol for WordPress GitHub-updateren."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import unittest
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parent.parent
SLUG = "hangar18-ai-stock-scanner"
MAIN = ROOT / "wordpress" / SLUG / (SLUG + ".php")
UPDATER = ROOT / "wordpress" / SLUG / "includes" / "class-asc-github-updater.php"
MANIFEST = ROOT / "update.json"


class UpdaterContractTests(unittest.TestCase):
    def test_version_and_zip_checksum(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["slug"], SLUG)
        version = manifest["version"]
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        main = MAIN.read_text(encoding="utf-8")
        self.assertIn("* Version: " + version, main)
        self.assertIn("define('ASC_PLUGIN_VERSION', '" + version + "')", main)
        path = ROOT / manifest["package_path"]
        self.assertEqual(path.name, SLUG + "-v" + version + ".zip")
        self.assertTrue(path.is_file())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), manifest["sha256"])
        with ZipFile(path) as archive:
            self.assertIsNone(archive.testzip())
            names = archive.namelist()
            self.assertEqual(len(names), len(set(name.casefold() for name in names)))
            self.assertTrue(all(name.startswith(SLUG + "/") for name in names))
            self.assertIn(SLUG + "/" + SLUG + ".php", names)
            self.assertIn(SLUG + "/includes/class-asc-github-updater.php", names)
            self.assertIn(SLUG + "/assets/dashboard.css", names)
            self.assertIn(SLUG + "/includes/class-asc-https-proxy.php", names)
            self.assertIn(SLUG + "/includes/class-asc-portfolio.php", names)
            self.assertIn(SLUG + "/includes/class-asc-market-quotes.php", names)
            package_main = archive.read(SLUG + "/" + SLUG + ".php").decode("utf-8")
            package_updater = archive.read(
                SLUG + "/includes/class-asc-github-updater.php"
            ).decode("utf-8")
            self.assertEqual(package_main, main)
            self.assertEqual(package_updater, UPDATER.read_text(encoding="utf-8"))

    def test_secure_plugin_update_hooks(self):
        source = UPDATER.read_text(encoding="utf-8")
        for requirement in (
            "https://raw.githubusercontent.com/phenixdk2020/AI-Stock-Scanner/main/",
            "hash('sha256'", "hash_equals(", "PclZip",
            "upgrader_pre_download", "upgrader_pre_install",
            "upgrader_post_install", "activate_plugin(",
            "is_plugin_active_for_network", "update_plugins_github.com",
            "check_admin_referer(", "current_user_can('update_plugins')",
            "redirection' => 0", "autoupdate' => false",
            "PCLZIP_OPT_EXTRACT_AS_STRING",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, source)
        main = MAIN.read_text(encoding="utf-8")
        self.assertIn("ASC_GitHub_Updater::register()", main)
        self.assertIn("ASC_GitHub_Updater::render_panel()", main)
        self.assertNotIn("ASC_GITHUB_TOKEN", source)
        self.assertNotIn("github_pat_", json.dumps(json.loads(MANIFEST.read_text())))


if __name__ == "__main__":
    unittest.main()
