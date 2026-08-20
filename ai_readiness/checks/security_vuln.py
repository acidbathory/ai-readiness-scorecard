"""Confidence: UNVERIFIED. No confirmed NerdGraph/NRQL shape for security or
vulnerability-management coverage exists anywhere in either reference repo --
this check tries two candidate query shapes and, if both fail, reports an
honest "Unknown" tier rather than a false "Absent" (a real account that
genuinely has zero vulnerability scanning should read as Absent; an account
where we simply guessed the wrong query should not look the same).
"""

from ..nerdgraph import NerdGraphError
from ..scoring import tier_from_count
from .base import CheckResult
from .. import config as config_module

DIMENSION = "security_vuln"
LABEL = "Security / vulnerability-management coverage"
LENS = "observability_for_ai"
CONFIDENCE = "unverified"
REMEDIATION = {
    0: "No vulnerability-management coverage detected. Enable New Relic's "
       "vulnerability management (Security RX / IAST) on your reporting services to "
       "get CVE and dependency-risk visibility.",
    1: "Some vulnerability scanning exists -- expand it to every AI-adjacent "
       "service. LLM-calling services often pull in fast-moving SDK dependencies "
       "(OpenAI/LangChain/etc.) with frequent CVEs, so partial coverage there is a "
       "real gap.",
    2: "Solid vulnerability coverage -- add alerting specifically on newly-disclosed "
       "critical/high CVEs in AI SDK dependencies, not just a general feed that's easy "
       "to tune out.",
    3: "Mature vulnerability management for standard CVEs. Extend the same rigor to "
       "LLM-specific risk classes vulnerability scanners don't cover -- prompt "
       "injection (OWASP LLM01), sensitive info disclosure (LLM06), and supply-chain "
       "risk in models/plugins (LLM05) -- via the OWASP LLM Top 10 as a checklist.",
}
REMEDIATION_UNKNOWN = (
    "Could not confirm a working vulnerability-management query shape on this "
    "account -- confirm Security RX / IAST is enabled and the user key has "
    "permission to read vulnerability data before trusting an Absent result here."
)

VULN_DOMAIN_QUERY = """
{ actor { entitySearch(query: "domain = 'VULN'") { count } } }
"""

NRAI_VULN_NRQL_QUERY = """
query($accountId: Int!, $nrql: Nrql!) {
  actor { account(id: $accountId) { nrql(query: $nrql) { results } } }
}
"""


def run(ctx):
    thresholds = ctx.config[DIMENSION]
    attempts = []

    count = None
    source = None

    try:
        data = ctx.gql(VULN_DOMAIN_QUERY, fixture_key="security_vuln.vuln_domain")
        count = data.get("actor", {}).get("entitySearch", {}).get("count", 0)
        source = "entitySearch(domain = 'VULN')"
    except NerdGraphError as exc:
        attempts.append(f"entitySearch(domain='VULN') failed: {exc}")

    if count is None:
        try:
            nrql = f"SELECT count(*) FROM NrAiVulnerability SINCE {ctx.lookback_days} days ago"
            data = ctx.gql(
                NRAI_VULN_NRQL_QUERY,
                {"accountId": ctx.account_id, "nrql": nrql},
                fixture_key="security_vuln.nrai_vuln",
            )
            results = data.get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])
            count = results[0].get("count", 0) if results else 0
            source = "NRQL FROM NrAiVulnerability"
        except NerdGraphError as exc:
            attempts.append(f"NRQL FROM NrAiVulnerability failed: {exc}")

    if count is None:
        evidence = (
            "Could not verify -- no confirmed NerdGraph/NRQL shape for "
            "security/vulnerability coverage exists in this codebase yet; "
            "needs confirming against a real account with Security "
            "RX/vulnerability management enabled. Attempts: " + "; ".join(attempts)
        )
        return CheckResult(
            dimension=DIMENSION,
            label=LABEL,
            lens=LENS,
            confidence=CONFIDENCE,
            score=None,
            tier=config_module.UNKNOWN_TIER_LABEL,
            evidence=evidence,
            raw_metrics={},
            error="both candidate queries failed",
            remediation=REMEDIATION_UNKNOWN,
        )

    score = tier_from_count(count, thresholds["min_scanned_entities_for_tier"])
    evidence = (
        f"{count} scanned entities/vulnerability records found via {source} "
        f"(UNVERIFIED query shape -- confirm against a real account)"
    )
    return CheckResult(
        dimension=DIMENSION,
        label=LABEL,
        lens=LENS,
        confidence=CONFIDENCE,
        score=score,
        tier=config_module.TIER_LABELS[score],
        evidence=evidence,
        raw_metrics={"scanned_count": count, "source": source},
        remediation=REMEDIATION[score],
    )
