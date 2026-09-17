import unittest

from ai_readiness import config as config_module
from ai_readiness.checks import autopilot, human_approval_gates, workflow_automation
from ai_readiness.checks.base import Context
from ai_readiness.nerdgraph import NerdGraphError


class CountingWorkflowsGql:
    """Every call is either the workflows() list query or a per-canvas YAML
    fetch; counts calls to each separately so tests can assert the list is
    fetched once regardless of how many checks ask for it."""

    def __init__(self, names, never_ending=False):
        self.names = names
        self.never_ending = never_ending
        self.workflows_calls = 0
        self.yaml_calls = 0

    def __call__(self, query, variables=None, fixture_key=None):
        if "workflows(" in query:
            self.workflows_calls += 1
            if self.never_ending:
                # Always hands back a cursor -- simulates a server that
                # never terminates the page loop.
                return {
                    "actor": {"account": {"workflowAutomation": {"workflows": {
                        "nextCursor": "more", "results": [{"definition": {"name": "wf-x"}}],
                    }}}}
                }
            return {
                "actor": {"account": {"workflowAutomation": {"workflows": {
                    "nextCursor": None,
                    "results": [{"definition": {"name": n}} for n in self.names],
                }}}}
            }
        self.yaml_calls += 1
        return {
            "actor": {"account": {"workflowAutomation": {"workflow": {
                "definition": {"yaml": "steps:\n  - action: slack.chat.postMessage\n"},
            }}}}
        }


def _ctx(gql, share_fetch_cache=False):
    return Context(
        gql=gql, account_id=1, lookback_days=30, config=config_module.THRESHOLDS,
        share_fetch_cache=share_fetch_cache,
    )


class TestFetchWorkflowsCaching(unittest.TestCase):
    def test_workflows_list_fetched_once_across_three_checks(self):
        """workflow_automation, autopilot, and human_approval_gates all call
        fetch_workflows() independently -- without caching this hits
        NerdGraph 3x for the exact same list every run."""
        gql = CountingWorkflowsGql(["wf-a", "wf-b"])
        ctx = _ctx(gql)

        workflow_automation.run(ctx)
        autopilot.run(ctx)
        human_approval_gates.run(ctx)

        self.assertEqual(gql.workflows_calls, 1)

    def test_raises_instead_of_silently_truncating(self):
        """Matches paginated_entity_search's behavior: a pagination loop
        that never terminates should raise, not silently return a partial
        list as if it were the whole account."""
        gql = CountingWorkflowsGql([], never_ending=True)
        with self.assertRaises(NerdGraphError):
            workflow_automation.run(_ctx(gql))


if __name__ == "__main__":
    unittest.main()
