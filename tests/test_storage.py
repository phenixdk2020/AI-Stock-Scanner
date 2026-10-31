"""SQLite-tests uden eksterne tjenester."""
import tempfile
from pathlib import Path
import unittest

import pandas as pd

from stockscanner.core import analyze_prices
from stockscanner.storage import recent_scans, save_scans, load_watchlist, save_watchlist


class StorageTests(unittest.TestCase):
    def test_scan_history_and_watchlist(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            index = pd.date_range("2024-01-01", periods=210, freq="B")
            prices = pd.DataFrame({"Close": list(range(100, 310)), "Volume": 500}, index=index)
            result = analyze_prices(prices, "MSFT")
            self.assertEqual(save_scans([result], path=root / "db.sqlite3"), 1)
            stored = recent_scans(path=root / "db.sqlite3")
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored.iloc[0]["ticker"], "MSFT")
            save_watchlist(["msft", "novo-b.co"], path=root / "watch.txt")
            self.assertEqual(load_watchlist(path=root / "watch.txt"), ["MSFT", "NOVO-B.CO"])


if __name__ == "__main__":
    unittest.main()
