"""Offline tests af kvalitet som percentil."""
import unittest

from stockscanner.quality import MetricResult, QualityResult
from stockscanner.quality_rank import quality_percentiles


def result(ticker, roce, debt, missing=False):
    metrics = [
        MetricResult("roce", "ROCE", "Lønsomhed", None if missing else roce, None if missing else roce * 100, ""),
        MetricResult("net_debt_ebitda", "Nettogæld/EBITDA", "Balance", debt, 100 - debt * 20, ""),
    ]
    return QualityResult(ticker, None, "", {}, metrics, [], 1.0, [], "DKK", "", False)


class QualityRankTests(unittest.TestCase):
    def test_best_on_all_metrics_ranks_highest_and_direction_respected(self):
        ranked = quality_percentiles([result("A", 0.30, 0.5), result("B", 0.10, 3.0), result("C", 0.20, 1.5)])
        self.assertEqual(max(ranked, key=ranked.get), "A")  # høj ROCE og lav gæld
        self.assertEqual(min(ranked, key=ranked.get), "B")
        self.assertAlmostEqual(ranked["A"], 100.0)

    def test_too_few_metrics_gives_no_score(self):
        ranked = quality_percentiles([result("A", 0.3, 0.5), result("B", 0.1, 3.0), result("C", 0.2, 1.5),
                                      result("D", 0.2, 1.0, missing=True)], min_share=1.0)
        self.assertNotIn("D", ranked)

    def test_empty_input(self):
        self.assertEqual(quality_percentiles([]), {})


if __name__ == "__main__":
    unittest.main()
