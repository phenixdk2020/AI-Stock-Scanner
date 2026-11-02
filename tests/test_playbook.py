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

    def test_routes(self):
        self.assertEqual(site_sync._api("https://aktier.hangar18.dk", "/playbook"),
                         "https://aktier.hangar18.dk/wp-json/ai-stock-scanner/v1/playbook")


if __name__ == "__main__":
    unittest.main()
