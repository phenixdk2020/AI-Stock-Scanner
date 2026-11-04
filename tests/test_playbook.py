"""Offline tests af playbook-snapshottet til hjemmesiden."""
import json
import unittest
from datetime import datetime, timezone
from unittest import mock

import numpy as np
import pandas as pd

from stockscanner import playbook, site_sync
from stockscanner.valuation import ValueChannel
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


def channel(**changes):
    base = dict(ticker="A", pe_base=15.0, pe_bear=10.0, pe_bull=20.0, eps_today=4.0, eps_horizon=5.0, price=60.0,
                scenario_prices={"bear": 50.0, "base": 75.0, "bull": 100.0},
                upside_pct={"bear": -16.7, "base": 25.0, "bull": 66.7}, cagr_pct={"bear": -8.7, "base": 11.8, "bull": 29.1},
                score=50.0, score_today=40.0, asymmetry=1.5, peg=1.2, implied_pe=None, notes=("Under 3 års P/E-historik",))
    base.update(changes)
    return ValueChannel(**base)


def payload_with(channels, rows=None, **extra):
    history = prices(np.linspace(50, 100, 300))
    rows = rows or [row("A"), row("B")]
    return playbook.build_payload(
        rows=rows, histories={r.ticker: history for r in rows}, currencies={"A": "USD", "B": "EUR"}, regions={},
        atrs={}, research=[], breadth={}, benchmark="RSP", factors=None, scores=None, regional=None,
        trades=pd.DataFrame(columns=["ticker", "koebsdato", "koebskurs", "salgsdato", "salgskurs", "salgsgrund"]),
        last_prices={}, changes=[], channels=channels, now=datetime(2026, 11, 2, 7, 0, tzinfo=timezone.utc), **extra)


class ScenarioTests(unittest.TestCase):
    def test_scenarios_in_payload_and_none_without_channel(self):
        payload = payload_with({"A": channel(), "B": None})
        scenarios = payload["stocks"]["A"]["scenarios"]
        self.assertEqual(scenarios["currency"], "USD")
        self.assertEqual(scenarios["horizon_years"], 2.0)
        self.assertEqual(scenarios["pe"], {"bear": 10.0, "base": 15.0, "bull": 20.0})
        self.assertEqual(scenarios["prices"]["base"], 75.0)
        self.assertEqual(scenarios["upside_pct"]["bull"], 66.7)
        self.assertEqual(scenarios["cagr_pct"]["bear"], -8.7)
        self.assertEqual((scenarios["eps_today"], scenarios["eps_horizon"]), (4.0, 5.0))
        self.assertEqual(scenarios["asymmetry"], 1.5)
        self.assertFalse(scenarios["asymmetry_inf"])
        self.assertEqual(scenarios["notes"], ["Under 3 års P/E-historik"])
        self.assertNotIn("scenarios", payload["stocks"]["B"])             # kanal er None
        self.assertNotIn("scenarios", payload_with(None)["stocks"]["A"])  # ingen kanaler overhovedet
        json.dumps(payload, allow_nan=False)

    def test_channel_without_scenario_prices_gets_no_field(self):
        empty = channel(scenario_prices={}, upside_pct={}, cagr_pct={}, asymmetry=None, score=None, score_today=None)
        self.assertNotIn("scenarios", payload_with({"A": empty})["stocks"]["A"])

    def test_channel_for_unknown_ticker_is_ignored(self):
        self.assertNotIn("Z", payload_with({"Z": channel()})["stocks"])

    def test_none_nan_and_inf_values_are_json_safe(self):
        nan, inf = float("nan"), float("inf")
        messy = channel(pe_bear=None, eps_today=nan, eps_horizon=inf, peg=nan, price=nan,
                        scenario_prices={"bear": nan, "base": 75.0, "bull": inf},
                        upside_pct={"bear": -inf, "base": None, "bull": nan}, cagr_pct={"base": nan}, notes=())
        payload = payload_with({"A": messy})
        json.dumps(payload, allow_nan=False)                              # ingen NaN/inf i JSON
        scenarios = payload["stocks"]["A"]["scenarios"]
        self.assertIsNone(scenarios["pe"]["bear"])
        self.assertIsNone(scenarios["eps_today"])
        self.assertIsNone(scenarios["eps_horizon"])
        self.assertIsNone(scenarios["prices"]["bear"])
        self.assertEqual(scenarios["prices"]["base"], 75.0)
        self.assertIsNone(scenarios["prices"]["bull"])
        self.assertIsNone(scenarios["upside_pct"]["bear"])
        self.assertIsNone(scenarios["cagr_pct"]["bull"])
        self.assertEqual(scenarios["notes"], [])

    def test_infinite_asymmetry_when_price_is_below_bear(self):
        below = channel(asymmetry=None, upside_pct={"bear": 5.0, "base": 40.0, "bull": 90.0})
        scenarios = payload_with({"A": below})["stocks"]["A"]["scenarios"]
        self.assertIsNone(scenarios["asymmetry"])
        self.assertTrue(scenarios["asymmetry_inf"])
        nan_asymmetry = channel(asymmetry=float("nan"))
        entry = playbook.scenarios_entry(nan_asymmetry, "USD", 2.0)
        self.assertIsNone(entry["asymmetry"])
        json.dumps(entry, allow_nan=False)

    def test_notes_are_limited(self):
        noisy = channel(notes=tuple("n" * 300 for _ in range(10)))
        notes = playbook.scenarios_entry(noisy, None, 2.0)["notes"]
        self.assertEqual(len(notes), playbook.MAX_SCENARIO_NOTES)
        self.assertTrue(all(len(n) == 160 for n in notes))

    def test_horizon_is_passed_on(self):
        self.assertEqual(playbook.scenarios_entry(channel(), "USD", 3.0)["horizon_years"], 3.0)


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
