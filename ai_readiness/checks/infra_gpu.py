"""Confidence: HIGH for base infra host count (entitySearch count field, same
primitive as apm_coverage but no pagination needed since we only want the
total). The GPU sub-signal is best-effort: `gpuUtilizationPercent` is an
assumed SystemSample attribute name, unconfirmed against a real account --
if it errors, try the alternate `gpu.utilization` Metric-type name instead.
"""

from ..scoring import combine_tiers, tier_from_count
from .base import CheckResult
from .. import config as config_module

DIMENSION = "infra_gpu"
LABEL = "Infra coverage, incl. GPU visibility"
LENS = "observability_for_ai"
CONFIDENCE = "high"
REMEDIATION = {
    0: "Install the New Relic Infrastructure agent on your compute hosts. If you run "
       "GPU workloads, also add the NVIDIA DCGM integration (`nri-gpu`) so GPU "
       "utilization reports alongside CPU/memory.",
    1: "Infra hosts are reporting but GPU metrics aren't -- confirm the DCGM "
       "exporter is running on every GPU host and that `nri-gpu` is enabled in the "
       "Infrastructure agent config, not just installed.",
    2: "GPU visibility is decent -- add alert conditions on GPU memory/utilization "
       "saturation so capacity issues surface before they cause LLM inference latency spikes.",
    3: "Maintain GPU fleet visibility; correlate GPU utilization with LLM request "
       "volume/token throughput to right-size instance types per model rather than "
       "over-provisioning by default.",
}
REMEDIATION_UNKNOWN = (
    "Confirm the New Relic user key has entitySearch and NRQL read permission on "
    "this account for INFRA-domain entities."
)

HOSTS_QUERY = """
{ actor { entitySearch(query: "domain = 'INFRA' AND type = 'HOST' AND reporting = 'true'") { count } } }
"""

GPU_HOSTS_QUERY = """
query($accountId: Int!, $nrql: Nrql!) {
  actor { account(id: $accountId) { nrql(query: $nrql) { results } } }
}
"""


def run(ctx):
    thresholds = ctx.config[DIMENSION]

    hosts_data = ctx.gql(HOSTS_QUERY, fixture_key="infra_gpu.hosts")
    host_count = hosts_data.get("actor", {}).get("entitySearch", {}).get("count", 0)

    gpu_nrql = (
        f"SELECT uniqueCount(hostname) FROM SystemSample "
        f"WHERE gpuUtilizationPercent IS NOT NULL SINCE {ctx.lookback_days} days ago"
    )
    gpu_data = ctx.gql(
        GPU_HOSTS_QUERY,
        {"accountId": ctx.account_id, "nrql": gpu_nrql},
        fixture_key="infra_gpu.gpu_hosts",
    )
    gpu_results = gpu_data.get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])
    gpu_host_count = gpu_results[0].get("uniqueCount.hostname", 0) if gpu_results else 0

    host_tier = tier_from_count(host_count, thresholds["min_hosts_for_tier"])
    if host_count == 0:
        # Avoids a false "ad hoc" reading from a stray GPU signal with
        # nothing else instrumented.
        score = 0
    else:
        gpu_tier = tier_from_count(gpu_host_count, thresholds["min_gpu_hosts_for_tier"])
        score = combine_tiers(host_tier, gpu_tier, method="max")

    evidence = (
        f"{host_count} infra hosts reporting; {gpu_host_count} with GPU "
        f"utilization metrics (best-effort signal, attribute name unverified "
        f"against a real account)"
    )

    return CheckResult(
        dimension=DIMENSION,
        label=LABEL,
        lens=LENS,
        confidence=CONFIDENCE,
        score=score,
        tier=config_module.TIER_LABELS[score],
        evidence=evidence,
        raw_metrics={"host_count": host_count, "gpu_host_count": gpu_host_count},
        remediation=REMEDIATION[score],
    )
