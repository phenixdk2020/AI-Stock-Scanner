"""Offline tests af MTI-lite."""
import unittest

import numpy as np
import pandas as pd

from stockscanner.mti_lite import home_index, mti_state


def daily(close, start="2025-01-06"):
    return pd.DataFrame({"Close": np.asarray(close, dtype=float)}, index=pd.bdate_range(start, periods=len(close)))


class MtiTests(unittest.TestCase):
    def test_home_index(self):
        self.assertEqual(home_index("NOVO-B.CO"), "^OMXC25")
        self.assertEqual(home_index("SAP.DE"), "^GDAXI")
        self.assertEqual(home_index("MSFT"), "RSP")

    def test_outperformer_is_double_green_and_laggard_is_not(self):
        index = daily(np.full(200, 100.0))
        self.assertTrue(mti_state(daily(100 * 1.003 ** np.arange(200)), index)["double_green"])
        state = mti_state(daily(100 * 0.997 ** np.arange(200)), index)
        self.assertFalse(state["daily"])
        self.assertFalse(state["double_green"])

    def test_too_little_data(self):
        self.assertIsNone(mti_state(daily(np.arange(1, 10)), daily(np.full(9, 1.0)))["daily"])


if __name__ == "__main__":
    unittest.main()
