import unittest

from ai_readiness import config as config_module
from ai_readiness.checks import ai_monitoring
from ai_readiness.checks.base import Context


class NullPercentageGql:
    """Simulates the real NRQL behaviour that no mock fixture exercised:
    percentage() over zero events returns null, not 0. An account with no
    AI telemetry yet -- the commonest case in a first pitch -- should hit
    this on every token_visibility query."""

    def __call__(self, query, variables=None, fixture_key=None):
        if fixture_key and fixture_key.endswith("token_visibility"):
            return {"actor": {"account": {"nrql": {"results": [{"percentage": None}]}}}}
        return {"actor": {"account": {"nrql": {"results": [{"count": 0}]}}}}


def _ctx():
    return Context(gql=NullPercentageGql(), account_id=1, lookback_days=30, config=config_module.THRESHOLDS)


class TestAiMonitoringNullPercentage(unittest.TestCase):
    def test_run_does_not_raise_on_null_percentage(self):
        result = ai_monitoring.run(_ctx())  # would previously raise TypeError formatting None with :.0f
        self.assertEqual(result.score, 0)

    def test_null_percentage_reports_as_zero_not_unknown(self):
        result = ai_monitoring.run(_ctx())
        self.assertIn("0% with token data", result.evidence)
        self.assertEqual(result.raw_metrics["llm_token_visibility_pct"], 0)
        self.assertEqual(result.raw_metrics["genai_token_visibility_pct"], 0)


if __name__ == "__main__":
    unittest.main()
