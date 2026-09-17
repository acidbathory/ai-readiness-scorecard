import unittest

from ai_readiness import config as config_module
from ai_readiness.checks import ai_cost_governance, alerting_anomaly
from ai_readiness.checks.base import Context


class PagedConditionsGql:
    """Simulates an account with more conditions than fit on one page --
    totalCount reflects everything, but nrqlConditions only ever returns the
    current page, exactly like a real nrqlConditionsSearch response."""

    def __init__(self, pages):
        self.pages = pages  # list of condition lists, one per page
        self.calls = []

    def __call__(self, query, variables=None, fixture_key=None):
        self.calls.append(variables)
        cursor = (variables or {}).get("cursor")
        page_num = 0 if cursor is None else int(cursor)
        conditions = self.pages[page_num]
        next_cursor = str(page_num + 1) if page_num + 1 < len(self.pages) else None
        return {
            "actor": {
                "account": {
                    "alerts": {
                        "nrqlConditionsSearch": {
                            "nextCursor": next_cursor,
                            "totalCount": sum(len(p) for p in self.pages),
                            "nrqlConditions": conditions,
                        }
                    }
                }
            }
        }


def _ctx(gql):
    return Context(gql=gql, account_id=1, lookback_days=30, config=config_module.THRESHOLDS)


class TestAlertingAnomalyPagination(unittest.TestCase):
    def test_follows_cursor_across_pages(self):
        gql = PagedConditionsGql(
            pages=[
                [{"id": "1", "name": "a", "enabled": True, "type": "STATIC"}],
                [{"id": "2", "name": "b", "enabled": True, "type": "BASELINE"}],
            ]
        )
        result = alerting_anomaly.run(_ctx(gql))
        self.assertEqual(result.raw_metrics["enabled_conditions"], 2)
        self.assertEqual(len(gql.calls), 2)


class TestAiCostGovernancePagination(unittest.TestCase):
    def test_follows_cursor_across_pages(self):
        gql = PagedConditionsGql(
            pages=[
                [{"id": "1", "name": "token spend", "enabled": True, "nrql": {"query": "SELECT 1"}}],
                [{"id": "2", "name": "checkout latency", "enabled": True, "nrql": {"query": "SELECT 2"}}],
            ]
        )
        result = ai_cost_governance.run(_ctx(gql))
        self.assertEqual(result.raw_metrics["enabled_conditions"], 2)
        self.assertEqual(result.raw_metrics["cost_conditions"], 1)
        self.assertEqual(len(gql.calls), 2)


if __name__ == "__main__":
    unittest.main()
