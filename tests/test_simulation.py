"""Offline tests af porteføljesimuleringen."""
import unittest

import numpy as np
import pandas as pd

from stockscanner.simulation import buy_and_hold, simulate, weekly_panel


def daily(close, start="2018-01-01"):
    index = pd.bdate_range(start, periods=len(close))
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"Open": close, "High": close * 1.01, "Low": close * 0.99, "Close": close}, index=index)


class SimulationTests(unittest.TestCase):
    def setUp(self):
        days = np.arange(1500)
        self.bench = daily(np.full(1500, 100.0))
        self.histories = {f"S{i}": daily(100 * np.exp(0.25 * np.sin(2 * np.pi * (days + 40 * i) / 260)))
                          for i in range(5)}

    def test_panel_and_simulation_run(self):
        panel = weekly_panel(self.histories, self.bench)
        self.assertEqual(len(panel), 5)
        self.assertTrue({"buy", "sell", "st_down", "close", "next_open"} <= set(panel["S0"].columns))
        result = simulate(panel, start="2019-06-01", max_positions=3)
        self.assertGreater(len(result.trades), 0)
        self.assertLessEqual(result.max_drawdown, 0)
        self.assertTrue(np.isfinite(result.cagr))

    def test_max_positions_respected(self):
        panel = weekly_panel(self.histories, self.bench)
        result = simulate(panel, start="2019-06-01", max_positions=1)
        open_at_once = 0
        for week in result.equity.index:
            held = ((result.trades["buy_week"] <= week) & (result.trades["sell_week"] > week)).sum() if len(result.trades) else 0
            open_at_once = max(open_at_once, held)
        self.assertLessEqual(open_at_once, 1)

    def picks(self, rank, slots=2):
        """Tre aktier har købssignal i første uge og sælges i sidste; returnerer de købte i købsrækkefølge."""
        weeks = pd.date_range("2020-01-03", periods=3, freq="W-FRI")
        table = pd.DataFrame({"buy": [True, False, False], "sell": [False, False, True], "st_down": False,
                              "close": 100.0, "next_open": 100.0, "above50": True, "rs_up": True}, index=weeks)
        panel = {ticker: table.copy() for ticker in ("AAA", "BBB", "CCC")}
        return list(simulate(panel, "2020-01-01", max_positions=slots, rank=rank).trades["ticker"])

    def test_without_rank_the_choice_stays_alphabetical(self):
        self.assertEqual(self.picks(None), ["AAA", "BBB"])

    def test_rank_buys_highest_score_first(self):
        rank = pd.DataFrame({"AAA": 1.0, "BBB": 2.0, "CCC": 3.0}, index=[pd.Timestamp("2020-01-03")])
        self.assertEqual(self.picks(rank), ["CCC", "BBB"])

    def test_stocks_without_score_come_last(self):
        rank = pd.DataFrame({"AAA": np.nan, "BBB": -5.0}, index=[pd.Timestamp("2020-01-03")])
        self.assertEqual(self.picks(rank), ["BBB", "AAA"])
        self.assertEqual(self.picks(rank, slots=3), ["BBB", "AAA", "CCC"])

    def test_buy_and_hold(self):
        cagr, dd = buy_and_hold(daily(100 * 1.0004 ** np.arange(1500)), "2018-06-01")
        self.assertGreater(cagr, 0)
        self.assertAlmostEqual(dd, 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
