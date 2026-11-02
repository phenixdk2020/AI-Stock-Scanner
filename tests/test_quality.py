"""Offline-tests af kvalitetsmodellen med syntetiske regnskabstal."""
import unittest

from stockscanner.fundamentals import FIELDS, FiscalYear, FundamentalData
from stockscanner.quality import (
    METRIC_PILLAR, PILLAR_WEIGHTS, THRESHOLDS, altman_z, interpolate, is_financial, label_for, piotroski,
    score_quality,
)


def year(date="2024-12-31", **values) -> FiscalYear:
    full = {name: None for name in FIELDS}
    full.update(values)
    return FiscalYear(end_date=date, values=full)


def company(years, sector="Technology", industry="Software", market_cap=None) -> FundamentalData:
    return FundamentalData(
        ticker="TEST", sector=sector, industry=industry, currency="USD",
        reporting_currency="USD", market_cap=market_cap, years=years,
    )


def metric(result, key):
    return next(m for m in result.metrics if m.key == key)


# Komplet, sund virksomhed med kendte tal (nyeste år).
GOOD = dict(
    revenue=1000.0, gross_profit=500.0, operating_income=200.0, ebit=200.0, ebitda=260.0,
    net_income=150.0, interest_expense=10.0, pretax_income=190.0, tax_provision=38.0,
    total_assets=1500.0, current_assets=600.0, current_liabilities=300.0, total_liabilities=700.0,
    stockholders_equity=600.0, total_debt=300.0, cash=100.0, retained_earnings=400.0, shares=100.0,
    operating_cash_flow=230.0, capital_expenditure=-50.0, free_cash_flow=180.0,
)


def good_years():
    older = dict(GOOD, revenue=900.0, operating_income=170.0, ebit=170.0, net_income=120.0)
    oldest = dict(GOOD, revenue=820.0, operating_income=150.0, ebit=150.0, net_income=100.0)
    return [year("2024-12-31", **GOOD), year("2023-12-31", **older), year("2022-12-31", **oldest)]


# Tre regnskabsår (nyeste Y0, forrige Y1, ældste Y2) hvor alle 9 Piotroski-tests består.
PIO_Y2 = dict(net_income=30.0, total_assets=1000.0, long_term_debt=400.0, revenue=700.0)
PIO_Y1 = dict(
    net_income=50.0, total_assets=1000.0, long_term_debt=380.0, current_assets=300.0,
    current_liabilities=250.0, shares=110.0, gross_profit=300.0, revenue=800.0,
)
PIO_Y0 = dict(
    net_income=100.0, total_assets=1100.0, operating_cash_flow=150.0, long_term_debt=300.0,
    current_assets=400.0, current_liabilities=250.0, shares=100.0, gross_profit=400.0, revenue=900.0,
)
SAME = ["Ordinary Shares Number", "Ordinary Shares Number", None]


class ModelStructureTests(unittest.TestCase):
    def test_weights_sum_to_100_and_pillars_known(self):
        self.assertEqual(sum(PILLAR_WEIGHTS.values()), 100)
        self.assertTrue(set(METRIC_PILLAR.values()) <= set(PILLAR_WEIGHTS))
        self.assertTrue(set(THRESHOLDS) <= set(METRIC_PILLAR))

    def test_interpolation_and_clamping(self):
        pts = THRESHOLDS["roic"]
        self.assertEqual(interpolate(pts, -0.1), 0)
        self.assertEqual(interpolate(pts, 0.10), 50)
        self.assertAlmostEqual(interpolate(pts, 0.175), 65)
        self.assertEqual(interpolate(pts, 0.25), 80)
        self.assertEqual(interpolate(pts, 0.5), 100)
        self.assertEqual(interpolate(THRESHOLDS["net_debt_ebitda"], -3), 100)  # nettokasse

    def test_label_boundaries(self):
        self.assertEqual(
            [label_for(v) for v in (80, 79.9, 60, 59.9, 40, 39.9)],
            ["Stærk", "God", "God", "Middel", "Middel", "Svag"],
        )


