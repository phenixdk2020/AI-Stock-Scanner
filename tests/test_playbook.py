"""Offline tests af playbook-snapshottet til hjemmesiden."""
import json
import unittest
from datetime import datetime, timezone
from unittest import mock

import numpy as np
import pandas as pd

from stockscanner import playbook, site_sync
from stockscanner.weekly_list import WeeklyRow


def prices(values):
    index = pd.bdate_range(end="2026-10-30", periods=len(values))
    close = pd.Series(values, index=index, dtype=float)
    return pd.DataFrame({"Open": close, "High": close * 1.01, "Low": close * 0.99, "Close": close, "Volume": 1})


def row(ticker, action="hold øje", reasons="intet StockMap-køb", asymmetry=None):
    return WeeklyRow(ticker, action, "–", None, None, None, 80.0, 50.0, 60.0, float("nan"), None, reasons,
                     asymmetry=asymmetry)


class PlaybookTests(unittest.TestCase):
    def test_payload_is_strict_json(self):
        history = prices(np.linspace(50, 100, 300))
        payload = playbook.build_payload(
            rows=[row("A", asymmetry=float("inf")), row("B", "pil ned", "StockMap-salg denne uge (ikke ejet)")],
            histories={"A": history, "B": history}, currencies={"A": "USD"}, regions={"A": "USA"},
            atrs={"A": 1.5}, research=["A"], breadth={50: 61.234}, benchmark="RSP", factors=None, scores=None,
            regional=None, trades=pd.DataFrame(columns=["ticker", "koebsdato", "koebskurs", "salgsdato", "salgskurs",
                                                        "salgsgrund"]),
            last_prices={}, changes=["A: x"], now=datetime(2026, 11, 2, 7, 0, tzinfo=timezone.utc))
        text = json.dumps(payload, allow_nan=False)          # fejler ved NaN/inf
        self.assertEqual(payload["generated_at"], "2026-11-02T07:00:00Z")
        self.assertTrue(payload["stocks"]["A"]["asymmetry_inf"])
        self.assertIsNone(payload["stocks"]["A"]["channel_score"])
        self.assertTrue(payload["stocks"]["B"]["exit"]["stockmap_sell"])
        self.assertFalse(payload["stocks"]["A"]["exit"]["stockmap_sell"])
        self.assertEqual(payload["breadth"], {"50": 61.2})
        self.assertIn("schema_version", text)

    def test_size_and_liquidity_in_stock_and_universe(self):
        entry = playbook.stock_entry(row("A"), prices(np.linspace(50, 100, 60)), "USD", "USA", 1.0)
        self.assertIsNone(entry["size"])
        self.assertIsNone(entry["liquidity"])
        factors = pd.DataFrame({"region": ["USA", "Norden"], "x_mcap_usd": [300e9, 0.0],
                                "x_adv_usd": [50e6, float("nan")], "x_idle_days": [0, float("nan")]},
                               index=["BIG", "UNL"])
        scores = pd.DataFrame({"quality": [80, 50]}, index=factors.index)
        section = playbook.universe_section(factors, scores, None)
        named = {r[0]: dict(zip(section["columns"], r)) for r in section["rows"]}
        self.assertEqual((named["BIG"]["size"], named["BIG"]["liquidity"]), ("Mega", "Høj"))
        self.assertEqual((named["UNL"]["size"], named["UNL"]["liquidity"]), ("ukendt", "ukendt"))
        old = factors.drop(columns=["x_adv_usd", "x_idle_days"])      # gammel cache uden likviditetskolonner
        self.assertEqual(playbook.universe_section(old, scores, None)["rows"][0][-1], "ukendt")
        json.dumps(section, allow_nan=False)

    def test_exit_facts_finds_sma50_break(self):
        falling = prices(np.r_[np.linspace(50, 100, 250), np.linspace(100, 70, 50)])
        facts = playbook.exit_facts(falling, False)
        self.assertTrue(facts["sma50_breaks"])
        self.assertTrue(facts["supertrend_down"])


class SiteSyncTests(unittest.TestCase):
    def test_credentials_need_all_three(self):
        with mock.patch.dict("os.environ", {"ASC_WP_SITE_URL": "https://aktier.hangar18.dk", "ASC_WP_USER": "a",
                                            "ASC_WP_APP_PASSWORD": ""}):
            self.assertIsNone(site_sync.credentials())

    def test_retries_dropped_connections_then_gives_up(self):
        import requests
        calls = []

        def flaky(*args, **kwargs):
            calls.append(1)
            if len(calls) < 3:
                raise requests.ConnectionError("afbrudt")
            return "svar"

        with mock.patch.object(site_sync, "RETRY_WAITS", (0, 0, 0)):
            self.assertEqual(site_sync._retrying(flaky)(), "svar")
            self.assertEqual(len(calls), 3)
            dead = mock.Mock(side_effect=requests.Timeout("for langsom"))
            with self.assertRaises(requests.Timeout):
                site_sync._retrying(dead)()
            self.assertEqual(dead.call_count, 4)

    def test_routes(self):
        self.assertEqual(site_sync._api("https://aktier.hangar18.dk", "/playbook"),
                         "https://aktier.hangar18.dk/wp-json/ai-stock-scanner/v1/playbook")


if __name__ == "__main__":
    unittest.main()
