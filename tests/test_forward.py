"""Fremadrettet måling: kun nye signaler, køb dagen efter listen og ingen gættede kurser."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from stockscanner import forward


def prices(start, days, first=100.0, daily=0.0):
    index = pd.bdate_range(start=start, periods=days)
    close = pd.Series(first * (1 + daily) ** np.arange(days), index=index)
    return pd.DataFrame({"Open": close, "Close": close})


def history(rows):
    return pd.DataFrame(rows, columns=["ticker", "dato", "action"])


class SignalTests(unittest.TestCase):
    def test_only_first_run_each_week_and_only_changes_count(self):
        found = forward.signals(history([
            ("A", "2026-11-02", "KØB-KANDIDAT"), ("A", "2026-11-04", "pil ned"),    # samme uge: kun mandag tæller
            ("A", "2026-11-09", "KØB-KANDIDAT"),                                    # stadig Entry: intet nyt signal
            ("A", "2026-11-16", "hold øje"), ("A", "2026-11-23", "KØB-KANDIDAT")]))
        self.assertEqual(list(zip(found["dato"], found["gruppe"])),
                         [("2026-11-02", "Entry"), ("2026-11-16", "Hold øje"), ("2026-11-23", "Entry")])

    def test_owned_is_not_a_group_but_leaving_it_is_a_new_signal(self):
        found = forward.signals(history([("A", "2026-11-02", "BEHOLD (ejet)"), ("A", "2026-11-09", "hold øje")]))
        self.assertEqual(list(found["dato"]), ["2026-11-09"])


class OutcomeTests(unittest.TestCase):
    def test_buys_the_open_after_the_list_and_compares_the_same_days(self):
        stock = prices("2026-01-05", 40)
        stock.loc["2026-01-06", "Open"] = 50.0      # åbningen dagen efter listen
        market = prices("2026-01-05", 40, daily=0.01)
        result = forward.outcome(stock, market, "2026-01-05", 4)
        self.assertAlmostEqual(result[0], 100.0)
        self.assertAlmostEqual(result[1], (1.01 ** 20 - 1) * 100)

    def test_a_list_cannot_buy_on_its_own_day(self):
        self.assertIsNone(forward.outcome(prices("2026-01-05", 1), prices("2026-01-05", 1), "2026-01-05"))

    def test_unfinished_period_gives_nothing_but_running_return_exists(self):
        stock, market = prices("2026-01-05", 10, daily=0.01), prices("2026-01-05", 10)
        self.assertIsNone(forward.outcome(stock, market, "2026-01-05", 4))
        self.assertIsNotNone(forward.outcome(stock, market, "2026-01-05"))

    def test_stock_that_stopped_trading_is_not_valued_at_an_old_price(self):
        self.assertIsNone(forward.outcome(prices("2026-01-05", 5), prices("2026-01-05", 60), "2026-01-05", 4))

    def test_a_hole_in_the_prices_is_not_bought_at_a_later_day(self):
        self.assertIsNone(forward.outcome(prices("2026-02-16", 60), prices("2026-01-05", 120), "2026-01-05", 4))
        self.assertIsNone(forward.outcome(prices("2026-01-05", 60), prices("2026-02-16", 60), "2026-01-05", 4))

    def test_prices_with_time_zone_work(self):
        stock = prices("2026-01-05", 40)
        stock.index = stock.index.tz_localize("Europe/Copenhagen")
        market = prices("2026-01-05", 40)
        market.index = market.index.tz_localize("America/New_York")
        self.assertEqual(forward.outcome(stock, market, "2026-01-05", 4), (0.0, 0.0))


class MeasureTests(unittest.TestCase):
    def measure(self, rows, histories, market):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "m.csv"
            result = forward.measure(history(rows), histories, market, path)
            return result, pd.read_csv(path, sep=";", encoding="utf-8-sig")

    def test_summary_and_saved_rows(self):
        market = prices("2026-01-05", 150)
        result, saved = self.measure([("A", "2026-01-05", "KØB-KANDIDAT"), ("B", "2026-01-05", "KØB-KANDIDAT")],
                                     {"A": prices("2026-01-05", 150, daily=0.01), "B": prices("2026-01-05", 150)}, market)
        cell = result["grupper"][0]["perioder"][1]
        self.assertEqual((cell["uger"], cell["antal"], cell["slaar_rsp_pct"]), (4, 2, 50.0))
        self.assertAlmostEqual(cell["forskel_pp"], (1.01 ** 20 - 1) * 50, places=2)
        self.assertEqual(result["afsluttede_entry"], 2)
        self.assertTrue(result["for_tidligt"])
        self.assertEqual(set(saved["horisont"]), {0, 4, 13, 26})

    def test_missing_prices_are_counted_never_guessed(self):
        market = prices("2026-01-05", 60)
        result, _ = self.measure([("A", "2026-01-05", "KØB-KANDIDAT")], {"A": prices("2026-01-05", 5)}, market)
        cell = result["grupper"][0]["perioder"][1]
        self.assertEqual((cell["antal"], cell["mangler"], cell["forskel_pp"]), (0, 1, None))

    def test_future_periods_are_waiting_not_missing(self):
        market = prices("2026-01-05", 10)
        result, _ = self.measure([("A", "2026-01-05", "KØB-KANDIDAT")], {"A": prices("2026-01-05", 10)}, market)
        self.assertEqual(result["grupper"][0]["perioder"][1]["mangler"], 0)

    def test_first_week_without_any_finished_period_still_works(self):
        result, saved = self.measure([("A", "2026-01-16", "pil ned")], {}, prices("2026-01-05", 9))
        self.assertTrue(saved.empty)
        self.assertEqual(result["grupper"][2]["signaler"], 1)
        self.assertTrue(forward.report(result))


class RunTests(unittest.TestCase):
    def test_fetches_stocks_no_longer_on_the_list_and_survives_a_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "h.csv"
            history([("A", "2026-01-05", "pil ned"), ("B", "2026-01-05", "pil ned")]).to_csv(
                path, sep=";", index=False, encoding="utf-8-sig")
            asked = []

            def fetch(ticker):
                asked.append(ticker)
                raise ValueError("ingen data")

            market = prices("2026-01-05", 40)
            result = forward.run(path, {"A": market}, market, fetch, Path(folder) / "m.csv")
        self.assertEqual(asked, ["B"])
        self.assertEqual(result["grupper"][2]["perioder"][1]["antal"], 1)


if __name__ == "__main__":
    unittest.main()
