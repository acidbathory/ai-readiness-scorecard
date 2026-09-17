import unittest

from ai_readiness import config as config_module
from ai_readiness.checks import human_approval_gates
from ai_readiness.checks.base import Context
from ai_readiness.scoring import aggregate


def _workflows_gql(names, yaml_by_name):
    def gql(query, variables=None, fixture_key=None):
        if "workflows(" in query:
            return {
                "actor": {
                    "account": {
                        "workflowAutomation": {
                            "workflows": {
                                "nextCursor": None,
                                "results": [{"definition": {"name": n}} for n in names],
                            }
                        }
                    }
                }
            }
        name = variables["name"]
        return {
            "actor": {
                "account": {
                    "workflowAutomation": {"workflow": {"definition": {"yaml": yaml_by_name[name]}}}
                }
            }
        }
    return gql


def _ctx(gql):
    return Context(gql=gql, account_id=1, lookback_days=30, config=config_module.THRESHOLDS)


class TestHumanApprovalGatesNotApplicable(unittest.TestCase):
    def test_zero_action_taking_workflows_scores_none_not_zero(self):
        """No autonomous actions anywhere means there's nothing to gate --
        that's a different claim from '0% of actions are gated', which is a
        real, scoreable gap (tier 0/Absent)."""
        gql = _workflows_gql(["wf-a"], {"wf-a": "steps:\n  - action: slack.chat.postMessage\n"})
        result = human_approval_gates.run(_ctx(gql))
        self.assertIsNone(result.score)
        self.assertEqual(result.tier, config_module.NOT_APPLICABLE_TIER_LABEL)
        self.assertIsNone(result.error)  # ran fine -- this is not a failure

    def test_action_taking_with_zero_gated_still_scores_zero(self):
        """The real Absent case: an autonomous action exists and isn't
        gated -- must stay a scored tier 0, not collapse into N/A."""
        gql = _workflows_gql(["wf-a"], {"wf-a": "steps:\n  - action: aws.lambda.invoke\n"})
        result = human_approval_gates.run(_ctx(gql))
        self.assertEqual(result.score, 0)
        self.assertEqual(result.tier, config_module.TIER_LABELS[0])

    def test_not_applicable_excluded_from_aggregate_like_unknown(self):
        gql = _workflows_gql([], {})
        result = human_approval_gates.run(_ctx(gql))
        agg = aggregate([result])
        self.assertEqual(agg["lens_scores"], {})
        self.assertEqual(agg["overall_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
