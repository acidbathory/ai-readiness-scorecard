import json
import unittest

from ai_readiness import config as config_module
from ai_readiness.checks import ALL_CHECKS
from ai_readiness.checks.base import Context, run_check
from ai_readiness.checks.security_vuln import DIMENSION as SECURITY_DIMENSION
from ai_readiness.checks import security_vuln
from ai_readiness.checks.ai_quality_feedback import DIMENSION as FEEDBACK_DIMENSION
from ai_readiness.checks import ai_quality_feedback
from ai_readiness.nerdgraph import NerdGraphError, make_mock_client
from ai_readiness.report import render_json
from ai_readiness.scoring import aggregate

EXPECTED_SCORES = {
    "none": {c.DIMENSION: 0 for c in ALL_CHECKS},
    "mature": {c.DIMENSION: 3 for c in ALL_CHECKS},
    "partial": {
        "apm_coverage": 2,
        "infra_gpu": 2,
        "ai_monitoring": 1,
        "ai_agent_tracing": 2,
        "ai_quality_feedback": 1,
        "human_approval_gates": 2,
        "model_vendor_diversity": 2,
        "security_vuln": 1,
        "workflow_automation": 2,
        "autopilot": 2,
        "alerting_anomaly": 2,
        "dashboards_logs": 2,
        "ai_cost_governance": 2,
        "ai_change_tracking": 1,
    },
}

# Displayed on a 0-10 scale (aggregate() scales internal 0-3 tier averages by
# 10/3): none stays 0.0, mature's raw 3.0 -> 10.0. partial's 5.8 is a golden
# value observed by running the fixtures (14 dimensions across 2 lenses of
# uneven size makes hand-deriving the exact roll-up error-prone) -- it
# happens to be unchanged from the 10-dimension version by coincidence.
EXPECTED_OVERALL = {"none": 0.0, "partial": 5.8, "mature": 10.0}


def run_all(scenario):
    gql = make_mock_client(scenario)
    ctx = Context(gql=gql, account_id=123, lookback_days=30, config=config_module.THRESHOLDS)
    return [run_check(c, ctx) for c in ALL_CHECKS]


class TestScenarios(unittest.TestCase):
    def test_all_dimensions_present_and_no_errors(self):
        for scenario in ("none", "partial", "mature"):
            with self.subTest(scenario=scenario):
                results = run_all(scenario)
                dims = {r.dimension for r in results}
                self.assertEqual(dims, {c.DIMENSION for c in ALL_CHECKS})
                for r in results:
                    self.assertIsNone(r.error, f"{scenario}/{r.dimension}: {r.error}")
                    self.assertTrue(r.remediation, f"{scenario}/{r.dimension}: missing remediation text")

    def test_expected_scores_per_scenario(self):
        for scenario, expected in EXPECTED_SCORES.items():
            with self.subTest(scenario=scenario):
                results = run_all(scenario)
                actual = {r.dimension: r.score for r in results}
                self.assertEqual(actual, expected)

    def test_aggregate_matches_expected_overall(self):
        for scenario, expected_overall in EXPECTED_OVERALL.items():
            with self.subTest(scenario=scenario):
                results = run_all(scenario)
                agg = aggregate(results)
                self.assertEqual(agg["overall_score"], expected_overall)

    def test_json_round_trips_with_required_keys(self):
        results = run_all("partial")
        agg = aggregate(results)
        meta = {"account_id": 123, "region": "us", "lookback_days": 30, "mock": True}
        payload = json.loads(render_json(results, agg, meta))
        self.assertIn("dimensions", payload)
        self.assertIn("lens_scores", payload)
        self.assertIn("overall_score", payload)
        required_keys = {"dimension", "label", "lens", "confidence", "score", "tier", "evidence", "raw_metrics", "error", "remediation"}
        for entry in payload["dimensions"]:
            self.assertEqual(required_keys, set(entry.keys()))


class TestSecurityVulnBothQueriesFail(unittest.TestCase):
    """Neither reference repo has a confirmed security/vulnerability query
    shape -- this exercises the honest-Unknown path when both candidate
    queries fail, distinct from the "query succeeds with zero" Absent path
    covered by the 'none' scenario above."""

    def test_unknown_when_both_candidates_error(self):
        def gql(query, variables=None, fixture_key=None):
            raise NerdGraphError("simulated schema mismatch")

        ctx = Context(gql=gql, account_id=123, lookback_days=30, config=config_module.THRESHOLDS)
        result = run_check(security_vuln, ctx)
        self.assertIsNone(result.score)
        self.assertEqual(result.tier, config_module.UNKNOWN_TIER_LABEL)
        self.assertEqual(result.dimension, SECURITY_DIMENSION)
        self.assertIsNotNone(result.error)


class TestAiQualityFeedbackQueryFails(unittest.TestCase):
    """LlmFeedbackMessage has never been confirmed populated on any account
    we've tested -- this exercises the honest-Unknown path when the query
    itself fails, distinct from the "query succeeds with zero" Absent path
    covered by the 'none' scenario above."""

    def test_unknown_when_query_errors(self):
        def gql(query, variables=None, fixture_key=None):
            raise NerdGraphError("simulated: LlmFeedbackMessage not recognized")

        ctx = Context(gql=gql, account_id=123, lookback_days=30, config=config_module.THRESHOLDS)
        result = run_check(ai_quality_feedback, ctx)
        self.assertIsNone(result.score)
        self.assertEqual(result.tier, config_module.UNKNOWN_TIER_LABEL)
        self.assertEqual(result.dimension, FEEDBACK_DIMENSION)
        self.assertIsNotNone(result.error)


if __name__ == "__main__":
    unittest.main()
