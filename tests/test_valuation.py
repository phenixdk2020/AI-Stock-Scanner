"""Offline tests af værdikanalen med håndlavede tal."""
import unittest
from datetime import date

import numpy as np
import pandas as pd

from stockscanner.valuation import (
    ValuationInputs, base_pe, eps_path, trailing_pe_history, value_channel,
)


def inputs(price=100.0, pe=20.0, eps=(4.0, 5.0, 6.0), as_of=date(2026, 7, 1), target=None, years=4):
    index = pd.bdate_range(end=pd.Timestamp(as_of), periods=252 * years)
    return ValuationInputs(
        ticker="TEST", price=price, as_of=as_of, last_fiscal_year_end=date(2025, 12, 31),
        eps_last=eps[0], eps_current_year=eps[1], eps_next_year=eps[2],
        pe_history=pd.Series(pe, index=index), target_price=target)


class EpsPathTests(unittest.TestCase):
    def test_interpolates_between_knots_and_extrapolates_growth(self):
        data = inputs(eps=(4.0, 5.0, 6.0))
        self.assertEqual(eps_path(data, 0), 4.0)
        self.assertEqual(eps_path(data, 1.5), 5.5)
        self.assertAlmostEqual(eps_path(data, 3), 6.0 * 1.2)

    def test_extrapolated_growth_is_capped(self):
        self.assertAlmostEqual(eps_path(inputs(eps=(1.0, 1.0, 3.0)), 3), 3.0 * 1.5)

    def test_missing_estimate_gives_none(self):
        self.assertIsNone(eps_path(inputs(eps=(4.0, None, 6.0)), 1))


class ChannelTests(unittest.TestCase):
    def test_minmax_rule_uses_lowest_and_highest_pe_with_midpoint_base(self):
        # 4 års historik med P/E 20 og nuværende P/E 100/4 = 25 → bear 20, bull 25, base 22,5
        channel = value_channel(inputs(price=100, pe=20, eps=(4, 5, 6)))
        self.assertAlmostEqual(channel.pe_bear, 20)
        self.assertAlmostEqual(channel.pe_bull, 25)
        self.assertAlmostEqual(channel.pe_base, 22.5)

    def test_minmax_falls_back_to_fixed_band_without_spread(self):
        channel = value_channel(inputs(price=80, pe=20, eps=(4, 5, 6)))  # nuværende P/E = 20 = historikken
        self.assertAlmostEqual(channel.pe_bear, 16)
        self.assertAlmostEqual(channel.pe_bull, 24)

    def test_band_and_linear_upside(self):
        channel = value_channel(inputs(price=100, pe=20, eps=(4, 5, 6)), horizon=0.5, band_rule="fixed")
        self.assertAlmostEqual(channel.pe_bear, 16)
        self.assertAlmostEqual(channel.pe_bull, 24)
        eps_h = eps_path(inputs(), (date(2026, 7, 1) - date(2025, 12, 31)).days / 365.25 + 0.5)
        self.assertAlmostEqual(channel.scenario_prices["base"], eps_h * 20)
        # kun P/E varierer: forholdet mellem scenariekurserne er forholdet mellem P/E (som Vestas-tjekket)
        ratio = (1 + channel.upside_pct["bull"] / 100) / (1 + channel.upside_pct["base"] / 100)
        self.assertAlmostEqual(ratio, 24 / 20)

    def test_score_is_100_on_bear_line_and_0_on_bull_line(self):
        fixed = lambda price: value_channel(inputs(price=price), horizon=1, band_rule="fixed")
        base = fixed(100.0)
        bear_price, bull_price = base.scenario_prices["bear"], base.scenario_prices["bull"]
        self.assertAlmostEqual(fixed(bear_price).score, 100)
        self.assertAlmostEqual(fixed(bull_price).score, 0)
        self.assertGreater(fixed(bear_price * 0.8).score, 100)  # ikke afkortet
        self.assertLess(fixed(bull_price * 1.5).score, 0)

    def test_override_like_user_drawn_channel(self):
        channel = value_channel(inputs(), pe_override=(10, 15, 30))
        self.assertEqual((channel.pe_bear, channel.pe_base, channel.pe_bull), (10, 15, 30))

    def test_asymmetry_peg_and_implied_pe(self):
        channel = value_channel(inputs(price=120, eps=(4, 5, 6), target=150))
        self.assertAlmostEqual(channel.implied_pe, 25)
        self.assertAlmostEqual(channel.peg, (120 / 6) / 20)
        if channel.upside_pct["bear"] < 0:
            self.assertAlmostEqual(channel.asymmetry, channel.upside_pct["base"] / -channel.upside_pct["bear"])

    def test_negative_or_missing_estimates_give_no_channel(self):
        channel = value_channel(inputs(eps=(4, -1, -2)))
        self.assertIsNone(channel.score)
        self.assertIn("Mangler positive EPS-estimater", channel.notes)
        self.assertIsNone(channel.peg)

    def test_inconsistent_estimates_are_rejected(self):
        channel = value_channel(inputs(eps=(1.37, 20.73, 23.63)))  # som SOBI hos yfinance
        self.assertIsNone(channel.score)
        self.assertIsNone(channel.peg)
        self.assertTrue(any("datafejl" in note for note in channel.notes))

    def test_short_history_is_noted(self):
        self.assertIn("Under 3 års P/E-historik", value_channel(inputs(years=2)).notes)


class PeHistoryTests(unittest.TestCase):
    def test_eps_known_only_after_report_lag(self):
        prices = pd.Series(100.0, index=pd.bdate_range("2025-01-01", "2025-06-30"))
        eps = pd.Series([5.0, 10.0], index=pd.to_datetime(["2023-12-31", "2024-12-31"]))
        pe = trailing_pe_history(prices, eps, lag_days=60)
        self.assertEqual(pe.loc["2025-02-03"], 20.0)   # 2024-EPS endnu ukendt
        self.assertEqual(pe.loc["2025-03-03"], 10.0)   # kendt efter 60 dage

    def test_negative_eps_days_are_dropped(self):
        prices = pd.Series(100.0, index=pd.bdate_range("2025-03-01", "2025-04-30"))
        eps = pd.Series([-2.0], index=pd.to_datetime(["2024-12-31"]))
        self.assertTrue(trailing_pe_history(prices, eps).empty)

    def test_base_pe_is_median_of_period_averages_of_yearly_medians(self):
        index = pd.bdate_range("2020-01-01", "2026-06-30")
        values = {2020: 10.0, 2021: 12.0, 2022: 14.0, 2023: 20.0, 2024: 22.0, 2025: 24.0, 2026: 26.0}
        series = pd.Series([values[d.year] for d in index], index=index)
        three = np.mean([22, 24, 26])               # 2024–2026
        five = np.mean([14, 20, 22, 24, 26])        # 2022–2026
        self.assertAlmostEqual(base_pe(series, date(2026, 6, 30)), np.median([three, five]))  # ingen 10-års data

    def test_base_pe_drops_distorted_years(self):
        index = pd.bdate_range("2023-01-01", "2026-06-30")
        values = {2023: 20.0, 2024: 270.0, 2025: 30.0, 2026: 25.0}   # 2024 som Vestas
        series = pd.Series([values[d.year] for d in index], index=index)
        self.assertAlmostEqual(base_pe(series, date(2026, 6, 30)), np.mean([30, 25]))


if __name__ == "__main__":
    unittest.main()
