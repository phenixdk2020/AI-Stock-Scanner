"""Dagligt entry-tjek: kun købskravene opdateres, resten af playbooken bliver stående."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from stockscanner import entry_check
from stockscanner.weekly_list import WeeklyRow, apply_news


def prices():
    close = pd.Series(np.linspace(50, 100, 300), index=pd.bdate_range(end="2026-11-05", periods=300))
    return pd.DataFrame({"Open": close, "High": close * 1.01, "Low": close * 0.99, "Close": close, "Volume": 1000.0})


def row(ticker, action, reasons="alle krav opfyldt"):
    return WeeklyRow(ticker, action, "køb 2026-10-30", None, None, None, 80.0, 50.0, 60.0, 55.0, 1.5, reasons)


NOW = datetime(2026, 11, 6, 8, 0, tzinfo=timezone.utc)


class EntryCheckTests(unittest.TestCase):
    def payload(self):
        return {"stocks": {"A": {"action": "hold øje", "news_summary": "nyheder: 1+", "quality": 80},
                           "B": {"action": "KØB-KANDIDAT"},
                           "C": {"action": "SÆLG (ejet)", "reasons": "stop ramt"}},
                "market_date": "2026-11-02", "changes": ["D: gammel ændring"]}

    def test_reports_moves_in_and_out_of_entry_and_keeps_the_rest(self):
        payload = self.payload()
        histories = {t: prices() for t in "AB"}
        changes = entry_check.apply(payload, [row("A", "KØB-KANDIDAT"), row("B", "hold øje", "regnskab om 3 d")],
                                    histories, NOW)
        self.assertEqual(changes, ["A: Entry nu (var hold øje)", "B: ikke længere Entry (regnskab om 3 d)"])
        self.assertEqual(payload["changes"], changes + ["D: gammel ændring"])
        stock = payload["stocks"]["A"]
        self.assertEqual((stock["action"], stock["entry_checked"]), ("KØB-KANDIDAT", "2026-11-06"))
        self.assertEqual((stock["news_summary"], stock["quality"]), ("nyheder: 1+", 80))
        self.assertEqual(payload["market_date"], "2026-11-05")

    def test_owned_stocks_are_never_touched(self):
        payload = self.payload()
        self.assertEqual(entry_check.followed(payload, ["A", "C", "Z"]), ["A"])
        self.assertEqual(entry_check.apply(payload, [row("C", "KØB-KANDIDAT")], {"C": prices()}, NOW), [])
        self.assertEqual(payload["stocks"]["C"], {"action": "SÆLG (ejet)", "reasons": "stop ramt"})

    def test_large_negative_news_from_monday_still_blocks(self):
        blocked = apply_news([row("A", "KØB-KANDIDAT")], {"A": "nyheder: 1−; STOR NEGATIV NYHED: svindel"})
        self.assertEqual(blocked[0].action, "hold øje")

    def test_latest_factors_keep_the_unrounded_score_from_the_newest_day(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "h.csv"
            path.write_text("ticker;quality;dato\nA;80.5;2026-10-26\nA;59.6;2026-11-02\n", encoding="utf-8-sig")
            self.assertEqual(entry_check.latest_factors(path).loc["A", "quality"], 59.6)


if __name__ == "__main__":
    unittest.main()
