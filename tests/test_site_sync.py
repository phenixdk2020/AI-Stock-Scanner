"""Fase 1/2 integrationskontrakter; ingen internetadgang nødvendig."""
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from stockscanner.site_sync import build_snapshot, make_endpoint, send_snapshot


class SnapshotTests(unittest.TestCase):
    def test_demo_is_visibly_marked(self):
        result = build_snapshot(demo=True)
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["mode"], "demo")
        self.assertEqual(len(result["rows"]), 2)

    def test_latest_per_ticker(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "data.sqlite3"
            with sqlite3.connect(db) as c:
                c.execute("CREATE TABLE scans (id INTEGER PRIMARY KEY, "
                          "ticker TEXT, market_date TEXT, score INTEGER, "
                          "signal TEXT, scanned_at_utc TEXT)")
                c.executemany(
                    "INSERT INTO scans (ticker, market_date, score, signal, scanned_at_utc) "
                    "VALUES (?, ?, ?, ?, ?)",
                    [
                        ("MSFT", "2026-11-01", 80, "Interessant", "2026-11-01T07:00:00Z"),
                        ("MSFT", "2026-10-31", 20, "Afvent", "2026-10-31T07:00:00Z"),
                        ("NOVO-B.CO", "2026-11-01", 60, "Hold øje", "2026-11-01T07:00:00Z"),
                    ],
                )
            payload = build_snapshot(db)
            self.assertEqual(payload["mode"], "research")
            self.assertEqual(len(payload["rows"]), 2)
            by_ticker = {item["ticker"]: item for item in payload["rows"]}
            self.assertEqual(by_ticker["MSFT"]["score"], 80)
            self.assertEqual(by_ticker["NOVO-B.CO"]["market"], "Danmark")

    def test_https_required(self):
        self.assertEqual(make_endpoint("https://aktier.hangar18.dk"),
                         "https://aktier.hangar18.dk/wp-json/ai-stock-scanner/v1/snapshot")
        for site in ("http://aktier.hangar18.dk", "https://user:pass@example.com",
                     "https://example.com:8080", "https://example.com/?q=1"):
            with self.subTest(site=site), self.assertRaises(ValueError):
                make_endpoint(site)

    def test_client_does_not_follow_redirects(self):
        class Stub:
            status_code = 200
            def json(self):
                return {"ok": True, "count": 2}
        with patch("stockscanner.site_sync.requests.post", return_value=Stub()) as post:
            data = send_snapshot(build_snapshot(demo=True),
                                 "https://aktier.hangar18.dk", "agent", "a-secret")
            self.assertTrue(data["ok"])
            self.assertFalse(post.call_args.kwargs["allow_redirects"])
            self.assertEqual(post.call_args.kwargs["timeout"], (8, 25))

    def test_repo_wordpress_plugin_contract(self):
        root = Path(__file__).resolve().parent.parent
        plugin = root / "wordpress/hangar18-ai-stock-scanner/hangar18-ai-stock-scanner.php"
        code = plugin.read_text(encoding="utf-8")
        for text in ("current_user_can('asc_sync')",
                     "is_user_logged_in()", "register_rest_route",
                     "ASC_PLUGIN_VERSION", "esc_html(", "register_activation_hook"):
            self.assertIn(text, code)


if __name__ == "__main__":
    unittest.main()
