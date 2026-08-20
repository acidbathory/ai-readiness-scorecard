"""Confidence: HIGH. Same `nrqlConditionsSearch` shape alerting_anomaly.py
already confirmed live (continental-demo/scripts/bootstrap.py:165-196), plus
one addition confirmed live on the same account (2026-08-20): the
`NrqlCondition` type's `nrql { query }` field returns each condition's actual
NRQL text, not just its name. That lets this check keyword-match on real
query content (e.g. a condition literally selecting `response.usage.total_tokens`)
even when the condition's name doesn't mention cost/tokens at all -- a real
gap a name-only match (like alerting_anomaly's anomaly-type annotation) would miss.
"""

from ..scoring import tier_from_count
from .base import CheckResult
from .. import config as config_module

DIMENSION = "ai_cost_governance"
LABEL = "AI cost / token spend governance"
LENS = "ai_for_observability"
CONFIDENCE = "high"
REMEDIATION = {
    0: "No cost/token-spend alert conditions detected. Add at least one NRQL alert on "
       "token usage or estimated LLM spend per hour -- a runaway agent loop or a "
       "misconfigured retry can turn into a large, invisible bill fast.",
    1: "One cost-related alert exists -- add coverage per model/service if you run "
       "more than one, since a spend spike on a single model can hide inside an "
       "account-wide aggregate.",
    2: "Cost alerting is developing -- add a budget-cap-style condition (not just an "
       "anomaly/spike alert) so there's a hard ceiling, not just a late warning.",
    3: "Solid cost governance -- review thresholds quarterly against actual usage "
       "growth so they don't silently become too loose (or too noisy) as volume changes.",
}
REMEDIATION_UNKNOWN = (
    "Confirm the New Relic user key has `alerts` NerdGraph read permission on this account."
)

QUERY = """
query($accountId: Int!) {
  actor {
    account(id: $accountId) {
      alerts {
        nrqlConditionsSearch(searchCriteria: {}) {
          totalCount
          nrqlConditions { id name enabled nrql { query } }
        }
      }
    }
  }
}
"""

COST_KEYWORDS = ("cost", "token", "spend", "budget", "usage.total_tokens", "gen_ai.usage")


def run(ctx):
    thresholds = ctx.config[DIMENSION]
    data = ctx.gql(QUERY, {"accountId": ctx.account_id}, fixture_key="ai_cost_governance.conditions")
    search = data.get("actor", {}).get("account", {}).get("alerts", {}).get("nrqlConditionsSearch", {})
    conditions = search.get("nrqlConditions", []) or []

    enabled = [c for c in conditions if c.get("enabled")]
    matched = [
        c for c in enabled
        if any(
            kw in (c.get("name") or "").lower() or kw in (c.get("nrql", {}).get("query") or "").lower()
            for kw in COST_KEYWORDS
        )
    ]

    score = tier_from_count(len(matched), thresholds["min_cost_conditions_for_tier"])
    evidence = (
        f"{len(matched)} of {len(enabled)} enabled alert conditions appear to target AI "
        f"cost/token spend (keyword-matched on condition name and underlying NRQL text)"
    )

    return CheckResult(
        dimension=DIMENSION,
        label=LABEL,
        lens=LENS,
        confidence=CONFIDENCE,
        score=score,
        tier=config_module.TIER_LABELS[score],
        evidence=evidence,
        raw_metrics={"cost_conditions": len(matched), "enabled_conditions": len(enabled)},
        remediation=REMEDIATION[score],
    )
