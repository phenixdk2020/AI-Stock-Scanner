"""Offline tests af SEC EDGAR-udtrækket (ingen netværk)."""
import unittest

import pandas as pd

from stockscanner.sec_edgar import annual_eps_from_facts, split_adjust


def entry(start, end, val, form="10-K", filed="2020-01-01"):
    return {"start": start, "end": end, "val": val, "form": form, "filed": filed}


class SecEdgarTests(unittest.TestCase):
    def test_keeps_annual_10k_and_latest_filing(self):
        facts = {"facts": {"us-gaap": {"EarningsPerShareDiluted": {"units": {"USD/shares": [
            entry("2018-07-01", "2019-06-30", 5.0, filed="2019-08-01"),
            entry("2018-07-01", "2019-06-30", 5.06, filed="2021-08-01"),   # omarbejdet senere
            entry("2019-04-01", "2019-06-30", 1.4),                        # kvartal: udelades
            entry("2019-07-01", "2020-06-30", 5.76, form="10-Q"),          # forkert form: udelades
        ]}}}}}
        eps = annual_eps_from_facts(facts)
        self.assertEqual(list(eps.index), [pd.Timestamp("2019-06-30")])
        self.assertAlmostEqual(eps.iloc[0], 5.06)

    def test_falls_back_to_basic_eps(self):
        facts = {"facts": {"us-gaap": {"EarningsPerShareBasic": {"units": {"USD/shares": [
            entry("2020-01-01", "2020-12-31", 2.0)]}}}}}
        self.assertAlmostEqual(annual_eps_from_facts(facts).iloc[0], 2.0)

    def test_empty_facts(self):
        self.assertTrue(annual_eps_from_facts({}).empty)

    def test_split_adjust_divides_only_before_split(self):
        eps = pd.Series([10.0, 12.0, 3.5], index=pd.to_datetime(["2022-12-31", "2023-12-31", "2024-12-31"]))
        splits = pd.Series([4.0], index=pd.to_datetime(["2024-06-10"]))
        adjusted = split_adjust(eps, splits)
        self.assertEqual(list(adjusted.round(2)), [2.5, 3.0, 3.5])


if __name__ == "__main__":
    unittest.main()
