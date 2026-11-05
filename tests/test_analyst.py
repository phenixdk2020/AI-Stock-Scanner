"""Offline tests af regnskabsdato og EPS-revisioner (value trap)."""
import unittest
from datetime import date

import pandas as pd

from stockscanner.analyst import (estimate_next, earnings_blocks, next_earnings, next_from_dates, revisions,
                                  rising_estimates, value_trap)


def trend(now, d30, d90):
    return pd.DataFrame({"current": [now, now], "7daysAgo": [now, now], "30daysAgo": [d30, d30],
                         "60daysAgo": [d90, d90], "90daysAgo": [d90, d90]}, index=["0y", "+1y"])


class EarningsTests(unittest.TestCase):
    def test_next_upcoming_date(self):
        calendar = {"Earnings Date": [date(2026, 10, 1), date(2026, 11, 4), date(2027, 1, 27)]}
        self.assertEqual(next_earnings(calendar, date(2026, 11, 2)), date(2026, 11, 4))
        self.assertIsNone(next_earnings({}, date(2026, 11, 2)))
        self.assertIsNone(next_earnings(None, date(2026, 11, 2)))

    def test_next_date_comes_from_the_list_when_calendar_only_has_the_last_report(self):
        dates = [date(2026, 7, 27), date(2026, 10, 26), date(2027, 2, 18)]
        self.assertEqual(next_from_dates(dates, date(2026, 11, 5)), date(2027, 2, 18))
        self.assertIsNone(next_from_dates(dates[:2], date(2026, 11, 5)))

    def test_estimate_uses_typical_gap_and_refuses_old_or_short_history(self):
        dates = [date(2026, 1, 27), date(2026, 4, 28), date(2026, 7, 28), date(2026, 10, 27)]
        self.assertEqual(estimate_next(dates, date(2026, 11, 5)), date(2027, 1, 26))
        self.assertIsNone(estimate_next(dates[:2], date(2026, 11, 5)))
        self.assertIsNone(estimate_next([date(2015, 3, 1), date(2015, 6, 1), date(2015, 9, 1)], date(2026, 11, 5)))

    def test_rising_estimates_never_hides_a_value_trap(self):
        self.assertIn("EPS +1y", rising_estimates({"+1y": {"30d": 2.5, "90d": 1.0}}))
        self.assertIn("90 d", rising_estimates({"0y": {"30d": 0.1, "90d": 6.0}}))
        self.assertIsNone(rising_estimates({"+1y": {"30d": 1.0, "90d": 2.0}}))
        self.assertIsNone(rising_estimates({"0y": {"30d": 3.0}, "+1y": {"30d": -3.0}}))

    def test_block_window(self):
        today = date(2026, 11, 2)
        self.assertTrue(earnings_blocks(date(2026, 11, 4), today))
        self.assertTrue(earnings_blocks(date(2026, 11, 9), today))
        self.assertFalse(earnings_blocks(date(2026, 11, 10), today))
        self.assertFalse(earnings_blocks(None, today))


class TrapTests(unittest.TestCase):
    def test_rising_estimates_are_no_trap(self):
        self.assertIsNone(value_trap(revisions(trend(20.0, 19.7, 19.5))))

    def test_drop_over_30_days(self):
        text = value_trap(revisions(trend(9.7, 10.0, 9.7)))
        self.assertIn("30 d", text)

    def test_drop_over_90_days(self):
        text = value_trap(revisions(trend(9.4, 9.5, 10.0)))
        self.assertIn("90 d", text)
        self.assertIn("-6.0", text)

    def test_missing_data(self):
        self.assertEqual(revisions(None), {})
        self.assertEqual(revisions(pd.DataFrame()), {})
        self.assertIsNone(value_trap({}))


if __name__ == "__main__":
    unittest.main()
