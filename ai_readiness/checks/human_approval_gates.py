"""Confidence: MEDIUM. Maps to OWASP LLM08 (Excessive Agency): if a workflow
takes an autonomous real-world action, is there a human-approval step before
it fires? Same heuristic-on-a-confirmed-primitive shape as autopilot.py --
reuses workflow_automation.fetch_workflows() (confirmed live,
2026-08-20) and per-workflow YAML fetch (confirmed:
continental-demo/scripts/bootstrap.py:99-106), then text-matches for two
marker sets. This is intentionally a coarse heuristic: it can't tell whether
an approval step actually GATES the action step (vs. sitting elsewhere in the
canvas) without parsing the YAML's step graph, only that both kinds of
markers are present somewhere in the same canvas.
"""

from ..scoring import tier_from_count
from .base import CheckResult
from .workflow_automation import fetch_workflows
from .. import config as config_module

DIMENSION = "human_approval_gates"
LABEL = "Human-approval gates on autonomous agent actions"
LENS = "observability_for_ai"
CONFIDENCE = "medium"
REMEDIATION = {
    0: "No autonomous action-taking workflows detected. If/when you automate a "
       "response that changes production state (rollback, restart, remediation), "
       "gate it behind a human-approval step from day one rather than retrofitting "
       "one later.",
    1: "Some action-taking canvases have no approval gate -- add a wait-for-reaction "
       "(e.g. Slack ✅) or similar approval step before the action step in each one, "
       "the same pattern already used elsewhere in your Workflow Automation setup.",
    2: "Most action-taking canvases are gated -- audit the remaining ungated ones "
       "specifically; an autonomous action with no human checkpoint is the highest-risk "
       "gap on this account.",
    3: "Approval gates are consistently present. Periodically test the timeout/no-action "
       "path too (what happens if nobody approves in time), not just the happy path.",
}
REMEDIATION_UNKNOWN = (
    "Confirm the New Relic user key has `workflow_automation.*` NerdGraph permission -- "
    "this check depends on the same workflow list and YAML fetch as workflow_automation/autopilot."
)

YAML_QUERY = """
query($accountId: Int!, $name: String!) {
  actor {
    account(id: $accountId) {
      workflowAutomation { workflow(name: $name) { definition { yaml } } }
    }
  }
}
"""

ACTION_MARKERS = ("http.post", "aws.", "lambda", "restart", "rollback", "remediate")
APPROVAL_MARKERS = ("getreactions", "approval", "waitfor", "reaction", "approve")


def run(ctx):
    thresholds = ctx.config[DIMENSION]
    workflows = fetch_workflows(ctx)

    action_taking = 0
    gated = 0
    for w in workflows:
        name = w.get("name")
        data = ctx.gql(
            YAML_QUERY,
            {"accountId": ctx.account_id, "name": name},
            fixture_key=f"human_approval_gates.yaml::{name}",
        )
        yaml_text = (
            data.get("actor", {}).get("account", {}).get("workflowAutomation", {})
            .get("workflow", {}).get("definition", {}).get("yaml", "") or ""
        ).lower()
        has_action = any(marker in yaml_text for marker in ACTION_MARKERS)
        if has_action:
            action_taking += 1
            if any(marker in yaml_text for marker in APPROVAL_MARKERS):
                gated += 1

    if action_taking == 0:
        score = 0
        evidence = (
            "No workflows appear to take autonomous real-world actions (deploy/rollback/"
            "remediate-style steps), so there's nothing to gate yet"
        )
    else:
        gate_coverage_pct = 100 * gated / action_taking
        score = tier_from_count(gate_coverage_pct, thresholds["min_gate_coverage_pct_for_tier"])
        evidence = (
            f"{action_taking} of {len(workflows)} workflows appear to take autonomous actions; "
            f"{gated} of those ({gate_coverage_pct:.0f}%) include a human-approval/reaction-wait "
            f"step before acting"
        )

    return CheckResult(
        dimension=DIMENSION,
        label=LABEL,
        lens=LENS,
        confidence=CONFIDENCE,
        score=score,
        tier=config_module.TIER_LABELS[score],
        evidence=evidence,
        raw_metrics={
            "action_taking_workflows": action_taking,
            "gated_workflows": gated,
            "total_workflows": len(workflows),
        },
        remediation=REMEDIATION[score],
    )
