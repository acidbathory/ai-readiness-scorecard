"""Confidence: UNVERIFIED. Langfuse's core differentiator vs plain LLM
logging: Scores/Evaluations/Datasets -- is anyone capturing whether the AI's
outputs were actually good (human or LLM-as-judge feedback), not just that a
call happened? Maps to New Relic's `LlmFeedbackMessage` event type, which is
a real documented AI Monitoring event type per New Relic's own docs, but was
never observed populated on the one live account this scorecard has been
tested against (zero events, query itself did not error). Follows the same
honest-Unknown-on-error pattern as security_vuln.py: a query failure means
"couldn't verify," not a false "Absent".
"""

from ..nerdgraph import NerdGraphError
from ..scoring import tier_from_count
from .base import CheckResult
from .. import config as config_module

DIMENSION = "ai_quality_feedback"
LABEL = "AI quality & feedback-loop coverage"
LENS = "observability_for_ai"
CONFIDENCE = "unverified"
REMEDIATION = (
    "Capture feedback on AI outputs (thumbs up/down, human review, or an "
    "LLM-as-judge score) and send it via New Relic's LLM feedback API so quality "
    "issues surface as data, not anecdotes."
)

NRQL_QUERY = """
query($accountId: Int!, $nrql: Nrql!) {
  actor { account(id: $accountId) { nrql(query: $nrql) { results } } }
}
"""


def run(ctx):
    thresholds = ctx.config[DIMENSION]

    try:
        nrql = f"SELECT count(*) FROM LlmFeedbackMessage SINCE {ctx.lookback_days} days ago"
        data = ctx.gql(
            NRQL_QUERY,
            {"accountId": ctx.account_id, "nrql": nrql},
            fixture_key="ai_quality_feedback.events",
        )
        results = data.get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])
        count = results[0].get("count", 0) if results else 0
    except NerdGraphError as exc:
        return CheckResult(
            dimension=DIMENSION,
            label=LABEL,
            lens=LENS,
            confidence=CONFIDENCE,
            score=None,
            tier=config_module.UNKNOWN_TIER_LABEL,
            evidence=(
                f"Could not verify -- LlmFeedbackMessage query failed: {exc}. This is a "
                f"real documented NR event type per our own knowledge, but has never been "
                f"confirmed populated on any account we've tested."
            ),
            raw_metrics={},
            error=str(exc),
            remediation=REMEDIATION,
        )

    score = tier_from_count(count, thresholds["min_feedback_events_for_tier"])
    evidence = f"{count} LlmFeedbackMessage events over {ctx.lookback_days}d"

    return CheckResult(
        dimension=DIMENSION,
        label=LABEL,
        lens=LENS,
        confidence=CONFIDENCE,
        score=score,
        tier=config_module.TIER_LABELS[score],
        evidence=evidence,
        raw_metrics={"feedback_event_count": count},
        remediation=REMEDIATION,
    )
