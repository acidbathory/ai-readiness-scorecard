import unittest

from ai_readiness.checks.base import CheckResult
from ai_readiness.scoring import aggregate, combine_tiers, tier_from_count


class TestTierFromCount(unittest.TestCase):
    THRESHOLDS = {1: 1, 2: 5, 3: 20}

    def test_below_first_threshold(self):
        self.assertEqual(tier_from_count(0, self.THRESHOLDS), 0)

    def test_none_count(self):
        self.assertEqual(tier_from_count(None, self.THRESHOLDS), 0)

    def test_exactly_at_threshold(self):
        self.assertEqual(tier_from_count(1, self.THRESHOLDS), 1)
        self.assertEqual(tier_from_count(5, self.THRESHOLDS), 2)
        self.assertEqual(tier_from_count(20, self.THRESHOLDS), 3)

    def test_one_below_threshold(self):
        self.assertEqual(tier_from_count(4, self.THRESHOLDS), 1)
        self.assertEqual(tier_from_count(19, self.THRESHOLDS), 2)

    def test_above_top_threshold(self):
        self.assertEqual(tier_from_count(1000, self.THRESHOLDS), 3)


class TestCombineTiers(unittest.TestCase):
    def test_min(self):
        self.assertEqual(combine_tiers(1, 3, method="min"), 1)

    def test_max(self):
        self.assertEqual(combine_tiers(1, 3, method="max"), 3)

    def test_ignores_none(self):
        self.assertEqual(combine_tiers(None, 2, method="min"), 2)

    def test_all_none(self):
        self.assertEqual(combine_tiers(None, None), 0)


class TestAggregate(unittest.TestCase):
    def _result(self, dimension, lens, score):
        return CheckResult(
            dimension=dimension, label=dimension, lens=lens, confidence="high",
            score=score, tier="x", evidence="",
        )

    def test_averages_per_lens_and_overall(self):
        results = [
            self._result("a", "observability_for_ai", 1),
            self._result("b", "observability_for_ai", 3),
            self._result("c", "ai_for_observability", 2),
        ]
        agg = aggregate(results)
        self.assertEqual(agg["lens_scores"]["observability_for_ai"], 2.0)
        self.assertEqual(agg["lens_scores"]["ai_for_observability"], 2.0)
        self.assertEqual(agg["overall_score"], 2.0)

    def test_failed_check_excluded_from_average(self):
        results = [
            self._result("a", "observability_for_ai", 3),
            self._result("b", "observability_for_ai", None),
        ]
        agg = aggregate(results)
        self.assertEqual(agg["lens_scores"]["observability_for_ai"], 3.0)

    def test_empty_results(self):
        agg = aggregate([])
        self.assertEqual(agg["lens_scores"], {})
        self.assertEqual(agg["overall_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
