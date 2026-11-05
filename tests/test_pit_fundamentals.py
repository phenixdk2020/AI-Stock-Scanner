import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stockscanner import pit_fundamentals as pit  # noqa: E402


def entry(start, end, val, filed, form="10-K"):
    return {"start": start, "end": end, "val": val, "filed": filed, "form": form}


def facts(**tags):
    return {"facts": {"us-gaap": {tag: {"units": {"USD": rows}} for tag, rows in tags.items()}}}


class PointInTimeTest(unittest.TestCase):
    def test_future_filing_never_used(self):
        f = facts(EarningsPerShareDiluted=[entry("2020-01-01", "2020-12-31", 2.0, "2021-02-15")])
        self.assertIsNone(pit.as_of(f, "2021-02-14")["eps_ttm"])
        self.assertEqual(pit.as_of(f, "2021-02-15")["eps_ttm"], 2.0)

    def test_restated_figure_counts_only_from_its_own_filed_date(self):
        f = facts(EarningsPerShareDiluted=[
            entry("2020-01-01", "2020-12-31", 2.0, "2021-02-15"),
            entry("2020-01-01", "2020-12-31", 1.5, "2022-02-15"),   # omarbejdet i næste års 10-K
        ])
        self.assertEqual(pit.as_of(f, "2021-12-31")["eps_ttm"], 2.0)
        self.assertEqual(pit.as_of(f, "2022-02-14")["eps_ttm"], 2.0)
        self.assertEqual(pit.as_of(f, "2022-02-15")["eps_ttm"], 1.5)

    def test_ttm_uses_year_plus_ytd_minus_prior_ytd(self):
        f = facts(EarningsPerShareDiluted=[
            entry("2020-01-01", "2020-12-31", 4.0, "2021-02-15"),
            entry("2020-01-01", "2020-06-30", 1.0, "2020-08-01", "10-Q"),
            entry("2021-01-01", "2021-06-30", 3.0, "2021-08-01", "10-Q"),
        ])
        self.assertEqual(pit.as_of(f, "2021-07-31")["eps_ttm"], 4.0)   # 10-Q endnu ikke indleveret
        self.assertEqual(pit.as_of(f, "2021-08-01")["eps_ttm"], 4.0 + 3.0 - 1.0)

    def test_ratios_and_no_future_in_growth(self):
        f = facts(
            NetIncomeLoss=[entry("2020-01-01", "2020-12-31", 100.0, "2021-02-15")],
            Revenues=[entry("2019-01-01", "2019-12-31", 800.0, "2020-02-15"),
                      entry("2020-01-01", "2020-12-31", 1000.0, "2021-02-15")],
            GrossProfit=[entry("2020-01-01", "2020-12-31", 400.0, "2021-02-15")],
            StockholdersEquity=[{"end": "2020-12-31", "val": 500.0, "filed": "2021-02-15", "form": "10-K"}],
            Assets=[{"end": "2020-12-31", "val": 2000.0, "filed": "2021-02-15", "form": "10-K"}],
            LongTermDebtNoncurrent=[{"end": "2020-12-31", "val": 250.0, "filed": "2021-02-15", "form": "10-K"}],
            OperatingIncomeLoss=[entry("2020-01-01", "2020-12-31", 200.0, "2021-02-15")],
            InterestExpense=[entry("2020-01-01", "2020-12-31", 20.0, "2021-02-15")],
        )
        r = pit.as_of(f, "2021-03-01")
        self.assertAlmostEqual(r["roe"], 0.2)
        self.assertAlmostEqual(r["roa"], 0.05)
        self.assertAlmostEqual(r["gross_margin"], 0.4)
        self.assertAlmostEqual(r["debt_equity"], 0.5)
        self.assertAlmostEqual(r["interest_coverage"], 10.0)
        self.assertAlmostEqual(r["revenue_growth"], 0.25)
        self.assertIsNone(pit.as_of(f, "2021-02-14")["roe"])

    def test_snapshot_lag_and_steps(self):
        f = facts(EarningsPerShareDiluted=[entry("2020-01-01", "2020-12-31", 2.0, "2021-02-15")])
        snap = pit.snapshots(pit.facts_table(f), since="2020-01-01")
        weeks = pd.DatetimeIndex(["2021-02-12", "2021-02-15", "2021-02-16", "2021-03-01"])
        got = pit.at_dates(snap, weeks, lag_days=1)
        self.assertTrue(np.isnan(got["eps_ttm"].iloc[0]))
        self.assertTrue(np.isnan(got["eps_ttm"].iloc[1]))   # samme dag: 1 dags forsinkelse
        self.assertEqual(got["eps_ttm"].iloc[2], 2.0)
        self.assertEqual(got["eps_ttm"].iloc[3], 2.0)

    def test_value_score_uses_only_past_and_present(self):
        idx = pd.date_range("2015-01-02", periods=400, freq="W-FRI")
        eps = pd.Series(1.0, index=idx)
        price = pd.Series(10.0, index=idx)
        price.iloc[-1] = 400.0                      # fremtidig/seneste spids må ikke ændre tidligere uger
        base = pit.value_score(price.iloc[:-1], eps.iloc[:-1])
        full = pit.value_score(price, eps)
        pd.testing.assert_series_equal(base, full.iloc[:-1])
        self.assertEqual(full.iloc[-1], 0.0)         # dyrest nogensinde

    def test_quality_percentile_rank(self):
        idx = pd.DatetimeIndex(["2020-01-03"])
        cols = [f"T{i}" for i in range(60)]
        good = pd.DataFrame([np.arange(60.0)], index=idx, columns=cols)
        tables = {k: good for k in ("roe", "roa", "gross_margin")}
        q = pit.quality_percentile(tables)
        self.assertGreater(q.iloc[0]["T59"], q.iloc[0]["T0"])
        self.assertGreaterEqual(q.iloc[0]["T59"], 99)


if __name__ == "__main__":
    unittest.main()
