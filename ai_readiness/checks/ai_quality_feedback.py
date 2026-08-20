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
REMEDIATION = {
    0: "No AI output feedback captured. Start simple: add a thumbs up/down on AI "
       "responses in your product UI and send it to New Relic via the LLM feedback "
       "API (`recordLlmFeedbackEvent` or your SDK's equivalent).",
    1: "Feedback capture exists but is sparse -- increase coverage (sample a higher "
       "% of responses) or add automatic LLM-as-judge scoring for responses with no "
       "human feedback.",
    2: "Feedback volume is solid -- start correlating scores against `request.model` "
       "/ prompt version so a regression in one specific model or prompt is catchable, "
       "not hidden inside an aggregate average.",
    3: "Mature feedback loop -- gate prompt/model changes on a regression test suite "
       "(e.g. a promptfoo-style CI eval) before they ship, using this feedback data as "
       "the baseline.",
}
REMEDIATION_UNKNOWN = (
    "Confirm the New Relic user key has NRQL read permission on this account and "
    "that the `LlmFeedbackMessage` event type is queryable."
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
            remediation=REMEDIATION_UNKNOWN,
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
        remediation=REMEDIATION[score],
    )
