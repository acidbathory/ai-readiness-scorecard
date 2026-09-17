"""Confidence: UNVERIFIED. New Relic's AI coding observability product
(the "Introducing AI Coding Observability" blog post that originated this
project's brief in prompt.md) emits three custom event types tracking AI
coding-assistant usage across an engineering org -- distinct from every other
dimension in this scorecard, which all measure AI *in production*, not AI
*in the SDLC*:

  AiToolCall     -- which AI coding tool was invoked, how often (adoption/usage)
  AiCodingTask   -- task-level: was an AI-assisted coding task completed or abandoned
  AiAntiPattern  -- anti-patterns flagged specifically in AI-generated code

None of the three has a confirmed live query shape in this codebase yet --
no account tested so far has this integration enabled. Follows the same
honest-Unknown-on-error pattern as security_vuln.py/ai_quality_feedback.py: a
query failure means "couldn't verify," not a false "Absent". AiToolCall
gates the tier (adoption is the base signal, and the one this check has the
most confidence exists as a real event type); AiCodingTask/AiAntiPattern are
evidence-only until their relationship to tiering is confirmed against a
real account with the integration enabled.
"""

from ..nerdgraph import GENERIC_NRQL_QUERY as NRQL_QUERY, NerdGraphError
from ..scoring import tier_from_count
from .base import CheckResult, result_for
from .. import config as config_module

DIMENSION = "ai_coding_observability"
LABEL = "AI coding assistant observability"
LENS = "ai_for_observability"
CONFIDENCE = "unverified"
REMEDIATION = {
    0: "No AI coding-assistant telemetry detected. Enable New Relic's AI coding "
       "observability integration so AiToolCall events start capturing which "
       "tools (Copilot, Cursor, Claude Code, etc.) your engineers actually use.",
    1: "Some AI coding-tool usage is tracked -- roll it out account-wide so "
       "adoption is visible across every team, not just an early-adopter pocket.",
    2: "Good adoption visibility -- start watching AiCodingTask completion data "
       "and AiAntiPattern flags (both evidence-only above) to see whether AI-"
       "assisted tasks are actually finishing, and whether AI-generated code is "
       "introducing recognizable smells.",
    3: "Mature AI coding-tool visibility -- correlate AiAntiPattern flags with "
       "your code-review/quality-gate process so they're acted on, not just logged.",
}
REMEDIATION_UNKNOWN = (
    "Confirm the New Relic user key has NRQL read permission on this account "
    "and that AiToolCall/AiCodingTask/AiAntiPattern event types are queryable -- "
    "these require New Relic's AI coding observability integration to be enabled."
)


def _count(ctx, from_clause, fixture_key):
    nrql = f"SELECT count(*) FROM {from_clause} SINCE {ctx.lookback_days} days ago"
    data = ctx.gql(NRQL_QUERY, {"accountId": ctx.account_id, "nrql": nrql}, fixture_key=fixture_key)
    results = data.get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])
    return results[0].get("count", 0) if results else 0


def run(ctx):
    thresholds = ctx.config[DIMENSION]

    try:
        tool_call_count = _count(ctx, "AiToolCall", "ai_coding_observability.tool_calls")
    except NerdGraphError as exc:
        return CheckResult(
            dimension=DIMENSION,
            label=LABEL,
            lens=LENS,
            confidence=CONFIDENCE,
            score=None,
            tier=config_module.UNKNOWN_TIER_LABEL,
            evidence=(
                f"Could not verify -- AiToolCall query failed: {exc}. This event type "
                f"requires New Relic's AI coding observability integration to be enabled; "
                f"has never been confirmed populated on any account tested so far."
            ),
            raw_metrics={},
            error=str(exc),
            remediation=REMEDIATION_UNKNOWN,
        )

    task_count = _count(ctx, "AiCodingTask", "ai_coding_observability.tasks")
    anti_pattern_count = _count(ctx, "AiAntiPattern", "ai_coding_observability.anti_patterns")

    score = tier_from_count(tool_call_count, thresholds["min_tool_call_events_for_tier"])
    evidence = (
        f"{tool_call_count} AiToolCall events (AI coding-tool usage) over {ctx.lookback_days}d. "
        f"Evidence only: {task_count} AiCodingTask events, {anti_pattern_count} AiAntiPattern flags"
    )

    return result_for(
        DIMENSION, LABEL, LENS, CONFIDENCE, REMEDIATION, score, evidence,
        raw_metrics={
            "tool_call_count": tool_call_count,
            "task_count": task_count,
            "anti_pattern_count": anti_pattern_count,
        },
    )
