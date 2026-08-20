"""Confidence: HIGH. Built entirely from attributes ai_monitoring.py already
confirmed live and populated on a real account (2026-08-20): `vendor` on
LlmChatCompletionSummary and `gen_ai.system` on Span. This check just applies
uniqueCount() -- a proven, already-used NRQL pattern elsewhere in this
codebase -- to a new question: is the AI workload locked into a single LLM
provider (a real resilience risk given how often providers have deprecated
models or changed pricing/availability), or is there genuine multi-provider
coverage?

`gen_ai.system` is the deprecated OTel attribute name (renamed to
`gen_ai.provider.name` in the GenAI semconv v1.37.0) -- same rename-to-watch
note as ai_monitoring.py. Queries `gen_ai.system` because it's the one
confirmed populated; add `gen_ai.provider.name` alongside it once that
attribute shows up live on some account.
"""

from ..scoring import tier_from_count
from .base import CheckResult
from .. import config as config_module

DIMENSION = "model_vendor_diversity"
LABEL = "Multi-provider / vendor resilience"
LENS = "observability_for_ai"
CONFIDENCE = "high"
REMEDIATION = {
    0: "No LLM vendor/provider data detected at all -- this tracks with an Absent "
       "ai_monitoring result. Get basic AI Monitoring coverage in place first; vendor "
       "diversity isn't measurable before that.",
    1: "All LLM traffic is on a single provider. Document and test a fallback path to "
       "a second provider (e.g. Azure OpenAI as a fallback to OpenAI direct, or Bedrock "
       "as a fallback to Anthropic direct) so a provider outage or model deprecation "
       "doesn't stop the AI workload cold.",
    2: "Two providers are in use -- confirm there's an actual automatic failover path "
       "between them, not just incidental multi-vendor usage across unrelated features.",
    3: "Good provider diversity -- periodically test the failover path itself under a "
       "simulated outage, not just confirm it's configured.",
}
REMEDIATION_UNKNOWN = (
    "Confirm the New Relic user key has NRQL read permission for LlmChatCompletionSummary "
    "and Span event types on this account."
)

NRQL_QUERY = """
query($accountId: Int!, $nrql: Nrql!) {
  actor { account(id: $accountId) { nrql(query: $nrql) { results } } }
}
"""


def _unique_count(ctx, nrql, fixture_key, key):
    data = ctx.gql(NRQL_QUERY, {"accountId": ctx.account_id, "nrql": nrql}, fixture_key=fixture_key)
    results = data.get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])
    return results[0].get(key, 0) if results else 0


def run(ctx):
    thresholds = ctx.config[DIMENSION]

    llm_vendor_count = _unique_count(
        ctx,
        f"SELECT uniqueCount(vendor) FROM LlmChatCompletionSummary SINCE {ctx.lookback_days} days ago",
        "model_vendor_diversity.llm_vendors",
        "uniqueCount.vendor",
    )
    genai_vendor_count = _unique_count(
        ctx,
        f"SELECT uniqueCount(gen_ai.system) FROM Span WHERE gen_ai.request.model IS NOT NULL "
        f"SINCE {ctx.lookback_days} days ago",
        "model_vendor_diversity.genai_vendors",
        "uniqueCount.gen_ai.system",
    )
    vendor_count = max(llm_vendor_count, genai_vendor_count)

    score = tier_from_count(vendor_count, thresholds["min_vendor_count_for_tier"])
    evidence = (
        f"{llm_vendor_count} distinct vendor(s) via LlmChatCompletionSummary, "
        f"{genai_vendor_count} distinct gen_ai.system value(s) via Span "
        f"(scoring on the stronger of the two signals)"
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
            "llm_vendor_count": llm_vendor_count,
            "genai_vendor_count": genai_vendor_count,
            "vendor_count": vendor_count,
        },
        remediation=REMEDIATION[score],
    )
