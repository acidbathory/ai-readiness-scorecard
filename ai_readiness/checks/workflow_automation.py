"""Confidence: HIGH. Confirmed live against a real account (2026-08-20):
`account(id:).workflowAutomation.workflows(cursor:)` returns a cursor-paginated
`{ nextCursor, results: [{ definition: { name, description, version } }] }` --
NOT the flat `{ name enabled }` shape originally guessed by analogy to the
singular `workflow(name:)` lookup (that one *is* confirmed:
continental-demo/scripts/bootstrap.py:97-110). There is no `enabled`/disabled
concept exposed anywhere on a workflow definition in this schema -- adoption
is measured by workflow *count*, not an enabled subset.
"""

import sys
import time

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


YAML_QUERY = """
query($accountId: Int!, $name: String!) {
  actor {
    account(id: $accountId) {
      workflowAutomation { workflow(name: $name) { definition { yaml } } }
    }
  }
}
"""

# How often (in canvases processed) to print a progress/ETA line for the
# per-canvas YAML loop. Only kicks in once there's enough workflows for the
# wait to actually matter.
_PROGRESS_EVERY = 25
_PROGRESS_MIN_TOTAL = 20


def fetch_workflow_yaml(ctx, workflows, dimension_label):
    """Yields (name, yaml_text) for each workflow, one NerdGraph call each --
    UNLESS ctx.share_fetch_cache is on (live runs only) and another dimension
    already fetched that exact canvas this run, in which case it's free.

    Prints a running elapsed/ETA line to stderr every _PROGRESS_EVERY
    canvases once there are enough of them for it to matter (skipped
    entirely under --quiet), since this loop -- one HTTP call per canvas --
    is the slow part on workflow-heavy accounts.
    """
    cache = ctx.cache.setdefault("workflow_yaml", {}) if ctx.share_fetch_cache else None
    total = len(workflows)
    started = time.monotonic()
    fetched = 0
    for i, w in enumerate(workflows, 1):
        name = w.get("name")
        if cache is not None and name in cache:
            yaml_text = cache[name]
        else:
            data = ctx.gql(
                YAML_QUERY,
                {"accountId": ctx.account_id, "name": name},
                fixture_key=f"{dimension_label}.yaml::{name}",
            )
            yaml_text = (
                data.get("actor", {}).get("account", {}).get("workflowAutomation", {})
                .get("workflow", {}).get("definition", {}).get("yaml", "") or ""
            )
            if cache is not None:
                cache[name] = yaml_text
            fetched += 1

        if not ctx.quiet and total >= _PROGRESS_MIN_TOTAL and (i % _PROGRESS_EVERY == 0 or i == total):
            elapsed = time.monotonic() - started
            remaining = (elapsed / fetched) * (total - i) if fetched else 0.0
            cached_so_far = i - fetched
            print(
                f"      {dimension_label}: canvas {i}/{total} "
                f"({fetched} fetched, {cached_so_far} reused from cache) -- "
                f"{elapsed:.0f}s elapsed, ~{remaining:.0f}s remaining",
                file=sys.stderr,
            )
        yield name, yaml_text


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
