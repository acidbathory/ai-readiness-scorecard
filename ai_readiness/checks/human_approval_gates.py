"""Confidence: MEDIUM. Maps to OWASP LLM08 (Excessive Agency): if a workflow
takes an autonomous real-world action, is there a human-approval step before
it fires? Same heuristic-on-a-confirmed-primitive shape as autopilot.py --
reuses workflow_automation.fetch_workflows() (confirmed live,
2026-08-20) and per-workflow YAML fetch (confirmed:
reference-repo-a/scripts/bootstrap.py:99-106), then text-matches for two
marker sets. This is intentionally a coarse heuristic: it can't tell whether
an approval step actually GATES the action step (vs. sitting elsewhere in the
canvas) without parsing the YAML's step graph, only that both kinds of
markers are present somewhere in the same canvas.

Zero action-taking workflows is scored `score=None` / tier `Not Applicable`,
not tier 0 -- there's nothing to gate yet, which isn't the same claim as "an
autonomous action exists and isn't gated" (the real tier-0 case below). Like
an Unknown result, `None` is dropped from the lens/overall average, but
`Not Applicable` reads as "measured, nothing to grade" rather than "couldn't
measure" in the report/dashboard.
"""

from ..scoring import tier_from_count
from .base import CheckResult, result_for
from .workflow_automation import fetch_workflows, fetch_workflow_yaml
from .. import config as config_module

DIMENSION = "human_approval_gates"
LABEL = "Human-approval gates on autonomous agent actions"
LENS = "observability_for_ai"
CONFIDENCE = "medium"
REMEDIATION = {
    0: "Autonomous action-taking workflows exist but none are gated -- add a "
       "human-approval step immediately; an ungated autonomous action is the "
       "highest-risk gap this dimension measures.",
    1: "Some action-taking canvases have no approval gate -- add a wait-for-reaction "
       "(e.g. Slack ✅) or similar approval step before the action step in each one, "
       "the same pattern already used elsewhere in your Workflow Automation setup.",
    2: "Most action-taking canvases are gated -- audit the remaining ungated ones "
       "specifically; an autonomous action with no human checkpoint is the highest-risk "
       "gap on this account.",
    3: "Approval gates are consistently present. Periodically test the timeout/no-action "
       "path too (what happens if nobody approves in time), not just the happy path.",
}
REMEDIATION_NOT_APPLICABLE = (
    "No autonomous action-taking workflows detected. If/when you automate a "
    "response that changes production state (rollback, restart, remediation), "
    "gate it behind a human-approval step from day one rather than retrofitting "
    "one later."
)
REMEDIATION_UNKNOWN = (
    "Confirm the New Relic user key has `workflow_automation.*` NerdGraph permission -- "
    "this check depends on the same workflow list and YAML fetch as workflow_automation/autopilot."
)

ACTION_MARKERS = ("http.post", "aws.", "lambda", "restart", "rollback", "remediate")
APPROVAL_MARKERS = ("getreactions", "approval", "waitfor", "reaction", "approve")


def run(ctx):
    thresholds = ctx.config[DIMENSION]
    workflows = fetch_workflows(ctx)

    action_taking = 0
    gated = 0
    for name, yaml_text in fetch_workflow_yaml(ctx, workflows, "human_approval_gates"):
        yaml_text = yaml_text.lower()
        has_action = any(marker in yaml_text for marker in ACTION_MARKERS)
        if has_action:
            action_taking += 1
            if any(marker in yaml_text for marker in APPROVAL_MARKERS):
                gated += 1

    if action_taking == 0:
        evidence = (
            "No workflows appear to take autonomous real-world actions (deploy/rollback/"
            "remediate-style steps), so there's nothing to gate yet"
        )
        return CheckResult(
            dimension=DIMENSION,
            label=LABEL,
            lens=LENS,
            confidence=CONFIDENCE,
            score=None,
            tier=config_module.NOT_APPLICABLE_TIER_LABEL,
            evidence=evidence,
            raw_metrics={
                "action_taking_workflows": action_taking,
                "gated_workflows": gated,
                "total_workflows": len(workflows),
            },
            remediation=REMEDIATION_NOT_APPLICABLE,
        )

    gate_coverage_pct = 100 * gated / action_taking
    score = tier_from_count(gate_coverage_pct, thresholds["min_gate_coverage_pct_for_tier"])
    evidence = (
        f"{action_taking} of {len(workflows)} workflows appear to take autonomous actions; "
        f"{gated} of those ({gate_coverage_pct:.0f}%) include a human-approval/reaction-wait "
        f"step before acting"
    )

    return result_for(
        DIMENSION, LABEL, LENS, CONFIDENCE, REMEDIATION, score, evidence,
        raw_metrics={
            "action_taking_workflows": action_taking,
            "gated_workflows": gated,
            "total_workflows": len(workflows),
        },
    )
