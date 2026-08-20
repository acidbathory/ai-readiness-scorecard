"""Confidence: HIGH. Dashboard entitySearch shape confirmed
(continental-demo/dashboard/deploy_dashboard.py:216-217,
scripts/bootstrap.py:233). Log volume via bytecountestimate() lifted from
deploy_dashboard.py's cost page. Both signals must be present to score above
"Ad hoc" (combine via min) -- a customer with dashboards but no real log
volume, or vice versa, isn't "Managed" on this dimension.
"""

from ..scoring import combine_tiers, tier_from_count
from .base import CheckResult
from .. import config as config_module

DIMENSION = "dashboards_logs"
LABEL = "Dashboard & log coverage"
LENS = "ai_for_observability"
CONFIDENCE = "high"
REMEDIATION = {
    0: "No dashboards or meaningful log volume detected. Build one single-pane "
       "dashboard covering the AI workload's golden signals, and confirm logs are "
       "actually being forwarded (check the log forwarder/agent config).",
    1: "Dashboards or log volume exist but not both at a meaningful level -- check "
       "the evidence above for which one is missing and fix that first, since this "
       "dimension needs both to score above Ad hoc.",
    2: "Solid dashboard/log coverage -- add a saved view or alert for log-based "
       "error patterns specific to the AI workload (e.g. rate-limit errors, "
       "context-length-exceeded errors).",
    3: "Mature observability hygiene -- periodically audit dashboards for "
       "staleness (unused widgets, queries broken by a schema change) rather than "
       "letting them accumulate indefinitely.",
}
REMEDIATION_UNKNOWN = (
    "Confirm the New Relic user key has entitySearch and NRQL read permission on "
    "this account for DASHBOARD entities and Log data."
)

DASHBOARDS_QUERY = """
query($query: String!) {
  actor { entitySearch(query: $query) { count } }
}
"""

NRQL_QUERY = """
query($accountId: Int!, $nrql: Nrql!) {
  actor { account(id: $accountId) { nrql(query: $nrql) { results } } }
}
"""


def run(ctx):
    thresholds = ctx.config[DIMENSION]

    dash_data = ctx.gql(
        DASHBOARDS_QUERY,
        {"query": f"type = 'DASHBOARD' AND accountId = {ctx.account_id}"},
        fixture_key="dashboards_logs.dashboards",
    )
    dashboard_count = dash_data.get("actor", {}).get("entitySearch", {}).get("count", 0)

    log_volume_nrql = f"SELECT bytecountestimate()/1e9 AS 'GB' FROM Log SINCE {ctx.lookback_days} days ago"
    log_data = ctx.gql(
        NRQL_QUERY,
        {"accountId": ctx.account_id, "nrql": log_volume_nrql},
        fixture_key="dashboards_logs.log_volume",
    )
    log_results = log_data.get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])
    total_gb = log_results[0].get("GB", 0) if log_results else 0
    gb_per_day = total_gb / ctx.lookback_days if ctx.lookback_days else 0

    entities_nrql = f"SELECT uniqueCount(entity.guid) FROM Log SINCE {ctx.lookback_days} days ago"
    entities_data = ctx.gql(
        NRQL_QUERY,
        {"accountId": ctx.account_id, "nrql": entities_nrql},
        fixture_key="dashboards_logs.log_entities",
    )
    entities_results = entities_data.get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])
    log_entity_count = entities_results[0].get("uniqueCount.entity.guid", 0) if entities_results else 0

    dash_tier = tier_from_count(dashboard_count, thresholds["min_dashboards_for_tier"])
    log_tier = tier_from_count(gb_per_day, thresholds["min_log_gb_per_day_for_tier"])
    score = combine_tiers(dash_tier, log_tier, method="min")

    evidence = (
        f"{dashboard_count} dashboards found; log volume ~{gb_per_day:.2f} GB/day "
        f"across {log_entity_count} entities over the last {ctx.lookback_days} days"
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
            "dashboard_count": dashboard_count,
            "log_gb_per_day": round(gb_per_day, 3),
            "log_entity_count": log_entity_count,
        },
        remediation=REMEDIATION[score],
    )
