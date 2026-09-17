"""Confidence: MEDIUM. Autopilot has no standalone NerdGraph query in either
reference repo -- it's only ever invoked as a `newrelic.autopilot.run` action
step inside a Workflow Automation canvas. This check reuses
workflow_automation's confirmed workflow list, then fetches each workflow's
YAML definition (shape confirmed: reference-repo-a/scripts/bootstrap.py:99-106)
and text-matches for an Autopilot action -- an indirect heuristic layered on
a confirmed primitive, hence "medium" rather than "high" confidence.
"""

from ..scoring import tier_from_count
from .base import result_for
from .workflow_automation import fetch_workflows, fetch_workflow_yaml

DIMENSION = "autopilot"
LABEL = "Autopilot usage within Workflow Automation"
LENS = "ai_for_observability"
CONFIDENCE = "medium"
REMEDIATION = {
    0: "No canvases invoke Autopilot. Add a `newrelic.autopilot.run` action step to "
       "your Workflow Automation canvases so incidents get an AI-generated "
       "root-cause summary before a human is paged.",
    1: "Autopilot is used in one canvas -- extend it to your other Workflow "
       "Automation canvases so every automated investigation benefits from AI-assisted RCA.",
    2: "Autopilot adoption is solid -- periodically spot-check a sample of past "
       "runs for investigation quality/accuracy rather than assuming it's always right.",
    3: "Mature Autopilot usage -- feed its investigation outputs back as training/eval "
       "data for the AI quality & feedback-loop dimension above, closing the loop.",
}
REMEDIATION_UNKNOWN = (
    "Confirm the New Relic user key has `workflow_automation.*` NerdGraph "
    "permission on this account -- this check depends on workflow_automation's "
    "own fetch succeeding first."
)

AUTOPILOT_MARKERS = ("autopilot", "newrelic.autopilot.run")


def run(ctx):
    thresholds = ctx.config[DIMENSION]
    workflows = fetch_workflows(ctx)

    matched = 0
    for name, yaml_text in fetch_workflow_yaml(ctx, workflows, "autopilot"):
        if any(marker in yaml_text.lower() for marker in AUTOPILOT_MARKERS):
            matched += 1

    score = tier_from_count(matched, thresholds["min_autopilot_workflows_for_tier"])
    if not workflows:
        evidence = "No workflows configured, so no Autopilot usage to detect"
    else:
        evidence = (
            f"{matched} of {len(workflows)} workflows reference an Autopilot "
            f"action step (text-matched on the canvas YAML -- Autopilot has no "
            f"standalone NerdGraph query, so this is an indirect signal)"
        )

    return result_for(
        DIMENSION, LABEL, LENS, CONFIDENCE, REMEDIATION, score, evidence,
        raw_metrics={"autopilot_workflows": matched, "total_workflows": len(workflows)},
    )
