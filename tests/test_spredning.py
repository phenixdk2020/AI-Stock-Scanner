"""Offline tests af sektor pr. aktie og papirporteføljens stilling mod RSP (feature/spredning)."""
import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from stockscanner import paper, playbook, universe
from stockscanner.sector_rs import SECTOR_DA, sector_da, sector_name
from stockscanner.weekly_list import WeeklyRow


def bench(values, end="2026-10-30"):
    index = pd.bdate_range(end=end, periods=len(values))
    return pd.DataFrame({"Close": pd.Series(values, index=index, dtype=float)})


def trades(*items):
    frame = pd.DataFrame(list(items))
    return frame.reindex(columns=paper.COLUMNS)


def row(ticker):
    return WeeklyRow(ticker, "hold øje", "–", None, None, None, 80.0, 50.0, 60.0, float("nan"), None, "x")


def prices(values):
    index = pd.bdate_range(end="2026-10-30", periods=len(values))
    close = pd.Series(values, index=index, dtype=float)
    return pd.DataFrame({"Open": close, "High": close * 1.01, "Low": close * 0.99, "Close": close, "Volume": 1})


class SectorTests(unittest.TestCase):
    def test_danish_names_and_fallbacks(self):
        self.assertEqual(sector_da("Technology"), "Teknologi")
        self.assertEqual(sector_da("Financial Services"), "Finans")
        self.assertEqual(sector_da("Healthcare"), "Sundhed")
        self.assertEqual(sector_da("Noget Nyt"), "Noget Nyt")          # ukendte vises uændret
        for missing in (None, "", "  ", float("nan")):
            self.assertEqual(sector_da(missing), "ukendt")
        self.assertEqual(len(set(SECTOR_DA.values())), len(SECTOR_DA))   # to sektorer får ikke samme navn

    def test_all_yahoo_sectors_are_translated(self):
        from stockscanner.sector_rs import US_SECTOR_ETF
        for name in US_SECTOR_ETF:
            self.assertIn(name, SECTOR_DA)

    def test_sector_prefers_universe_column_then_map(self):
        factors = pd.DataFrame({"x_sector": ["Technology", None, float("nan")]}, index=["A", "B", "C"])
        mapping = {"B": {"sector": "Energy"}, "C": {}, "D": {"sector": "Utilities"}}
        self.assertEqual(sector_name("A", factors, mapping), "Teknologi")
        self.assertEqual(sector_name("B", factors, mapping), "Energi")          # kolonnen tom: sector_map
        self.assertEqual(sector_name("C", factors, mapping), "ukendt")
        self.assertEqual(sector_name("D", factors, mapping), "Forsyning")       # ikke i universet
        self.assertEqual(sector_name("E", factors, mapping), "ukendt")
        self.assertEqual(sector_name("D", None, mapping), "Forsyning")
        no_column = pd.DataFrame({"region": ["USA"]}, index=["B"])               # gammel cache uden kolonnen
        self.assertEqual(sector_name("B", no_column, mapping), "Energi")
        self.assertEqual(sector_name("B", no_column, None), "ukendt")

    def test_info_extras_keeps_sector(self):
        self.assertEqual(universe.info_extras({"sector": "Technology"})["x_sector"], "Technology")
        self.assertNotIn("x_sector", universe.info_extras({"marketCap": 1e9, "currency": "USD"}))
        self.assertNotIn("x_sector", universe.info_extras({"sector": "  "}))

    def test_universe_section_has_sector_last(self):
        factors = pd.DataFrame({"region": ["USA", "USA", "Norden"], "x_sector": ["Technology", None, None]},
                               index=["A", "B", "C"])
        scores = pd.DataFrame({"quality": [80, 50, 40]}, index=factors.index)
        section = playbook.universe_section(factors, scores, None, {"B": {"sector": "Healthcare"}})
        self.assertEqual(section["columns"][-1], "sector")
        named = {r[0]: r[-1] for r in section["rows"]}
        self.assertEqual(named, {"A": "Teknologi", "B": "Sundhed", "C": "ukendt"})
        old = factors.drop(columns=["x_sector"])
        self.assertEqual(playbook.universe_section(old, scores, None)["rows"][0][-1], "ukendt")
        json.dumps(section, allow_nan=False)

    def test_payload_stocks_carry_sector(self):
        history = prices(np.linspace(50, 100, 120))
        factors = pd.DataFrame({"region": ["USA"], "x_sector": ["Technology"]}, index=["A"])
        payload = playbook.build_payload(
            rows=[row("A"), row("B")], histories={"A": history, "B": history}, currencies={}, regions={}, atrs={},
            research=[], breadth={}, benchmark="RSP", factors=factors, scores=pd.DataFrame({"quality": [1]}, index=["A"]),
            regional=pd.DataFrame({"quality": [1]}, index=["A"]), trades=trades(), last_prices={}, changes=[], sector_map={"B": {"sector": "Utilities"}},
            now=datetime(2026, 11, 2, 7, 0, tzinfo=timezone.utc))
        self.assertEqual(payload["stocks"]["A"]["sector"], "Teknologi")
        self.assertEqual(payload["stocks"]["B"]["sector"], "Forsyning")
        self.assertIsNone(payload["paper_score"])                      # additivt felt, tomt uden beregning
        json.dumps(payload, allow_nan=False)


