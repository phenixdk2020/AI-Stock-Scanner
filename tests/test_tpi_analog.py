import unittest

import numpy as np
import pandas as pd

from stockscanner.tpi_analog import analog_scores_weekly, analog_states, features, state_returns


def _weekly(n=400, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2010-01-01", periods=n, freq="W-FRI")
    return pd.Series(100 * np.exp(np.cumsum(rng.normal(0.002, 0.03, n))), index=idx)


def _daily(n_weeks=500, seed=1):
    w = _weekly(n_weeks, seed)
    idx = pd.bdate_range(w.index[0] - pd.Timedelta(days=4), w.index[-1])
    close = w.reindex(idx).ffill().bfill()
    return pd.DataFrame({"Open": close * 0.999, "Close": close}, index=idx)


class AnalogTests(unittest.TestCase):
    def test_ingen_fremtid(self):
        w = _weekly()
        cut = 300
        w2 = w.copy()
        w2.iloc[cut + 1:] = w2.iloc[cut + 1:] * 3.7 + 50
        a, b = analog_scores_weekly(w), analog_scores_weekly(w2)
        pd.testing.assert_frame_equal(a.iloc[:cut + 1], b.iloc[:cut + 1])
        self.assertTrue(a.iloc[:cut + 1].notna().any().any())

    def test_sidste_uge_paavirker_kun_sig_selv(self):
        w = _weekly(300)
        w2 = w.copy()
        w2.iloc[-1] *= 5
        a, b = analog_scores_weekly(w), analog_scores_weekly(w2)
        pd.testing.assert_frame_equal(a.iloc[:-1], b.iloc[:-1])

    def test_features_kun_fortid(self):
        w = _weekly(120)
        w2 = w.copy()
        w2.iloc[100:] *= 2
        pd.testing.assert_frame_equal(features(w).iloc[:100], features(w2).iloc[:100])

    def test_periodisk_kurve_giver_endelig_score(self):
        idx = pd.date_range("2005-01-07", periods=500, freq="W-FRI")
        w = pd.Series(100 + 10 * np.sin(np.arange(500) * 2 * np.pi / 52) + np.arange(500) * 0.05, index=idx)
        s = analog_scores_weekly(w)["score_20d"].dropna()
        self.assertGreater(len(s), 100)
        self.assertTrue(np.isfinite(s).all())

    def test_ekstreme_sidste_uger_paavirker_kun_sig_selv(self):
        w = _weekly(300)
        w2 = w.copy()
        w2.iloc[-3:] *= 10
        a, b = analog_scores_weekly(w), analog_scores_weekly(w2)
        pd.testing.assert_frame_equal(a.iloc[:-3], b.iloc[:-3])

    def test_tilstande_og_afkast(self):
        d = _daily(500)
        st = analog_states(d)
        self.assertTrue(set(st["state"]) <= {"oversolgt", "overkøbt", "neutral"})
        self.assertTrue(st["short_pct"].between(0, 100).all())
        r = state_returns(st, d)
        self.assertIn("end_130d", r.columns)
        self.assertTrue((r["week"] < r["end_20d"].fillna(pd.Timestamp.max)).all())


if __name__ == "__main__":
    unittest.main()
