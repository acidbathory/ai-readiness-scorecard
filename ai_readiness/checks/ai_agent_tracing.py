"""Confidence: HIGH (for the LlmTool half). Langfuse's "observations"/nested
tool-call spans + retrieval (RAG) spans concepts, combined into one dimension
-- two NR event types, one maturity signal: is agentic/multi-step AI
behavior actually visible, or is it just flat chat completions?

`LlmTool` was confirmed real and heavily populated (365K events) on a live
account (2026-08-20) -- it gates the score. `LlmVectorSearch` is a real,
non-erroring query shape but was zero on that account, so it's surfaced as
evidence only, not allowed to drag the score down (same "don't let an
unconfirmed sub-signal gate a confirmed one" pattern as infra_gpu.py's GPU
sub-signal).
"""

from ..scoring import tier_from_count
from .base import CheckResult
from .. import config as config_module

DIMENSION = "ai_agent_tracing"
LABEL = "AI agent tool-call & retrieval (RAG) tracing"
LENS = "observability_for_ai"
CONFIDENCE = "high"
REMEDIATION = (
    "Instrument agent tool-calls and retrieval/vector-search steps (not just "
    "top-level chat completions) so multi-step AI behavior is traceable end to end."
)

NRQL_QUERY = """
query($accountId: Int!, $nrql: Nrql!) {
  actor { account(id: $accountId) { nrql(query: $nrql) { results } } }
}
"""


def _count(ctx, event_type, fixture_key):
    nrql = f"SELECT count(*) FROM {event_type} SINCE {ctx.lookback_days} days ago"
    data = ctx.gql(NRQL_QUERY, {"accountId": ctx.account_id, "nrql": nrql}, fixture_key=fixture_key)
    results = data.get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])
    return results[0].get("count", 0) if results else 0


def run(ctx):
    thresholds = ctx.config[DIMENSION]

    tool_call_count = _count(ctx, "LlmTool", "ai_agent_tracing.tool_calls")
    vector_search_count = _count(ctx, "LlmVectorSearch", "ai_agent_tracing.vector_search")

    score = tier_from_count(tool_call_count, thresholds["min_tool_call_events_for_tier"])

    evidence = (
        f"{tool_call_count} tool-call (LlmTool) events and {vector_search_count} "
        f"retrieval/vector-search (LlmVectorSearch) events over {ctx.lookback_days}d"
    )

    return CheckResult(
        dimension=DIMENSION,
        label=LABEL,
        lens=LENS,
        confidence=CONFIDENCE,
        score=score,
        tier=config_module.TIER_LABELS[score],
        evidence=evidence,
        raw_metrics={"tool_call_count": tool_call_count, "vector_search_count": vector_search_count},
        remediation=REMEDIATION,
    )