class PaperScoreTests(unittest.TestCase):
    def setUp(self):
        # RSP stiger 1 pr. børsdag fra 100 (2026-10-30 = 120 hvis 21 værdier)
        self.rsp = bench(np.arange(100, 121))
        self.days = list(self.rsp.index)

    def day(self, n):
        return str(self.days[n].date())

    def test_no_trades(self):
        result = paper.score(trades(), {}, self.rsp, date(2026, 10, 30))
        self.assertEqual(result["antal"], 0)
        self.assertEqual(result["sammenlignet"], 0)
        for key in ("afkast_pct", "rsp_pct", "forskel_pp", "vinderandel_pct", "start", "dage"):
            self.assertIsNone(result[key])
        self.assertTrue(result["for_tidligt"])
        json.dumps(result, allow_nan=False)

    def test_open_and_closed_trade(self):
        frame = trades(
            {"ticker": "A", "koebsdato": self.day(0), "koebskurs": 100.0, "salgsdato": self.day(10), "salgskurs": 120.0},
            {"ticker": "B", "koebsdato": self.day(10), "koebskurs": 50.0})
        result = paper.score(frame, {"B": 45.0}, self.rsp, date(2026, 10, 30))
        self.assertEqual((result["antal"], result["sammenlignet"], result["udeladt"]), (2, 2, 0))
        # A: +20 % mod RSP 100 -> 110 (+10 %); B: -10 % mod RSP 110 -> 120 (+9,09 %), seneste kursdato
        self.assertAlmostEqual(result["afkast_pct"], (20.0 - 10.0) / 2)
        self.assertAlmostEqual(result["rsp_pct"], (10.0 + (120 / 110 - 1) * 100) / 2)
        self.assertAlmostEqual(result["forskel_pp"], result["afkast_pct"] - result["rsp_pct"])
        self.assertAlmostEqual(result["vinderandel_pct"], 50.0)
        self.assertAlmostEqual(result["slaar_rsp_pct"], 50.0)
        self.assertEqual(result["start"], self.day(0))
        self.assertEqual(result["dage"], (date(2026, 10, 30) - self.days[0].date()).days)
        self.assertTrue(result["for_tidligt"])
        json.dumps(result, allow_nan=False)

    def test_missing_rsp_trade_is_left_out_and_counted(self):
        frame = trades(
            {"ticker": "A", "koebsdato": self.day(0), "koebskurs": 100.0, "salgsdato": self.day(10), "salgskurs": 120.0},
            {"ticker": "OLD", "koebsdato": "2020-01-06", "koebskurs": 10.0, "salgsdato": "2020-02-03", "salgskurs": 20.0},
            {"ticker": "NOPRICE", "koebsdato": self.day(5), "koebskurs": 10.0})        # åben uden seneste kurs
        result = paper.score(frame, {}, self.rsp, date(2026, 10, 30))
        self.assertEqual((result["antal"], result["sammenlignet"], result["udeladt"]), (3, 1, 2))
        self.assertAlmostEqual(result["afkast_pct"], 20.0)                              # kun A indgår
        self.assertAlmostEqual(result["rsp_pct"], 10.0)
        self.assertEqual(result["start"], "2020-01-06")                                 # startdatoen er den første handel

    def test_without_benchmark_nothing_is_compared(self):
        frame = trades({"ticker": "A", "koebsdato": self.day(0), "koebskurs": 100.0, "salgsdato": self.day(10),
                        "salgskurs": 120.0})
        for missing in (None, pd.DataFrame()):
            result = paper.score(frame, {}, missing, date(2026, 10, 30))
            self.assertEqual((result["antal"], result["sammenlignet"], result["udeladt"]), (1, 0, 1))
            self.assertIsNone(result["afkast_pct"])
            self.assertIsNone(result["forskel_pp"])

    def test_three_months_threshold(self):
        frame = trades({"ticker": "A", "koebsdato": "2026-07-01", "koebskurs": 100.0, "salgsdato": "2026-07-10",
                        "salgskurs": 105.0})
        rsp = bench(np.linspace(100, 130, 200), end="2026-10-30")
        self.assertFalse(paper.score(frame, {}, rsp, date(2026, 10, 30))["for_tidligt"])     # 121 dage
        self.assertTrue(paper.score(frame, {}, rsp, date(2026, 8, 15))["for_tidligt"])        # 45 dage

    def test_log_overwrites_same_date(self):
        frame = trades({"ticker": "A", "koebsdato": self.day(0), "koebskurs": 100.0, "salgsdato": self.day(10),
                        "salgskurs": 120.0})
        first = paper.score(frame, {}, self.rsp, date(2026, 10, 30))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "undermappe" / "papir_stilling.csv"
            paper.log_score(first, date(2026, 10, 29), path)
            paper.log_score(first, date(2026, 10, 30), path)
            again = dict(first, afkast_pct=1.5, rsp_pct=1.0, forskel_pp=0.5)
            paper.log_score(again, date(2026, 10, 30), path)           # dublet: erstatter linjen
            lines = path.read_text(encoding="utf-8-sig").splitlines()
            self.assertEqual(lines[0], "dato;antal;gns_afkast;gns_rsp;forskel")
            self.assertEqual(len(lines), 3)
            self.assertEqual(lines[1].split(";")[0], "2026-10-29")
            self.assertEqual(lines[2], "2026-10-30;1;1.5;1.0;0.5")
            empty = paper.score(trades(), {}, self.rsp, date(2026, 10, 31))
            paper.log_score(empty, date(2026, 10, 31), path)           # ingen handler: tomme tal, ikke gæt
            self.assertEqual(path.read_text(encoding="utf-8-sig").splitlines()[3], "2026-10-31;0;;;")

    def test_payload_has_paper_score(self):
        history = prices(np.linspace(50, 100, 60))
        score = paper.score(trades({"ticker": "A", "koebsdato": "2026-10-05", "koebskurs": 100.0,
                                    "salgsdato": "2026-10-12", "salgskurs": 110.0}), {}, bench(np.arange(100, 121)),
                            date(2026, 10, 30))
        payload = playbook.build_payload(
            rows=[row("A")], histories={"A": history}, currencies={}, regions={}, atrs={}, research=[], breadth={},
            benchmark="RSP", factors=None, scores=None, regional=None, trades=trades(), last_prices={}, changes=[],
            paper_score=score, now=datetime(2026, 11, 2, 7, 0, tzinfo=timezone.utc))
        section = payload["paper_score"]
        self.assertEqual((section["antal"], section["sammenlignet"], section["udeladt"]), (1, 1, 0))
        self.assertAlmostEqual(section["afkast_pct"], 10.0)
        self.assertEqual(section["start"], "2026-10-05")
        self.assertTrue(section["for_tidligt"])
        json.dumps(payload, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
