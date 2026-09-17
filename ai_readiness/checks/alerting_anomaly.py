"""Confidence: HIGH for the enabled-condition count (query shape confirmed:
reference-repo-a/scripts/bootstrap.py:165-196). The anomaly/baseline-type
breakdown is a best-effort annotation only -- it does NOT gate the tier --
since the exact `type` field values are unverified against a live account.
"""

from ..nerdgraph import paginated_alert_conditions
from ..scoring import tier_from_count
from .base import result_for

DIMENSION = "alerting_anomaly"
LABEL = "Alerting & anomaly-detection coverage"
LENS = "ai_for_observability"
CONFIDENCE = "high"
REMEDIATION = {
    0: "No alert conditions configured. Start with NRQL alert conditions on the AI "
       "workload's key signals: LLM error rate, p95 latency, and token cost per hour.",
    1: "A few alerts exist -- add baseline/anomaly-detection type conditions (not "
       "just static thresholds) for signals with natural daily/weekly seasonality, "
       "like request volume.",
    2: "Good alert coverage -- verify every condition routes to a real notification "
       "channel and has actually fired at least once in testing, not just been "
       "created and forgotten.",
    3: "Comprehensive alerting -- periodically prune conditions that haven't fired "
       "in 90+ days, or tune ones that fire too often (a real alert-fatigue risk).",
}
REMEDIATION_UNKNOWN = (
    "Confirm the New Relic user key has `alerts` NerdGraph read permission on this account."
)

QUERY = """
query($accountId: Int!, $cursor: String) {
  actor {
    account(id: $accountId) {
      alerts {
        nrqlConditionsSearch(searchCriteria: {}, cursor: $cursor) {
          nextCursor
          totalCount
          nrqlConditions { id name enabled type }
        }
      }
    }
  }
}
"""

# Best-effort guess at anomaly/baseline condition type labels -- unverified.
ANOMALY_TYPE_MARKERS = ("baseline", "anomaly")


def run(ctx):
    thresholds = ctx.config[DIMENSION]
    conditions = paginated_alert_conditions(
        ctx.gql, QUERY, ctx.account_id, fixture_key="alerting_anomaly.conditions"
    )

    enabled = [c for c in conditions if c.get("enabled")]
    anomaly_like = [
        c for c in enabled
        if any(marker in (c.get("type") or "").lower() for marker in ANOMALY_TYPE_MARKERS)
    ]

    score = tier_from_count(len(enabled), thresholds["min_conditions_for_tier"])
    evidence = (
        f"{len(enabled)} enabled alert conditions, of which {len(anomaly_like)} "
        f"appear to be anomaly/baseline-type (condition `type` field values "
        f"unverified against a live account)"
    )

    return result_for(
        DIMENSION, LABEL, LENS, CONFIDENCE, REMEDIATION, score, evidence,
        raw_metrics={"enabled_conditions": len(enabled), "anomaly_like_conditions": len(anomaly_like)},
    )
