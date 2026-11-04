"""Offline tests af regnskabsrisiko: niveau, vindue, regnskabsbevægelse, log og at den aldrig ændrer handlingen."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pandas as pd

from stockscanner import earnings_risk as er
from stockscanner import playbook
from stockscanner.analyst import AnalystInfo
from stockscanner.news import NewsItem
from stockscanner.weekly_list import UNKNOWN_EARNINGS, WeeklyRow, build_rows

TODAY = date(2026, 11, 4)
CUT = {"0y": {"30d": -3.0, "90d": -1.0}}
FLAT = {"0y": {"30d": 0.5, "90d": 1.0}}


def prices(values, end="2026-11-03"):
    index = pd.bdate_range(end=end, periods=len(values))
    close = pd.Series(values, index=index, dtype=float)
    return pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close, "Volume": 1})


def item(sentiment, published="2026-11-02"):
    return NewsItem("t", "s", "https://x/" + sentiment + published, published, sentiment, 1)


STEADY = prices(np.full(60, 100.0))
RISING = prices(np.linspace(100, 160, 60))     # ca. +24 % på 30 handelsdage


class PointTests(unittest.TestCase):
    def test_all_three_points_is_high(self):
        result = er.assess(5, AnalystInfo(revisions=CUT), [item("negativ"), item("negativ"), item("positiv")], RISING, TODAY)
        self.assertEqual((result["level"], result["points"]), ("Høj", 3))
        self.assertEqual(len(result["reasons"]), 3)

    def test_two_points_is_high_one_is_middle_zero_is_low(self):
        two = er.assess(5, AnalystInfo(revisions=CUT), [item("positiv")], RISING, TODAY)
        self.assertEqual((two["level"], two["points"]), ("Høj", 2))
        one = er.assess(5, AnalystInfo(revisions=CUT), [item("positiv")], STEADY, TODAY)
        self.assertEqual((one["level"], one["points"]), ("Middel", 1))
        zero = er.assess(5, AnalystInfo(revisions=FLAT), [item("positiv")], STEADY, TODAY)
        self.assertEqual((zero["level"], zero["points"]), ("Lav", 0))
        self.assertEqual(zero["reasons"], ["ingen advarselstegn"])

    def test_missing_data_gives_no_points_but_is_stated(self):
        result = er.assess(5, None, None, None, TODAY)
        self.assertEqual((result["level"], result["points"]), ("Lav", 0))
        self.assertEqual(len(result["reasons"]), 3)
        self.assertTrue(all("ingen data" in r for r in result["reasons"]))

    def test_estimates_without_30d_change_are_no_data(self):
        self.assertIsNone(er.estimates_cut(AnalystInfo(revisions={"0y": {"90d": -9.0}})))
        self.assertIsNone(er.estimates_cut(AnalystInfo()))
        self.assertTrue(er.estimates_cut(AnalystInfo(revisions={"0y": {"30d": -2.0}})))     # grænsen er med
        self.assertFalse(er.estimates_cut(AnalystInfo(revisions={"0y": {"30d": -1.9}})))

    def test_news_needs_more_negative_than_positive_within_seven_days(self):
        self.assertEqual(er.negative_news([item("negativ"), item("positiv")], TODAY)[0], False)    # lige: intet point
        self.assertEqual(er.negative_news([item("negativ"), item("neutral")], TODAY), (True, 0, 1))
        old = [item("negativ", "2026-10-20")]
        self.assertIsNone(er.negative_news(old, TODAY)[0])                                         # for gammel = ingen data
        self.assertIsNone(er.negative_news([item("uvurderet")], TODAY)[0])
        self.assertIsNone(er.negative_news(None, TODAY)[0])

    def test_run_up_threshold_and_too_little_history(self):
        flat_then_up = np.concatenate([np.full(30, 100.0), np.full(1, 100.0), np.full(30, 115.0)])
        self.assertTrue(er.run_up(prices(flat_then_up))[0])
        just_below = np.concatenate([np.full(31, 100.0), np.full(30, 114.9)])
        self.assertFalse(er.run_up(prices(just_below))[0])
        self.assertEqual(er.run_up(prices(np.full(20, 100.0))), (None, None))
        self.assertEqual(er.run_up(None), (None, None))


class WindowTests(unittest.TestCase):
    def test_only_assessed_within_14_days(self):
        self.assertEqual(er.EARNINGS_WINDOW_DAYS, 14)
        for days in (0, 1, 14):
            self.assertIsNotNone(er.assess(days, None, None, None, TODAY), days)
        for days in (15, 40, -1, None):
            self.assertIsNone(er.assess(days, None, None, None, TODAY), days)

    def test_build_risks_skips_rows_outside_window_or_without_date(self):
        rows = [SimpleNamespace(ticker=t) for t in ("IN", "OUT", "NODATE")]
        analyst = {"IN": AnalystInfo(date(2026, 11, 10)), "OUT": AnalystInfo(date(2026, 12, 20)),
                   "NODATE": AnalystInfo()}
        histories = {t: STEADY for t in ("IN", "OUT", "NODATE")}
        risks = er.build_risks(rows, analyst, {}, histories, TODAY, dates_loader=lambda t: [])
        self.assertEqual(list(risks), ["IN"])
        self.assertEqual(risks["IN"]["earnings"], "2026-11-10")
        self.assertEqual(risks["IN"]["note"], "for få regnskaber")

    def test_loader_failure_does_not_crash(self):
        def boom(ticker):
            raise RuntimeError("net væk")
        rows = [SimpleNamespace(ticker="IN")]
        risks = er.build_risks(rows, {"IN": AnalystInfo(date(2026, 11, 10))}, {}, {"IN": STEADY}, TODAY, dates_loader=boom)
        self.assertEqual(risks["IN"]["count"], 0)
        with mock.patch.dict("sys.modules", {"yfinance": None}):          # import fejler
            self.assertEqual(er.load_earnings_dates("X"), [])


class MoveTests(unittest.TestCase):
    def make(self, moves):
        """Historik med 12 uger mellem regnskaber; bevægelsen sker mellem lukkekursen før og efter hver dato."""
        index = pd.bdate_range("2024-01-01", periods=400)
        close = pd.Series(100.0, index=index)
        dates = []
        for n, move in enumerate(moves):
            day = index[40 + n * 40]
            dates.append(day.date())
            close.loc[close.index > day] *= 1 + move / 100       # kursen efter datoen er flyttet
            # lukkekursen på selve dagen ligger lige før springet -> springet sker "dagen efter"
        return pd.DataFrame({"Close": close}), dates

    def test_move_is_close_before_date_to_close_day_after(self):
        index = pd.bdate_range("2026-10-26", "2026-11-03")      # man 26-10 … tirs 03-11 (7 handelsdage)
        history = pd.DataFrame({"Close": pd.Series([100, 100, 100, 104, 108, 90, 90], index=index, dtype=float)})
        self.assertAlmostEqual(er.move_for(history, date(2026, 10, 29)), 8.0)      # 28-10 (100) -> 30-10 (108)
        self.assertAlmostEqual(er.move_for(history, date(2026, 10, 30)), 100 * (90 / 104 - 1))
        self.assertIsNone(er.move_for(history, date(2026, 11, 3)))      # ingen dag efter
        self.assertIsNone(er.move_for(history, date(2026, 10, 20)))     # ingen dag før
        self.assertIsNone(er.move_for(None, date(2026, 10, 29)))

    def test_stats_average_abs_and_share_down(self):
        history, dates = self.make([5, -10, 3, -2, 8, -6])
        moves = er.past_moves(history, dates)
        self.assertEqual(len(moves), 6)
        stats = er.move_stats(moves)
        self.assertEqual(stats["count"], 6)
        self.assertAlmostEqual(stats["down_share_pct"], 50.0)
        self.assertIsNone(stats["note"])
        self.assertEqual([round(m, 6) for m in sorted(moves)], sorted([5, -10, 3, -2, 8, -6]))
        self.assertAlmostEqual(stats["avg_abs_pct"], 34 / 6)

    def test_only_latest_eight(self):
        history, dates = self.make([1] * 9)
        self.assertEqual(len(er.past_moves(history, dates)), 8)

    def test_fewer_than_four_is_too_few(self):
        history, dates = self.make([5, -5, 5])
        stats = er.move_stats(er.past_moves(history, dates))
        self.assertEqual((stats["count"], stats["avg_abs_pct"], stats["down_share_pct"], stats["note"]),
                         (3, None, None, "for få regnskaber"))
        self.assertEqual(er.move_stats([])["note"], "for få regnskaber")
        self.assertIsNone(er.move_stats([1, 2, 3, 4])["note"])

    def test_dates_with_timezone_and_timestamps_are_accepted(self):
        history, dates = self.make([5, -5, 5, -5])
        stamps = [pd.Timestamp(d, tz="America/New_York") for d in dates]
        self.assertEqual(len(er.past_moves(history, stamps)), 4)


class LogTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "log.csv"

    def risk(self, level="Middel", points=1, reasons=("a", "b"), earnings="2026-11-10", close=100.0):
        return {"level": level, "points": points, "reasons": list(reasons), "earnings": earnings, "close": close}

    def test_one_row_per_key_and_overwritten_until_earnings(self):
        er.log_assessments({"AAA": self.risk()}, date(2026, 11, 3), self.path)
        er.log_assessments({"AAA": self.risk("Høj", 2, ("c",), close=105.0), "BBB": self.risk(earnings="2026-11-12")},
                           date(2026, 11, 4), self.path)
        rows = er.read_log(self.path)
        self.assertEqual(len(rows), 2)
        first = next(r for r in rows if r["ticker"] == "AAA")
        self.assertEqual((first["dato"], first["niveau"], first["point"], first["begrundelser"], first["lukkekurs"]),
                         ("2026-11-04", "Høj", "2", "c", "105.0000"))
        er.log_assessments({"AAA": self.risk(earnings="2027-02-01")}, date(2026, 11, 5), self.path)
        self.assertEqual(len(er.read_log(self.path)), 3)          # ny regnskabsdato = ny række
        self.assertEqual(self.path.read_bytes()[:3], b"\xef\xbb\xbf")
        self.assertIn(";", self.path.read_text(encoding="utf-8-sig").splitlines()[0])

    def test_outcome_filled_once_earnings_passed_and_idempotent(self):
        er.log_assessments({"AAA": self.risk(earnings="2026-10-28")}, date(2026, 10, 27), self.path)
        index = pd.bdate_range("2026-10-20", "2026-11-03")
        close = pd.Series(100.0, index=index)
        close.loc[close.index >= "2026-10-29"] = 92.0
        histories = {"AAA": pd.DataFrame({"Close": close})}
        self.assertEqual(er.fill_outcomes(histories, date(2026, 10, 28), self.path), 0)      # ikke passeret endnu
        self.assertEqual(er.fill_outcomes({}, date(2026, 11, 4), self.path), 0)               # ingen kurser
        self.assertEqual(er.fill_outcomes(histories, date(2026, 11, 4), self.path), 1)
        self.assertEqual(er.read_log(self.path)[0]["udfald_pct"], "-8.00")
        before = self.path.read_bytes()
        self.assertEqual(er.fill_outcomes(histories, date(2026, 11, 5), self.path), 0)
        self.assertEqual(self.path.read_bytes(), before)
        # en udfyldt række overskrives ikke af en sen vurdering
        er.log_assessments({"AAA": self.risk("Høj", 3, earnings="2026-10-28")}, date(2026, 11, 5), self.path)
        row = er.read_log(self.path)[0]
        self.assertEqual((row["niveau"], row["udfald_pct"]), ("Middel", "-8.00"))

    def test_missing_log_and_no_risks_write_nothing(self):
        self.assertEqual(er.read_log(self.path), [])
        er.log_assessments({}, TODAY, self.path)
        self.assertFalse(self.path.exists())
        self.assertEqual(er.fill_outcomes({"A": STEADY}, TODAY, self.path), 0)


def weekly_args(earnings):
    channel = SimpleNamespace(score=60.0, score_today=60.0, peg=1.0, asymmetry=4.0, upside_pct={"bear": -5.0})
    info = {"AAA": AnalystInfo(earnings_date=earnings)}
    return dict(tickers=["AAA"], histories={"AAA": STEADY}, benchmark=STEADY, quality_pct={"AAA": 80.0},
                value_pct={"AAA": 50.0}, momentum_pct={"AAA": 50.0}, channels={"AAA": channel}, analyst=info,
                today=TODAY)


class UnknownEarningsTests(unittest.TestCase):
    signal = ("køb 2026-10-30", "grøn", 10.0)

    def rows(self, earnings, positions=None):
        with mock.patch("stockscanner.weekly_list.latest_signal", return_value=self.signal), \
                mock.patch("stockscanner.weekly_list.tpi_states", return_value=pd.DataFrame()), \
                mock.patch("stockscanner.portfolio.exit_check", return_value=[]), \
                mock.patch("stockscanner.portfolio.profit_pct", return_value=None):
            return build_rows(**weekly_args(earnings), positions=positions)

    def test_unknown_date_stays_buy_candidate_with_warning(self):
        (row,) = self.rows(None)
        self.assertEqual(row.action, "KØB-KANDIDAT")
        self.assertIn(UNKNOWN_EARNINGS, row.reasons)
        self.assertIsNone(row.earnings)

    def test_known_date_has_no_warning(self):
        (row,) = self.rows(date(2026, 12, 15))
        self.assertEqual(row.action, "KØB-KANDIDAT")
        self.assertNotIn(UNKNOWN_EARNINGS, row.reasons)

    def test_owned_stock_is_not_changed(self):
        (row,) = self.rows(None, positions={"AAA": SimpleNamespace()})
        self.assertEqual(row.action, "BEHOLD (ejet)")
        self.assertNotIn(UNKNOWN_EARNINGS, row.reasons)

    def test_close_earnings_still_blocks(self):
        (row,) = self.rows(date(2026, 11, 8))
        self.assertEqual(row.action, "hold øje")


class NeverChangesActionTests(unittest.TestCase):
    def test_build_risks_leaves_rows_untouched_and_action_independent_of_risk(self):
        row = WeeklyRow("AAA", "KØB-KANDIDAT", "køb 2026-10-30", None, None, None, 80.0, 50.0, 60.0, 70.0, 1.0,
                        "alle krav opfyldt", earnings="2026-11-10")
        before = row.__dict__.copy()
        risks = er.build_risks([row], {"AAA": AnalystInfo(date(2026, 11, 10), CUT)},
                               {"AAA": [item("negativ")]}, {"AAA": RISING}, TODAY, dates_loader=lambda t: [])
        self.assertEqual(risks["AAA"]["level"], "Høj")
        self.assertEqual(row.__dict__, before)
        self.assertEqual(row.action, "KØB-KANDIDAT")

    def test_payload_adds_earnings_risk_but_keeps_action(self):
        row = WeeklyRow("AAA", "KØB-KANDIDAT", "–", None, None, None, 80.0, 50.0, 60.0, 70.0, 1.0, "alle krav opfyldt")
        trades = pd.DataFrame(columns=["ticker", "koebsdato", "koebskurs", "salgsdato", "salgskurs", "salgsgrund"])
        args = dict(rows=[row], histories={"AAA": STEADY}, currencies={}, regions={}, atrs={}, research=[],
                    breadth={}, benchmark="RSP", factors=None, scores=None, regional=None, trades=trades,
                    last_prices={}, changes=[])
        plain = playbook.build_payload(**args)
        self.assertNotIn("earnings_risk", plain["stocks"]["AAA"])
        risk = {"level": "Høj", "points": 2, "reasons": ["x"], "avg_abs_pct": 8.123, "down_share_pct": 62.5,
                "count": 8, "note": None}
        with_risk = playbook.build_payload(**args, earnings_risk={"AAA": risk, "ZZZ": risk})
        entry = with_risk["stocks"]["AAA"]
        json.dumps(with_risk, allow_nan=False)
        self.assertEqual(entry["action"], "KØB-KANDIDAT")
        self.assertEqual(entry["earnings_risk"], {"level": "Høj", "points": 2, "reasons": ["x"], "avg_move_pct": 8.1,
                                                  "down_share_pct": 62.0, "count": 8, "note": None})
        self.assertNotIn("ZZZ", with_risk["stocks"])
        too_few = playbook.earnings_risk_entry({"level": "Lav", "points": 0, "reasons": [], "count": 2,
                                                "avg_abs_pct": None, "down_share_pct": None, "note": "for få regnskaber"})
        self.assertIsNone(too_few["avg_move_pct"])


if __name__ == "__main__":
    unittest.main()
