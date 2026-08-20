"""Confidence: HIGH for the enabled-condition count (query shape confirmed:
continental-demo/scripts/bootstrap.py:165-196). The anomaly/baseline-type
breakdown is a best-effort annotation only -- it does NOT gate the tier --
since the exact `type` field values are unverified against a live account.
"""

from ..scoring import tier_from_count
from .base import CheckResult
from .. import config as config_module

DIMENSION = "alerting_anomaly"
LABEL = "Alerting & anomaly-detection coverage"
LENS = "ai_for_observability"
CONFIDENCE = "high"
REMEDIATION = (
    "Add NRQL alert conditions -- including baseline/anomaly-detection type "
    "conditions -- for the AI workload's key signals (latency, error rate, token cost)."
)

QUERY = """
query($accountId: Int!) {
  actor {
    account(id: $accountId) {
      alerts {
        nrqlConditionsSearch(searchCriteria: {}) {
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
    data = ctx.gql(QUERY, {"accountId": ctx.account_id}, fixture_key="alerting_anomaly.conditions")
    search = data.get("actor", {}).get("account", {}).get("alerts", {}).get("nrqlConditionsSearch", {})
    conditions = search.get("nrqlConditions", []) or []

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

    return CheckResult(
        dimension=DIMENSION,
        label=LABEL,
        lens=LENS,
        confidence=CONFIDENCE,
        score=score,
        tier=config_module.TIER_LABELS[score],
        evidence=evidence,
        raw_metrics={"enabled_conditions": len(enabled), "anomaly_like_conditions": len(anomaly_like)},
        remediation=REMEDIATION,
    )
