"""Offline tests af papirporteføljen."""
import unittest
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd

from stockscanner import paper


def prices(values):
    index = pd.bdate_range(end="2026-10-30", periods=len(values))
    close = pd.Series(values, index=index, dtype=float)
    return pd.DataFrame({"Open": close, "High": close * 1.01, "Low": close * 0.99, "Close": close, "Volume": 1})


class PaperTests(unittest.TestCase):
    def test_buy_candidate_is_bought_once(self):
        rising = prices(np.linspace(50, 100, 300))
        rows = [SimpleNamespace(ticker="A", action="KØB-KANDIDAT"), SimpleNamespace(ticker="B", action="hold øje")]
        frame, messages = paper.update(paper.load(path=paper.Path("ikke-findes.csv")), rows, {"A": rising, "B": rising},
                                       date(2026, 11, 2))
        self.assertEqual(list(frame["ticker"]), ["A"])
        self.assertEqual(messages, ["PAPIR KØB A 100.00"])
        again, _ = paper.update(frame, rows, {"A": rising}, date(2026, 11, 9))
        self.assertEqual(len(again), 1)

    def test_exit_rule_closes_trade(self):
        falling = prices(np.r_[np.linspace(50, 100, 250), np.linspace(100, 70, 50)])
        frame = pd.DataFrame([{"ticker": "A", "koebsdato": "2025-06-02", "koebskurs": 60.0}]).reindex(columns=paper.COLUMNS)
        frame, messages = paper.update(frame, [], {"A": falling}, date(2026, 11, 2))
        self.assertEqual(frame.loc[0, "salgsdato"], "2026-11-02")
        self.assertTrue(messages[0].startswith("PAPIR SALG A"))

    def test_summary(self):
        frame = pd.DataFrame([{"ticker": "A", "koebsdato": "2026-01-05", "koebskurs": 100.0, "salgsdato": "2026-03-02",
                               "salgskurs": 110.0, "salgsgrund": "x"},
                              {"ticker": "B", "koebsdato": "2026-02-02", "koebskurs": 50.0}]).reindex(columns=paper.COLUMNS)
        result = paper.summary(frame, {"B": 45.0})
        self.assertEqual((result["handler"], result["aabne"]), (2, 1))
        self.assertAlmostEqual(result["afkast_pct"], 0.0)
        self.assertAlmostEqual(result["vundne_pct"], 50.0)
        self.assertEqual(paper.summary(pd.DataFrame(columns=paper.COLUMNS), {})["handler"], 0)


if __name__ == "__main__":
    unittest.main()
