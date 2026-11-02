"""Offline test af porteføljens kurser og gevinst."""
import unittest
from datetime import date

from stockscanner.portfolio import Position, valuation


class ValuationTests(unittest.TestCase):
    def test_value_and_gain(self):
        positions = {"MSFT": Position("MSFT", 10, 400.0, date(2026, 1, 5)),
                     "NOVO-B.CO": Position("NOVO-B.CO", 5, 300.0, date(2026, 2, 1))}
        table = valuation(positions, {"MSFT": (440.0, "USD"), "NOVO-B.CO": (None, None)}).set_index("ticker")
        self.assertAlmostEqual(table.loc["MSFT", "vaerdi"], 4400)
        self.assertAlmostEqual(table.loc["MSFT", "gevinst"], 400)
        self.assertAlmostEqual(table.loc["MSFT", "gevinst_pct"], 10)
        self.assertTrue(table.isna().loc["NOVO-B.CO", "kurs"])

    def test_change_since_yesterday(self):
        positions = {"MSFT": Position("MSFT", 10, 400.0, date(2026, 1, 5))}
        row = valuation(positions, {"MSFT": (440.0, "USD", 400.0)}).iloc[0]
        self.assertAlmostEqual(row["dag"], 400)
        self.assertAlmostEqual(row["dag_pct"], 10)

    def test_empty(self):
        self.assertTrue(valuation({}, {}).empty)


if __name__ == "__main__":
    unittest.main()