class MetricTests(unittest.TestCase):
    def test_roic_roce_margins_on_known_numbers(self):
        result = score_quality(company(good_years(), market_cap=3000.0))
        # skattesats 38/190 = 20 %; NOPAT 160; investeret kapital 300+600-100 = 800 => 20 %
        roic = metric(result, "roic")
        self.assertAlmostEqual(roic.value, 0.20, places=6)
        self.assertAlmostEqual(roic.score, 70.0, places=1)  # 10 %->50, 25 %->80: 20 % => 70
        self.assertAlmostEqual(metric(result, "roce").value, 200 / 1200, places=6)
        self.assertAlmostEqual(metric(result, "roe").value, 0.25, places=6)
        self.assertAlmostEqual(metric(result, "roa").value, 0.10, places=6)
        self.assertAlmostEqual(metric(result, "gross_margin").value, 0.5, places=6)
        self.assertAlmostEqual(metric(result, "operating_margin").value, 0.2, places=6)
        self.assertAlmostEqual(metric(result, "fcf_margin").value, 0.18, places=6)
        self.assertAlmostEqual(metric(result, "cash_conversion").value, 1.2, places=6)
        self.assertAlmostEqual(metric(result, "current_ratio").value, 2.0, places=6)
        self.assertAlmostEqual(metric(result, "net_debt_ebitda").value, 200 / 260, places=6)
        self.assertAlmostEqual(metric(result, "interest_coverage").value, 20.0, places=6)

    def test_default_tax_rate_when_tax_missing(self):
        result = score_quality(company([year(**dict(GOOD, tax_provision=None))]))
        self.assertAlmostEqual(metric(result, "roic").value, 200 * 0.78 / 800, places=6)

    def test_stability_and_cagr_need_three_years(self):
        two = score_quality(company(good_years()[:2]))
        self.assertIsNone(metric(two, "margin_stability").value)
        self.assertIsNone(metric(two, "revenue_cagr").value)
        three = score_quality(company(good_years()))
        elapsed = 731 / 365.25  # 2022-12-31 -> 2024-12-31 inkl. skudår
        self.assertAlmostEqual(metric(three, "revenue_cagr").value, (1000 / 820) ** (1 / elapsed) - 1, places=6)
        self.assertIsNotNone(metric(three, "margin_stability").value)

    def test_cagr_uses_elapsed_time_with_gap_years(self):
        years = [
            year("2024-12-31", **dict(GOOD, revenue=1000.0)),
            year("2022-12-31", **dict(GOOD, revenue=900.0)),
            year("2020-12-31", **dict(GOOD, revenue=820.0)),
        ]
        result = score_quality(company(years))
        self.assertAlmostEqual(metric(result, "revenue_cagr").value, (1000 / 820) ** 0.25 - 1, places=6)

    def test_missing_inputs_give_none_and_are_listed(self):
        result = score_quality(company([year(**dict(GOOD, total_debt=None))]))
        self.assertIsNone(metric(result, "roic").value)
        self.assertIn("ROIC", result.missing)
        self.assertIn("total_debt", metric(result, "roic").reason)

    def test_piotroski_all_nine_pass(self):
        points, computed, passed, not_run = piotroski([PIO_Y0, PIO_Y1, PIO_Y2], SAME)
        self.assertEqual((points, computed, not_run), (9, 9, []))

    def test_piotroski_expected_seven_with_two_failures(self):
        y0 = dict(PIO_Y0, shares=120.0, gross_profit=270.0)  # nye aktier + lavere bruttomargin
        points, computed, passed, _ = piotroski([y0, PIO_Y1, PIO_Y2], SAME)
        self.assertEqual((points, computed), (7, 9))
        self.assertNotIn("Ingen nye aktier", passed)
        self.assertNotIn("Bruttomargin steget", passed)

    def test_piotroski_uses_beginning_assets_for_roa(self):
        # ROA-ændring skal bruge startaktiver: Y0 100/1000 = 10 %, Y1 50/1000 = 5 %.
        # Med slutaktiver (1100 mod 1000) ville ROA stadig stige, så vælg tal der skelner:
        y0 = dict(PIO_Y0, net_income=52.0, total_assets=2000.0)
        # start: 52/1000 = 5,2 % > 5 % (bestået); slut ville give 2,6 % < 5 % (dumpet)
        points, computed, passed, _ = piotroski([y0, PIO_Y1, PIO_Y2], SAME)
        self.assertIn("ROA steget", passed)

    def test_piotroski_two_years_leaves_three_year_tests_not_computable(self):
        points, computed, passed, not_run = piotroski([PIO_Y0, PIO_Y1], SAME)
        for name in ("ROA steget", "Langfristet gæld/gns. aktiver faldet", "Aktivomsætning steget"):
            self.assertIn(name, not_run)
        self.assertEqual(computed, 6)
        self.assertEqual(points, 6)

    def test_piotroski_share_test_needs_same_source_label(self):
        labels = ["Ordinary Shares Number", "Share Issued", None]
        points, computed, passed, not_run = piotroski([PIO_Y0, PIO_Y1, PIO_Y2], labels)
        self.assertIn("Ingen nye aktier", not_run)
        self.assertEqual(computed, 8)

    def test_piotroski_reports_computable_checks(self):
        y0 = dict(net_income=10.0, operating_cash_flow=20.0)
        y1 = dict(total_assets=100.0)
        points, computed, _, not_run = piotroski([y0, y1])
        self.assertEqual((points, computed), (3, 3))  # ROA>0, OCF>0, OCF>resultat
        self.assertEqual(len(not_run), 6)
        full = [
            year("2024-12-31", **PIO_Y0), year("2023-12-31", **PIO_Y1), year("2022-12-31", **PIO_Y2),
        ]
        for item in full:
            item.share_label = "Ordinary Shares Number"
        result = score_quality(company(full))
        self.assertIn("9 af 9 beregnelige", metric(result, "piotroski").reason)
        self.assertEqual(metric(result, "piotroski").score, 100.0)

    def test_altman_known_numbers(self):
        values = dict(
            total_assets=1000.0, current_assets=400.0, current_liabilities=200.0,
            retained_earnings=300.0, ebit=150.0, total_liabilities=500.0, revenue=900.0,
        )
        # 0,24 + 0,42 + 0,495 + 1,8 + 0,9 = 3,855
        self.assertAlmostEqual(altman_z(values, 1500.0), 3.855, places=6)
        self.assertIsNone(altman_z(values, None))

    def test_altman_skipped_when_currencies_differ(self):
        data = company(good_years(), market_cap=3000.0)
        data.currency, data.reporting_currency = "DKK", "USD"
        result = score_quality(data)
        self.assertIsNone(metric(result, "altman_z").value)
        self.assertIn("ikke sammenlignelige", metric(result, "altman_z").reason)


