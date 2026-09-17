import unittest

from ai_readiness import config as config_module
from ai_readiness.checks import apm_coverage
from ai_readiness.checks.base import Context


class RecordingGql:
    """Scripted responses keyed by query-document substring; records every
    call's variables so tests can assert on the exact filter string sent."""

    def __init__(self, total_count, tagged_pages):
        self.calls = []
        self.total_count = total_count
        self.tagged_pages = tagged_pages

    def __call__(self, query, variables=None, fixture_key=None):
        self.calls.append((query, variables))
        if "count" in query:
            return {"actor": {"entitySearch": {"count": self.total_count}}}
        cursor = (variables or {}).get("cursor")
        page = self.tagged_pages.get(cursor, {"entities": [], "nextCursor": None})
        return {"actor": {"entitySearch": {"results": page}}}


def _ctx(gql, account_id=42):
    return Context(gql=gql, account_id=account_id, lookback_days=30, config=config_module.THRESHOLDS)


class TestApmCoverageUsesTagNotNamePattern(unittest.TestCase):
    def test_mundane_ai_substring_names_dont_inflate_count(self):
        """email-service and maintenance-cron both contain the substring
        'ai' -- the old name-glob heuristic (`*ai*`) would have falsely
        matched both. They're part of the account's total reporting APM
        count here, but untagged, so a real server would never return them
        from the tags.aiEnabledApp-filtered query. Only the one genuinely
        tagged entity should count."""
        gql = RecordingGql(
            total_count=8,  # includes email-service, maintenance-cron, and 5 other untagged services
            tagged_pages={None: {"entities": [{"guid": "x1", "name": "rag-service"}], "nextCursor": None}},
        )
        result = apm_coverage.run(_ctx(gql))
        self.assertEqual(result.raw_metrics["ai_adjacent_matches"], 1)
        self.assertEqual(result.raw_metrics["total_apm_entities"], 8)

    def test_filter_scopes_to_account_and_tag_not_name(self):
        gql = RecordingGql(total_count=0, tagged_pages={None: {"entities": [], "nextCursor": None}})
        apm_coverage.run(_ctx(gql, account_id=42))
        filter_strings = [v["query"] for _, v in gql.calls]
        for query in filter_strings:
            self.assertIn("accountId = 42", query)
        self.assertTrue(any("tags.aiEnabledApp = 'true'" in q for q in filter_strings))
        self.assertFalse(any("*ai*" in q for q in filter_strings))

    def test_evidence_mentions_tag_not_name_patterns(self):
        gql = RecordingGql(
            total_count=1,
            tagged_pages={None: {"entities": [{"guid": "x1", "name": "rag-service"}], "nextCursor": None}},
        )
        result = apm_coverage.run(_ctx(gql))
        self.assertIn("aiEnabledApp", result.evidence)
        self.assertNotIn("name pattern", result.evidence)


if __name__ == "__main__":
    unittest.main()
