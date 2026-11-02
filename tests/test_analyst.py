"""Offline tests af regnskabsdato og EPS-revisioner (value trap)."""
import unittest
from datetime import date

import pandas as pd

from stockscanner.analyst import earnings_blocks, next_earnings, revisions, value_trap


def trend(now, d30, d90):
    return pd.DataFrame({"current": [now, now], "7daysAgo": [now, now], "30daysAgo": [d30, d30],
                         "60daysAgo": [d90, d90], "90daysAgo": [d90, d90]}, index=["0y", "+1y"])


class EarningsTests(unittest.TestCase):
    def test_next_upcoming_date(self):
        calendar = {"Earnings Date": [date(2026, 10, 1), date(2026, 11, 4), date(2027, 1, 27)]}
        self.assertEqual(next_earnings(calendar, date(2026, 11, 2)), date(2026, 11, 4))
        self.assertIsNone(next_earnings({}, date(2026, 11, 2)))
        self.assertIsNone(next_earnings(None, date(2026, 11, 2)))

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
