import unittest

from ai_readiness import config as config_module
from ai_readiness.checks import ALL_CHECKS
from ai_readiness.checks.base import Context, run_check
from ai_readiness.nerdgraph import make_mock_client
from ai_readiness.report import _escape, render_html
from ai_readiness.scoring import aggregate


def run_partial():
    gql = make_mock_client("partial")
    ctx = Context(gql=gql, account_id=123, lookback_days=30, config=config_module.THRESHOLDS)
    return [run_check(c, ctx) for c in ALL_CHECKS]


class TestRenderHtml(unittest.TestCase):
    def setUp(self):
        self.results = run_partial()
        self.agg = aggregate(self.results)
        self.meta = {
            "account_id": 123,
            "region": "us",
            "lookback_days": 30,
            "mock": True,
            "generated_at": "2026-08-20T12:00:00",
        }
        self.html = render_html(self.results, self.agg, self.meta)

    def test_is_a_full_html_document(self):
        self.assertIn("<!DOCTYPE html>", self.html)
        self.assertIn("</html>", self.html)

    def test_contains_every_dimension_label_and_remediation(self):
        for r in self.results:
            self.assertIn(_escape(r.label), self.html)
            self.assertIn(_escape(r.remediation), self.html)

    def test_contains_overall_score_and_lens_averages(self):
        self.assertIn(f"{self.agg['overall_score']} / 3", self.html)
        for lens_key, score in self.agg["lens_scores"].items():
            self.assertIn(str(score), self.html)

    def test_escapes_html_special_characters_in_evidence(self):
        self.assertEqual(_escape("<script>&"), "&lt;script&gt;&amp;")

    def test_generated_timestamp_present(self):
        self.assertIn("2026-08-20T12:00:00", self.html)


if __name__ == "__main__":
    unittest.main()
