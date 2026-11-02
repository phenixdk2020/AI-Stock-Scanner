"""Offline tests af Value- og Momentum-percentiler."""
import unittest

import numpy as np
import pandas as pd

from stockscanner.scores import momentum_factors, momentum_scores, value_factors, value_scores


def info(pe, pb, cap, fcf, dy, ps, ev):
    return {"trailingPE": pe, "priceToBook": pb, "marketCap": cap, "freeCashflow": fcf,
            "dividendYield": dy, "priceToSalesTrailing12Months": ps, "enterpriseToEbitda": ev}


class ScoreTests(unittest.TestCase):
    def test_value_factors_drop_negative_multiples(self):
        factors = value_factors(info(-5, 2, 100, -10, None, 1, 8))
        self.assertIsNone(factors["pe"])
        self.assertIsNone(factors["pfcf"])
        self.assertEqual(factors["dividend_yield"], 0.0)

    def test_cheapest_gets_highest_value_score(self):
        scores = value_scores({
            "CHEAP": info(8, 1, 100, 20, 0.05, 0.5, 5),
            "MID": info(15, 2, 100, 10, 0.02, 1.5, 10),
            "DEAR": info(40, 8, 100, 2, 0.0, 6, 30),
        })
        self.assertEqual(scores.idxmax(), "CHEAP")
        self.assertEqual(scores.idxmin(), "DEAR")

    def test_momentum(self):
        up = pd.DataFrame({"Close": 100 * 1.001 ** np.arange(300)})
        down = pd.DataFrame({"Close": 100 * 0.999 ** np.arange(300)})
        flat = pd.DataFrame({"Close": np.full(300, 100.0)})
        factors = momentum_factors(up)
        self.assertGreater(factors["ret_12m"], 0)
        self.assertEqual(factors["stability"], 1.0)
        scores = momentum_scores({"UP": up, "DOWN": down, "FLAT": flat})
        self.assertEqual(scores.idxmax(), "UP")
        self.assertEqual(scores.idxmin(), "DOWN")

    def test_short_history_gives_none(self):
        factors = momentum_factors(pd.DataFrame({"Close": np.arange(1, 50, dtype=float)}))
        self.assertIsNone(factors["ret_12m"])
        self.assertIsNone(factors["stability"])


if __name__ == "__main__":
    unittest.main()
