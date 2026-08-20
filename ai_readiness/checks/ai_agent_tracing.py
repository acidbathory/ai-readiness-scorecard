"""Confidence: HIGH. Langfuse's "observations"/nested tool-call spans +
retrieval (RAG) spans concepts, combined into one dimension -- multiple event
schemas, one maturity signal: is agentic/multi-step AI behavior actually
visible, or is it just flat chat completions?

Two independent tool-call detection paths, gating the score via max (either
proves readiness): New Relic's own `LlmTool` custom event (confirmed real and
heavily populated, 365K events on a live account, 2026-08-20) and OpenTelemetry
GenAI's `gen_ai.tool.name` Span attribute (confirmed real and populated on the
SAME account, 367K spans) -- researched to be a genuinely DISTINCT schema, not
a duplicate: `LlmTool` is New Relic's own AI-Monitoring-specific event type,
`gen_ai.tool.name` is OTel's generic "any tool execution" span convention
(e.g. emitted by OpenLLMetry/Traceloop-instrumented accounts that never
populate `LlmTool` at all). An account only using one path should still score
correctly.

`LlmVectorSearch` and `gen_ai.data_source.id` (OTel's retrieval-span
convention) are both real, non-erroring query shapes but were zero on the one
account tested, so both are surfaced as evidence only, not allowed to drag
the score down (same pattern as infra_gpu.py's GPU sub-signal).
"""

from ..scoring import combine_tiers, tier_from_count
from .base import CheckResult
from .. import config as config_module

DIMENSION = "ai_agent_tracing"
LABEL = "AI agent tool-call & retrieval (RAG) tracing"
LENS = "observability_for_ai"
CONFIDENCE = "high"
REMEDIATION = {
    0: "No tool-call/agent-step tracing detected. If your AI workload uses "
       "function-calling or tool use, instrument it so each invocation emits a span "
       "-- New Relic's AI Monitoring captures this automatically for supported SDKs; "
       "OTel-based agents need `gen_ai.execute_tool` spans from a library like OpenLLMetry.",
    1: "Some tool-call tracing exists -- extend it to every agent/tool in the "
       "pipeline, not just one, so a multi-step agent run is fully visible end to end.",
    2: "Tool-call tracing is solid; add retrieval/RAG span instrumentation too "
       "(currently evidence-only above) so vector-search steps are traceable "
       "alongside tool calls, not just chat completions.",
    3: "Comprehensive agent tracing -- add span-level latency budgets/alerts per "
       "tool so a slow tool call (not just a slow LLM call) pages the right team.",
}
REMEDIATION_UNKNOWN = (
    "Confirm the New Relic user key has NRQL read permission on this account for "
    "`LlmTool` and `Span` event types."
)

NRQL_QUERY = """
query($accountId: Int!, $nrql: Nrql!) {
  actor { account(id: $accountId) { nrql(query: $nrql) { results } } }
}
"""


def _count(ctx, from_clause, fixture_key):
    nrql = f"SELECT count(*) FROM {from_clause} SINCE {ctx.lookback_days} days ago"
    data = ctx.gql(NRQL_QUERY, {"accountId": ctx.account_id, "nrql": nrql}, fixture_key=fixture_key)
    results = data.get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])
    return results[0].get("count", 0) if results else 0


def run(ctx):
    thresholds = ctx.config[DIMENSION]

    tool_call_count = _count(ctx, "LlmTool", "ai_agent_tracing.tool_calls")
    genai_tool_count = _count(ctx, "Span WHERE gen_ai.tool.name IS NOT NULL", "ai_agent_tracing.genai_tool_calls")
    vector_search_count = _count(ctx, "LlmVectorSearch", "ai_agent_tracing.vector_search")
    genai_retrieval_count = _count(
        ctx, "Span WHERE gen_ai.data_source.id IS NOT NULL", "ai_agent_tracing.genai_retrieval"
    )

    score = combine_tiers(
        tier_from_count(tool_call_count, thresholds["min_tool_call_events_for_tier"]),
        tier_from_count(genai_tool_count, thresholds["min_tool_call_events_for_tier"]),
        method="max",
    )

    evidence = (
        f"Tool-call tracing: {tool_call_count} LlmTool events, {genai_tool_count} gen_ai.tool.name spans. "
        f"Retrieval/RAG tracing (evidence only): {vector_search_count} LlmVectorSearch events, "
        f"{genai_retrieval_count} gen_ai.data_source.id spans (over {ctx.lookback_days}d)"
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
            "tool_call_count": tool_call_count,
            "genai_tool_call_count": genai_tool_count,
            "vector_search_count": vector_search_count,
            "genai_retrieval_count": genai_retrieval_count,
        },
        remediation=REMEDIATION[score],
    )
