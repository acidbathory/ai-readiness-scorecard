"""Confidence: MEDIUM. Originally UNVERIFIED, guessing at `LlmCompletion,
LlmChatCompletionSummary, LlmEmbedding` -- run live against a real account
(2026-08-20) that confirmed `LlmChatCompletionSummary` is the real, heavily
populated event type (`LlmCompletion` and `LlmEmbedding` were both zero on
that account and dropped from the query). Bumped from unverified to medium,
not high: confirmed against one live account, not yet a proven pattern
across multiple engagements.

The token/cost visibility sub-signal (Langfuse's "generation cost & token
tracking" concept) is new: `response.usage.{prompt,completion,total}_tokens`
and `request.model`/`vendor` were confirmed present as real attributes on
`LlmChatCompletionSummary` via a live `SELECT keyset()` on the same account.
"""

from ..scoring import combine_tiers, tier_from_count
from .base import CheckResult
from .. import config as config_module

DIMENSION = "ai_monitoring"
LABEL = "AI Monitoring / LLM span coverage"
LENS = "observability_for_ai"
CONFIDENCE = "medium"
REMEDIATION = (
    "Enable New Relic AI Monitoring on LLM-calling services (OpenAI/Bedrock/Azure "
    "OpenAI SDKs) to start capturing prompt/response, token, and cost telemetry."
)

NRQL_QUERY = """
query($accountId: Int!, $nrql: Nrql!) {
  actor { account(id: $accountId) { nrql(query: $nrql) { results } } }
}
"""


def _nrql_result(ctx, nrql, fixture_key):
    data = ctx.gql(NRQL_QUERY, {"accountId": ctx.account_id, "nrql": nrql}, fixture_key=fixture_key)
    return data.get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])


def run(ctx):
    thresholds = ctx.config[DIMENSION]

    events_nrql = f"SELECT count(*) FROM LlmChatCompletionSummary SINCE {ctx.lookback_days} days ago"
    events_results = _nrql_result(ctx, events_nrql, "ai_monitoring.events")
    event_count = events_results[0].get("count", 0) if events_results else 0

    entities_nrql = (
        f"SELECT uniqueCount(entity.guid) FROM LlmChatCompletionSummary "
        f"SINCE {ctx.lookback_days} days ago"
    )
    entities_results = _nrql_result(ctx, entities_nrql, "ai_monitoring.entities")
    entity_count = entities_results[0].get("uniqueCount.entity.guid", 0) if entities_results else 0

    token_nrql = (
        f"SELECT percentage(count(*), WHERE response.usage.total_tokens IS NOT NULL) "
        f"FROM LlmChatCompletionSummary SINCE {ctx.lookback_days} days ago"
    )
    token_results = _nrql_result(ctx, token_nrql, "ai_monitoring.token_visibility")
    # NRQL's exact column key for a bare percentage(...) varies by account/API
    # version -- take the lone value rather than hardcoding a key name.
    token_visibility_pct = next(iter(token_results[0].values()), 0) if token_results else 0

    event_tier = tier_from_count(event_count, thresholds["min_events_for_tier"])
    entity_tier = tier_from_count(entity_count, thresholds["min_entities_for_tier"])
    token_tier = tier_from_count(token_visibility_pct, thresholds["min_token_visibility_pct_for_tier"])
    score = combine_tiers(event_tier, entity_tier, token_tier, method="min")

    evidence = (
        f"{event_count} LlmChatCompletionSummary events across {entity_count} distinct "
        f"entities over {ctx.lookback_days}d; {token_visibility_pct:.0f}% carry token/cost "
        f"usage data (request.model, vendor, response.usage.total_tokens)"
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
            "event_count": event_count,
            "entity_count": entity_count,
            "token_visibility_pct": round(token_visibility_pct, 1),
        },
        remediation=REMEDIATION,
    )
