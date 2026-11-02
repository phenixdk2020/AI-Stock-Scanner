"""Offline tests af portefølje og salgstjek."""
import tempfile
import unittest
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from stockscanner.portfolio import Position, exit_check, load_portfolio, profit_pct


def daily(close, start="2025-01-01"):
    index = pd.bdate_range(start, periods=len(close))
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"Open": close, "High": close * 1.01, "Low": close * 0.99, "Close": close}, index=index)


class PortfolioTests(unittest.TestCase):
    def test_load_portfolio(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "p.csv"
            path.write_text("ticker;antal;koebskurs;koebsdato\nNOVO-B.CO;10;300;2026-01-15\n", encoding="utf-8")
            positions = load_portfolio(path)
        self.assertEqual(positions["NOVO-B.CO"], Position("NOVO-B.CO", 10.0, 300.0, date(2026, 1, 15)))

    def test_missing_file_is_empty(self):
        self.assertEqual(load_portfolio(Path("findes-ikke.csv")), {})

    def test_exit_reasons_after_fall_and_none_in_uptrend(self):
        up = daily(np.linspace(100, 200, 300))
        position = Position("X", 1, 100, date(2025, 1, 1))
        self.assertEqual(exit_check(up, position, False), [])
        self.assertAlmostEqual(profit_pct(up, position), 100.0)
        fall = daily(np.concatenate([np.linspace(100, 200, 250), np.linspace(200, 140, 50)]))
        reasons = exit_check(fall, position, True)
        self.assertTrue(any("Supertrend" in r for r in reasons))
        self.assertTrue(any("SMA50" in r for r in reasons))
        self.assertIn("StockMap-salg denne uge", reasons)


if __name__ == "__main__":
    unittest.main()
