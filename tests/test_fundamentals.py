"""Offline-tests af regnskabsnormalisering og cache; ingen netværk."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from stockscanner.fundamentals import FundamentalData, fetch_fundamentals
from stockscanner.storage import get_cached_fundamentals, load_or_fetch_fundamentals, save_fundamentals


def frame(columns: dict[str, dict[str, float]]) -> pd.DataFrame:
    """Kolonner = datoer, rækker = yfinance-lignende labels."""
    return pd.DataFrame({pd.Timestamp(date): values for date, values in columns.items()})


def fake_fetcher(income=None, balance=None, cashflow=None, info=None):
    def fetch(ticker):
        return {
            "income_stmt": income, "balance_sheet": balance, "cashflow": cashflow,
            "info": info if info is not None else {
                "sector": "Technology", "industry": "Software", "currency": "USD",
                "financialCurrency": "USD", "marketCap": 5000.0, "shortName": "Test A/S",
            },
        }
    return fetch


class FundamentalsTests(unittest.TestCase):
    def test_label_fallbacks(self):
        income = frame({"2024-12-31": {"Operating Revenue": 1000.0, "Net Income Common Stockholders": 100.0}})
        balance = frame({"2024-12-31": {
            "Common Stock Equity": 500.0, "Total Liabilities Net Minority Interest": 700.0,
            "Cash Cash Equivalents And Short Term Investments": 80.0,
        }})
        data = fetch_fundamentals("T", fetcher=fake_fetcher(income, balance, None))
        values = data.years[0].values
        self.assertEqual(values["revenue"], 1000.0)
        self.assertEqual(values["net_income"], 100.0)
        self.assertEqual(values["stockholders_equity"], 500.0)
        self.assertEqual(values["total_liabilities"], 700.0)
        self.assertEqual(values["cash"], 80.0)
        self.assertEqual(data.source, "yfinance (uofficiel)")
        self.assertEqual(data.sector, "Technology")
        self.assertEqual(data.years[0].end_date, "2024-12-31")

    def test_free_cash_flow_derived_from_ocf_and_capex(self):
        cash = frame({"2024-12-31": {"Operating Cash Flow": 300.0, "Capital Expenditure": -80.0}})
        values = fetch_fundamentals("T", fetcher=fake_fetcher(None, None, cash)).years[0].values
        self.assertEqual(values["capital_expenditure"], -80.0)
        self.assertEqual(values["free_cash_flow"], 220.0)

    def test_positive_capex_sign_is_normalised(self):
        cash = frame({"2024-12-31": {"Operating Cash Flow": 300.0, "Capital Expenditure": 80.0}})
        values = fetch_fundamentals("T", fetcher=fake_fetcher(None, None, cash)).years[0].values
        self.assertEqual(values["free_cash_flow"], 220.0)

    def test_reported_free_cash_flow_is_kept(self):
        cash = frame({"2024-12-31": {"Operating Cash Flow": 300.0, "Capital Expenditure": -80.0, "Free Cash Flow": 999.0}})
        values = fetch_fundamentals("T", fetcher=fake_fetcher(None, None, cash)).years[0].values
        self.assertEqual(values["free_cash_flow"], 999.0)

    def test_missing_fields_reported_and_never_invented(self):
        income = frame({"2024-12-31": {"Total Revenue": 1000.0}})
        data = fetch_fundamentals("T", fetcher=fake_fetcher(income, None, None))
        self.assertIsNone(data.years[0].values["total_debt"])
        self.assertIn("total_debt", data.missing)
        self.assertIn("free_cash_flow", data.missing)
        self.assertNotIn("revenue", data.missing)

    def test_nan_is_missing_and_years_sorted_newest_first(self):
        income = frame({
            "2022-12-31": {"Total Revenue": 800.0},
            "2024-12-31": {"Total Revenue": float("nan")},
            "2023-12-31": {"Total Revenue": 900.0},
        })
        data = fetch_fundamentals("T", fetcher=fake_fetcher(income, None, None))
        self.assertEqual([y.end_date for y in data.years], ["2023-12-31", "2022-12-31"])

    def test_shares_label_recorded_and_no_income_statement_fallback(self):
        income = frame({
            "2024-12-31": {"Total Revenue": 1000.0, "Diluted Average Shares": 90.0},
            "2023-12-31": {"Total Revenue": 900.0, "Diluted Average Shares": 95.0},
        })
        balance = frame({
            "2024-12-31": {"Share Issued": 100.0, "Long Term Debt": 50.0},
            "2023-12-31": {"Ordinary Shares Number": 98.0, "Share Issued": 99.0},
        })
        data = fetch_fundamentals("T", fetcher=fake_fetcher(income, balance, None))
        new, old = data.years
        self.assertEqual((new.values["shares"], new.share_label), (100.0, "Share Issued"))
        self.assertEqual((old.values["shares"], old.share_label), (98.0, "Ordinary Shares Number"))
        self.assertEqual(new.values["long_term_debt"], 50.0)
        # uden balance-label bruges gennemsnitsaktier fra resultatopgørelsen IKKE
        only_income = fetch_fundamentals("T", fetcher=fake_fetcher(income, None, None))
        self.assertIsNone(only_income.years[0].values["shares"])
        self.assertIsNone(only_income.years[0].share_label)

    def test_no_data_raises(self):
        with self.assertRaises(ValueError):
            fetch_fundamentals("T", fetcher=fake_fetcher(pd.DataFrame(), None, None))


class FundamentalsCacheTests(unittest.TestCase):
    def sample(self, fetched: datetime) -> FundamentalData:
        income = frame({"2024-12-31": {"Total Revenue": 1000.0}})
        data = fetch_fundamentals("MSFT", fetcher=fake_fetcher(income))
        data.fetched_at_utc = fetched.isoformat(timespec="seconds")
        return data

    def test_save_load_and_expiry(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "db.sqlite3"
            now = datetime.now(timezone.utc)
            self.assertIsNone(get_cached_fundamentals("MSFT", path=db))
            save_fundamentals(self.sample(now - timedelta(days=2)), path=db)
            loaded = get_cached_fundamentals("MSFT", max_age_days=7, path=db)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.years[0].values["revenue"], 1000.0)
            self.assertIsNone(get_cached_fundamentals("MSFT", max_age_days=1, path=db))
            save_fundamentals(self.sample(now - timedelta(days=30)), path=db)  # erstatter rækken
            self.assertIsNone(get_cached_fundamentals("MSFT", max_age_days=7, path=db))

    def test_load_or_fetch_uses_cache(self):
        calls = []

        def fetcher(ticker):
            calls.append(ticker)
            return fake_fetcher(frame({"2024-12-31": {"Total Revenue": 5.0}}))(ticker)

        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "db.sqlite3"
            load_or_fetch_fundamentals("X", path=db, fetcher=fetcher)
            load_or_fetch_fundamentals("X", path=db, fetcher=fetcher)
            self.assertEqual(calls, ["X"])


if __name__ == "__main__":
    unittest.main()
