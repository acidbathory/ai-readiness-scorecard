"""Confidence: MEDIUM. Originally UNVERIFIED, guessing at `LlmCompletion,
LlmChatCompletionSummary, LlmEmbedding` -- run live against a real account
(2026-08-20) that confirmed `LlmChatCompletionSummary` is the real, heavily
populated event type (`LlmCompletion` and `LlmEmbedding` were both zero on
that account and dropped from the query). The token/cost visibility
sub-signal (Langfuse's "generation cost & token tracking" concept) is
likewise confirmed real: `response.usage.{prompt,completion,total}_tokens`
and `request.model`/`vendor` were confirmed present via a live `SELECT
keyset()` on the same account.

Second detection path added the same day, after researching OpenTelemetry's
GenAI semantic conventions (as implemented by OpenLLMetry/Traceloop, a
backend-agnostic OTel SDK -- New Relic is just one of ~20 tested
destinations): an account instrumented via generic OTel GenAI
auto-instrumentation instead of New Relic's own AI Monitoring agent hooks
emits `gen_ai.*` attributes on plain `Span` events -- a genuinely separate
telemetry path, confirmed live on the same account (`gen_ai.request.model`:
2.5M+ spans, `gen_ai.usage.{input,output}_tokens`: 1.2M+) -- and could show
ZERO `Llm*` custom events while still being fully instrumented. Both paths
are computed independently and combined via max: either one proves
readiness, neither is required.

Still MEDIUM, not HIGH: confirmed against one live account, and the OTel
`gen_ai.*` convention itself is spec-flagged **Development** status (not
Stable) as of this research -- `gen_ai.system` was renamed to
`gen_ai.provider.name` in v1.37.0 (2025-08-25), so expect further renames.

The content-capture check is a deliberate non-gating evidence flag: OpenLLMetry
captures raw prompt/completion content into span attributes BY DEFAULT
(`TRACELOOP_TRACE_CONTENT` defaults to `"true"`) -- a confirmed fact worth
surfacing as a data-governance/PII note, not a maturity signal either way.
"""

from ..scoring import combine_tiers, tier_from_count
from .base import CheckResult
from .. import config as config_module

DIMENSION = "ai_monitoring"
LABEL = "AI Monitoring / LLM span coverage"
LENS = "observability_for_ai"
CONFIDENCE = "medium"
REMEDIATION = {
    0: "No LLM telemetry detected via either path. Enable AI Monitoring in your New "
       "Relic APM agent config (`ai_monitoring.enabled: true`), or add OpenTelemetry "
       "GenAI auto-instrumentation (e.g. OpenLLMetry) pointing its OTLP exporter at "
       "New Relic's endpoint.",
    1: "LLM calls are visible but coverage or token-tracking is thin -- instrument "
       "every service that calls an LLM (not just one), and confirm your agent/SDK "
       "version captures `response.usage.*` / `gen_ai.usage.*` token fields (upgrade "
       "it if not).",
    2: "Coverage is good -- close the remaining token/cost visibility gap so every "
       "call reports prompt/completion/total tokens, enabling accurate per-model cost "
       "dashboards.",
    3: "Strong LLM telemetry on both paths. If the PII note above is nonzero, confirm "
       "raw prompt/completion content capture is an intentional, reviewed decision "
       "(e.g. set `TRACELOOP_TRACE_CONTENT=false` if it isn't).",
}
REMEDIATION_UNKNOWN = (
    "Confirm the New Relic user key has NRQL read permission on this account, and "
    "that `LlmChatCompletionSummary` / `Span` event types are queryable."
)

NRQL_QUERY = """
query($accountId: Int!, $nrql: Nrql!) {
  actor { account(id: $accountId) { nrql(query: $nrql) { results } } }
}
"""


def _nrql_result(ctx, nrql, fixture_key):
    data = ctx.gql(NRQL_QUERY, {"accountId": ctx.account_id, "nrql": nrql}, fixture_key=fixture_key)
    return data.get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])


def _single_value(results, key=None):
    if not results:
        return 0
    return results[0].get(key, 0) if key else next(iter(results[0].values()), 0)


def _path_tier(ctx, thresholds, from_clause, token_condition, key_prefix):
    events_results = _nrql_result(
        ctx, f"SELECT count(*) FROM {from_clause} SINCE {ctx.lookback_days} days ago", f"{key_prefix}.events"
    )
    event_count = _single_value(events_results, "count")

    entities_results = _nrql_result(
        ctx,
        f"SELECT uniqueCount(entity.guid) FROM {from_clause} SINCE {ctx.lookback_days} days ago",
        f"{key_prefix}.entities",
    )
    entity_count = _single_value(entities_results, "uniqueCount.entity.guid")

    token_results = _nrql_result(
        ctx,
        f"SELECT percentage(count(*), WHERE {token_condition}) FROM {from_clause} "
        f"SINCE {ctx.lookback_days} days ago",
        f"{key_prefix}.token_visibility",
    )
    token_visibility_pct = _single_value(token_results)

    event_tier = tier_from_count(event_count, thresholds["min_events_for_tier"])
    entity_tier = tier_from_count(entity_count, thresholds["min_entities_for_tier"])
    token_tier = tier_from_count(token_visibility_pct, thresholds["min_token_visibility_pct_for_tier"])
    tier = combine_tiers(event_tier, entity_tier, token_tier, method="min")
    return tier, event_count, entity_count, token_visibility_pct


def run(ctx):
    thresholds = ctx.config[DIMENSION]

    llm_tier, llm_events, llm_entities, llm_token_pct = _path_tier(
        ctx, thresholds, "LlmChatCompletionSummary", "response.usage.total_tokens IS NOT NULL", "ai_monitoring"
    )
    genai_tier, genai_events, genai_entities, genai_token_pct = _path_tier(
        ctx,
        thresholds,
        "Span WHERE gen_ai.request.model IS NOT NULL",
        "gen_ai.usage.input_tokens IS NOT NULL",
        "ai_monitoring.genai",
    )
    score = combine_tiers(llm_tier, genai_tier, method="max")

    content_capture_results = _nrql_result(
        ctx,
        f"SELECT count(*) FROM Span WHERE gen_ai.prompt IS NOT NULL OR gen_ai.input.messages IS NOT NULL "
        f"SINCE {ctx.lookback_days} days ago",
        "ai_monitoring.content_capture",
    )
    content_capture_count = _single_value(content_capture_results, "count")

    evidence = (
        f"NR AI Monitoring path: {llm_events} LlmChatCompletionSummary events / {llm_entities} entities / "
        f"{llm_token_pct:.0f}% with token data. OTel GenAI path: {genai_events} gen_ai.* spans / "
        f"{genai_entities} entities / {genai_token_pct:.0f}% with token data (over {ctx.lookback_days}d)."
    )
    if content_capture_count:
        evidence += (
            f" NOTE: {content_capture_count} spans capture raw prompt/completion content "
            f"(gen_ai.prompt / gen_ai.input.messages) -- review for PII handling."
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
            "llm_event_count": llm_events,
            "llm_entity_count": llm_entities,
            "llm_token_visibility_pct": round(llm_token_pct, 1),
            "genai_event_count": genai_events,
            "genai_entity_count": genai_entities,
            "genai_token_visibility_pct": round(genai_token_pct, 1),
            "content_capture_span_count": content_capture_count,
        },
        remediation=REMEDIATION[score],
    )
