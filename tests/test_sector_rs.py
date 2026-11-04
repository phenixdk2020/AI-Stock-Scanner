"""Offline tests af sektor-delen (B-07/B-11)."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from stockscanner import sector_rs as sr
from stockscanner.mti_lite import mti_state


def daily(close, end="2025-12-26"):
    close = np.asarray(close, dtype=float)
    index = pd.bdate_range(end=end, periods=len(close))
    return pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close}, index=index)


class SectorMapTests(unittest.TestCase):
    def test_us_and_eu_etf(self):
        self.assertEqual(sr.sector_etf("MSFT", {"sector": "Technology"}), "XLK")
        self.assertEqual(sr.sector_etf("SAP.DE", {"sector": "Technology"}), "EXV3.DE")
        self.assertEqual(sr.sector_etf("NOVO-B.CO", {"sector": "Healthcare", "industry": "Drug Manufacturers"}), "EXV4.DE")
        self.assertEqual(sr.sector_etf("TOP.CO", {"sector": "Financial Services", "industry": "Insurance - Life"}), "EXH5.DE")
        self.assertEqual(sr.sector_etf("VOLV-B.ST", {"sector": "Consumer Cyclical", "industry": "Auto Manufacturers"}), "EXV5.DE")

    def test_unknown_sector_gives_none(self):
        self.assertIsNone(sr.sector_etf("SPY", {}))
        self.assertIsNone(sr.sector_etf("XYZ", {"sector": "Ukendt"}))
        self.assertIsNone(sr.sector_etf("XYZ", None))

    def test_benchmark(self):
        self.assertEqual(sr.benchmark_for("AAPL"), "RSP")
        self.assertEqual(sr.benchmark_for("DSV.CO"), "EXSA.DE")

    def test_cache_fetches_only_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "sector_map.json"
            calls = []

            def fake(ticker):
                calls.append(ticker)
                return {"sector": "Energy"} if ticker == "XOM" else {}

            first = sr.ensure_sector_map(["XOM", "SPY"], path, fake)
            self.assertEqual(first["XOM"], {"sector": "Energy"})
            sr.ensure_sector_map(["XOM", "SPY", "CVX"], path, fake)
            self.assertEqual(calls, ["XOM", "SPY", "CVX"])
            self.assertEqual(sr.load_sector_map(path)["SPY"], {})
        self.assertEqual(sr.load_sector_map(Path("findes/ikke.json")), {})


class RsTests(unittest.TestCase):
    def test_flags_match_mti_state_on_friday(self):
        rng = np.random.default_rng(3)
        stock = daily(100 * np.exp(np.cumsum(rng.normal(0.001, 0.01, 300))))
        sector = daily(100 * np.exp(np.cumsum(rng.normal(0.0, 0.008, 300))))
        self.assertEqual(sr.mti_sector_state(stock, sector), mti_state(stock, sector))

    def test_outperformer_green_laggard_not(self):
        sector = daily(np.full(200, 100.0))
        self.assertTrue(sr.mti_sector_state(daily(100 * 1.003 ** np.arange(200)), sector)["double_green"])
        self.assertFalse(sr.mti_sector_state(daily(100 * 0.997 ** np.arange(200)), sector)["double_green"])

    def test_too_little_data(self):
        state = sr.mti_sector_state(daily(np.full(10, 100.0)), daily(np.full(10, 100.0)))
        self.assertEqual(state, {"daily": None, "weekly": None, "double_green": None})

    def test_flags_on_asof_and_none_early(self):
        sector = daily(np.full(200, 100.0))
        stock = daily(100 * 1.003 ** np.arange(200))
        flags = sr.rs_flags(stock, sector)
        self.assertIsNone(sr.flags_on(flags, flags.index[3]))
        self.assertTrue(sr.flags_on(flags, flags.index[-1]))
        self.assertIsNone(sr.flags_on(flags, "2000-01-01"))


class SectorConfirmTests(unittest.TestCase):
    def test_confirmed_by_angle(self):
        index = pd.date_range("2025-01-03", periods=3, freq="W-FRI")
        rot = pd.DataFrame({"angle": [np.nan, 45.0, 200.0]}, index=index)
        self.assertIsNone(sr.sector_confirmed(rot, index[0]))
        self.assertTrue(sr.sector_confirmed(rot, index[1]))
        self.assertTrue(sr.sector_confirmed(rot, index[2] - pd.Timedelta(days=1)))  # uge 3 er ikke afsluttet
        self.assertFalse(sr.sector_confirmed(rot, index[2]))
        self.assertIsNone(sr.sector_confirmed(rot, "2024-01-01"))


if __name__ == "__main__":
    unittest.main()