class AggregationTests(unittest.TestCase):
    def test_full_score_label_and_pillars(self):
        result = score_quality(company(good_years(), market_cap=3000.0))
        self.assertIsNotNone(result.total)
        self.assertGreaterEqual(result.total, 80)
        self.assertEqual(result.label, "Stærk")
        self.assertEqual(set(result.pillars), set(PILLAR_WEIGHTS))
        self.assertEqual(result.coverage, 1.0)
        self.assertEqual(result.data_years[0], "2024-12-31")

    def test_total_is_weighted_mean_of_pillars(self):
        result = score_quality(company(good_years(), market_cap=3000.0))
        expected = sum(PILLAR_WEIGHTS[p] * s for p, s in result.pillars.items()) / 100
        self.assertAlmostEqual(result.total, expected, delta=0.06)

    def test_finance_sector_skips_metrics(self):
        bank = dict(
            revenue=1000.0, operating_income=300.0, net_income=200.0, total_assets=20000.0,
            stockholders_equity=1500.0, operating_cash_flow=250.0, free_cash_flow=240.0, shares=100.0,
        )
        years = [
            year("2024-12-31", **bank), year("2023-12-31", **dict(bank, net_income=180.0)),
            year("2022-12-31", **dict(bank, revenue=900.0)),
        ]
        result = score_quality(company(years, sector="Financial Services", industry="Banks - Diversified"))
        self.assertTrue(result.is_financial)
        self.assertEqual(result.model_note, "begrænset (finans)")
        for key in ("roic", "roce", "gross_margin", "current_ratio", "net_debt_ebitda", "altman_z",
                    "fcf_margin", "cash_conversion"):
            item = metric(result, key)
            self.assertFalse(item.applicable)
            self.assertIsNone(item.value)
            self.assertNotIn(item.label, result.missing)
        self.assertIsNotNone(metric(result, "roe").score)
        self.assertIsNotNone(result.total)
        self.assertIsNone(result.pillars["Cashflow"])  # søjlen udgår af vægtningen
        self.assertEqual(result.coverage, 1.0)
        used = {p: v for p, v in result.pillars.items() if v is not None}
        expected = sum(PILLAR_WEIGHTS[p] * v for p, v in used.items()) / sum(PILLAR_WEIGHTS[p] for p in used)
        self.assertAlmostEqual(result.total, expected, delta=0.06)

    def test_visa_like_credit_services_gets_full_model(self):
        result = score_quality(company(
            good_years(), sector="Financial Services", industry="Credit Services", market_cap=3000.0,
        ))
        self.assertFalse(result.is_financial)
        self.assertNotEqual(result.model_note, "begrænset (finans)")
        self.assertTrue(metric(result, "roic").applicable)
        self.assertIsNotNone(metric(result, "fcf_margin").value)

    def test_finance_industry_classification(self):
        for industry in ("Banks - Diversified", "Insurance - Life", "Capital Markets", "Asset Management",
                         "Mortgage Finance", "Financial Conglomerates"):
            self.assertTrue(is_financial("Financial Services", industry), industry)
        for industry in ("Credit Services", "Insurance Brokers", "Software", "", None):
            self.assertFalse(is_financial("Financial Services", industry), industry)

    def test_insurance_industry_counts_as_financial(self):
        result = score_quality(company([year(**GOOD)], sector="Other", industry="Insurance - Life"))
        self.assertTrue(result.is_financial)

    def test_low_coverage_gives_no_total(self):
        sparse = year(revenue=1000.0, operating_income=100.0, net_income=50.0, total_assets=800.0)
        result = score_quality(company([sparse]))
        self.assertLess(result.coverage, 0.6)
        self.assertIsNone(result.total)
        self.assertEqual(result.label, "Utilstrækkelige data")
        self.assertTrue(result.missing)


if __name__ == "__main__":
    unittest.main()
