"""Confidence: MEDIUM. `ChangeTrackingEvent` is a real, populated NRQL event
type -- confirmed live on a real account (2026-08-20, 70 events over 90
days) with `category`/`description` fields. What's a heuristic, not
confirmed: whether an entry is AI/prompt/model-related. NRQL `LIKE`
case-sensitivity is uncertain, so this fetches raw `description` text (same
"fetch raw, pattern-match locally" approach as apm_coverage.py) and keyword-
matches in Python instead of trusting a NRQL string filter. Capped at a
200-event sample for the keyword pass; the total count is fetched separately
so evidence can disclose when the sample is a subset of a larger history.
"""

from ..scoring import tier_from_count
from .base import CheckResult
from .. import config as config_module

DIMENSION = "ai_change_tracking"
LABEL = "AI/prompt/model change tracking"
LENS = "ai_for_observability"
CONFIDENCE = "medium"
REMEDIATION = {
    0: "No Change Tracking events reference AI/model/prompt changes. Start recording "
       "prompt and model-version changes as Change Tracking events (`changeTrackingCreateEvent`) "
       "so an AI regression can be correlated with 'what changed', the same way a bad "
       "deploy is today.",
    1: "A few AI-related changes are tracked -- make it consistent: every prompt edit "
       "or model-version bump should create a Change Tracking event, not just some of them.",
    2: "Good tracking coverage -- correlate these change events against the "
       "ai_quality_feedback dimension so a feedback-score drop can be traced back to "
       "the specific change that caused it.",
    3: "Mature change-tracking hygiene -- consider gating prompt/model changes on the "
       "regression-test habit described in ai_quality_feedback's top tier before they ship.",
}
REMEDIATION_UNKNOWN = (
    "Confirm the New Relic user key has NRQL read permission for the ChangeTrackingEvent "
    "event type on this account."
)

NRQL_QUERY = """
query($accountId: Int!, $nrql: Nrql!) {
  actor { account(id: $accountId) { nrql(query: $nrql) { results } } }
}
"""

AI_KEYWORDS = ("model", "prompt", "llm", "gpt", "gen_ai", "claude", "gemini")
SAMPLE_LIMIT = 200


def run(ctx):
    thresholds = ctx.config[DIMENSION]

    total_results = ctx.gql(
        NRQL_QUERY,
        {"accountId": ctx.account_id, "nrql": f"SELECT count(*) FROM ChangeTrackingEvent SINCE {ctx.lookback_days} days ago"},
        fixture_key="ai_change_tracking.total",
    )
    total_count = (
        total_results.get("actor", {}).get("account", {}).get("nrql", {}).get("results", [{}])[0].get("count", 0)
    )

    sample_data = ctx.gql(
        NRQL_QUERY,
        {
            "accountId": ctx.account_id,
            "nrql": f"SELECT description FROM ChangeTrackingEvent SINCE {ctx.lookback_days} days ago LIMIT {SAMPLE_LIMIT}",
        },
        fixture_key="ai_change_tracking.events",
    )
    sample = sample_data.get("actor", {}).get("account", {}).get("nrql", {}).get("results", []) or []

    ai_related = [
        r for r in sample
        if any(kw in (r.get("description") or "").lower() for kw in AI_KEYWORDS)
    ]

    score = tier_from_count(len(ai_related), thresholds["min_ai_change_events_for_tier"])
    sample_note = f" (sample of {len(sample)}" + (f" out of {total_count} total)" if total_count > len(sample) else ")")
    evidence = (
        f"{len(ai_related)} of {len(sample)} Change Tracking events reference AI/model/prompt "
        f"keywords over {ctx.lookback_days}d{sample_note}"
    )

    return CheckResult(
        dimension=DIMENSION,
        label=LABEL,
        lens=LENS,
        confidence=CONFIDENCE,
        score=score,
        tier=config_module.TIER_LABELS[score],
        evidence=evidence,
        raw_metrics={"ai_related_events": len(ai_related), "total_events": total_count, "sample_size": len(sample)},
        remediation=REMEDIATION[score],
    )
