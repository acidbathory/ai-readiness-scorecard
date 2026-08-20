"""Confidence: HIGH. Confirmed live against a real account (2026-08-20):
`account(id:).workflowAutomation.workflows(cursor:)` returns a cursor-paginated
`{ nextCursor, results: [{ definition: { name, description, version } }] }` --
NOT the flat `{ name enabled }` shape originally guessed by analogy to the
singular `workflow(name:)` lookup (that one *is* confirmed:
continental-demo/scripts/bootstrap.py:97-110). There is no `enabled`/disabled
concept exposed anywhere on a workflow definition in this schema -- adoption
is measured by workflow *count*, not an enabled subset.
"""

from ..scoring import tier_from_count
from .base import CheckResult
from .. import config as config_module

DIMENSION = "workflow_automation"
LABEL = "Workflow Automation adoption"
LENS = "ai_for_observability"
CONFIDENCE = "high"
REMEDIATION = {
    0: "No Workflow Automation canvases configured. Start with one: automate the "
       "response to your highest-volume alert (e.g. a deployment rollback or "
       "restart-on-crash) using New Relic Workflow Automation.",
    1: "One canvas exists -- extend automation to your next 2-3 most common "
       "incident types so on-call isn't manually running repeatable playbooks by hand.",
    2: "Good canvas coverage -- audit for overlapping/redundant canvases and "
       "consolidate them, and confirm every P1 alert policy has a corresponding canvas.",
    3: "Comprehensive automation -- review canvases quarterly against actual "
       "incident history to prune stale ones and catch new repeatable patterns "
       "before they become manual toil again.",
}
REMEDIATION_UNKNOWN = (
    "Confirm the New Relic user key has `workflow_automation.*` NerdGraph "
    "permission on this account."
)

QUERY = """
query($accountId: Int!, $cursor: String) {
  actor {
    account(id: $accountId) {
      workflowAutomation {
        workflows(cursor: $cursor) {
          nextCursor
          results { definition { name } }
        }
      }
    }
  }
}
"""

MAX_PAGES = 10


def fetch_workflows(ctx):
    """Returns a list of {"name": ...} dicts, following nextCursor."""
    workflows = []
    cursor = None
    for _ in range(MAX_PAGES):
        data = ctx.gql(
            QUERY,
            {"accountId": ctx.account_id, "cursor": cursor},
            fixture_key="workflow_automation.workflows",
        )
        page = data.get("actor", {}).get("account", {}).get("workflowAutomation", {}).get("workflows", {}) or {}
        for r in page.get("results", []) or []:
            name = r.get("definition", {}).get("name")
            if name:
                workflows.append({"name": name})
        cursor = page.get("nextCursor")
        if not cursor:
            break
    return workflows


def run(ctx):
    thresholds = ctx.config[DIMENSION]
    workflows = fetch_workflows(ctx)
    score = tier_from_count(len(workflows), thresholds["min_workflows_for_tier"])
    evidence = f"{len(workflows)} workflows configured"

    return CheckResult(
        dimension=DIMENSION,
        label=LABEL,
        lens=LENS,
        confidence=CONFIDENCE,
        score=score,
        tier=config_module.TIER_LABELS[score],
        evidence=evidence,
        raw_metrics={"total_workflows": len(workflows)},
        remediation=REMEDIATION[score],
    )
