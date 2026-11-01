"""Fase 1/2 integrationskontrakter; ingen internetadgang nødvendig."""
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from stockscanner.site_sync import build_snapshot, make_endpoint, send_snapshot, check_auth


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

    def test_authorization_fallback_after_401(self):
        class NotLoggedIn:
            status_code = 401
            def json(self):
                return {"code": "rest_not_logged_in", "message": "Not logged in"}
        class Accepted:
            status_code = 200
            def json(self):
                return {"ok": True, "count": 2}
        with patch("stockscanner.site_sync.requests.post",
                   side_effect=[NotLoggedIn(), Accepted()]) as post:
            data = send_snapshot(build_snapshot(demo=True),
                                 "https://aktier.hangar18.dk", "agent", "abcd efgh")
        self.assertEqual(data["count"], 2)
        self.assertEqual(post.call_count, 2)
        first, second = post.call_args_list
        self.assertEqual(first.kwargs["auth"], ("agent", "abcd efgh"))
        self.assertNotIn("auth", second.kwargs)
        self.assertEqual(second.kwargs["headers"]["X-ASC-Authorization"],
                         "Basic YWdlbnQ6YWJjZCBlZmdo")
        self.assertFalse(second.kwargs["allow_redirects"])
        self.assertEqual(first.args[0], second.args[0])

    def test_check_auth_only_reads_endpoint(self):
        class NotLoggedIn:
            status_code = 401
            def json(self):
                return {"code": "rest_not_logged_in"}
        class Accepted:
            status_code = 200
            def json(self):
                return {"ok": True, "authenticated": True}
        with patch("stockscanner.site_sync.requests.get",
                   side_effect=[NotLoggedIn(), Accepted()]) as get:
            info = check_auth("https://aktier.hangar18.dk", "agent", "app password")
        self.assertTrue(info["authenticated"])
        self.assertEqual(get.call_count, 2)
        self.assertTrue(get.call_args.args[0].endswith("/auth-check"))
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

    def test_scoped_app_password_contract(self):
        root = Path(__file__).resolve().parent.parent
        plugin = root / "wordpress/hangar18-ai-stock-scanner/hangar18-ai-stock-scanner.php"
        source = plugin.read_text(encoding="utf-8")
        for expected in (
            "'x-asc-authorization'", "wp_authenticate_application_password(null,",
            "wp_is_application_passwords_available()", "user_can($user, 'asc_sync')",
            "is_ssl()", "'/auth-check'", "['status' => 403]",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)
        self.assertNotIn("wp_is_application_passwords_available', '__return_true'", source)

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
