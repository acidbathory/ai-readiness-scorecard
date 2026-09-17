"""Confidence: MEDIUM. entitySearch domain-filter mechanism is HIGH-confidence
proven (reference-repo-a/scripts/bootstrap.py:233), but the signal this check
counts on top of it -- the `aiEnabledApp` entity tag -- was confirmed live
against only one account (2026-08-20), so per the README's own confidence
legend that caps the dimension at MEDIUM until a second account confirms it.

`aiEnabledApp` is the same boolean tag the Catalog "AI Assets" filter is built
on, set by New Relic's own APM agents when they detect an AI SDK (openai,
langchain, etc.) in the instrumented process -- it replaces an earlier
name-pattern heuristic (`*ai*`/`*agent*`/`*model*` globs) that matched on
substrings and false-positived on ordinary service names like
`email-service` or `retail-checkout` (both contain "ai"). Tag coverage varies
by agent language -- a Java app has carried `ai`/`ai.name` without
`ai.capable` -- so the plain `aiEnabledApp` boolean is the safer filter for a
count than the dotted `ai.capable`/`ai.category`/`ai.name` tags (which are
richer but entitySearch-only, unconfirmed to flatten onto Transaction/Span
rows).

The tag proves the SDK was detected, not that AI calls are actually
happening -- an Azure Function app has carried `aiEnabledApp` with none of
the `ai.*` detail tags. `ai_monitoring` already counts entities emitting
`LlmChatCompletionSummary`/`gen_ai.*`, so the two dimensions together
distinguish "instrumented" from "actively calling an LLM". Needs full entity
list (not just count) for the evidence names, hence the pagination helper.
"""

from ..nerdgraph import paginated_entity_search
from ..scoring import tier_from_count
from .base import result_for

DIMENSION = "apm_coverage"
LABEL = "APM coverage of AI-adjacent services"
LENS = "observability_for_ai"
CONFIDENCE = "medium"
REMEDIATION = {
    0: "Install a New Relic APM agent (Python/Node/Java/.NET/Go/Ruby) on at least "
       "one AI-calling service -- the agent auto-detects AI SDKs (openai, langchain, "
       "etc.) and tags the entity `aiEnabledApp: true`, no manual naming needed.",
    1: "Expand APM instrumentation beyond the one pilot service -- instrument every "
       "microservice that calls an LLM or serves model inference, not just the entry point.",
    2: "Most AI-adjacent services are tagged -- audit the untagged ones: either the "
       "APM agent version predates AI-SDK detection, or the service genuinely isn't "
       "calling an LLM yet.",
    3: "Add a CI check that fails a deploy if a new service under an AI-workload "
       "directory ships without APM instrumentation, so coverage doesn't silently regress "
       "as the fleet grows.",
}
REMEDIATION_UNKNOWN = (
    "Confirm the New Relic user key has entitySearch read permission on this account, "
    "and that at least one APM-reporting entity exists."
)

TOTAL_QUERY = """
query($query: String!) {
  actor { entitySearch(query: $query) { count } }
}
"""

QUERY = """
query($query: String!, $cursor: String) {
  actor {
    entitySearch(query: $query) {
      results(cursor: $cursor) {
        entities { guid name }
        nextCursor
      }
    }
  }
}
"""


def run(ctx):
    thresholds = ctx.config[DIMENSION]
    base_filter = f"domain = 'APM' AND reporting = 'true' AND accountId = {ctx.account_id}"

    total_data = ctx.gql(TOTAL_QUERY, {"query": base_filter}, fixture_key="apm_coverage.total")
    total_count = total_data.get("actor", {}).get("entitySearch", {}).get("count", 0)

    tagged_filter = f"{base_filter} AND tags.aiEnabledApp = 'true'"
    matched = paginated_entity_search(
        ctx.gql, QUERY, variables={"query": tagged_filter}, fixture_key="apm_coverage.entities"
    )

    score = tier_from_count(len(matched), thresholds["min_entities_for_tier"])
    names_preview = ", ".join(e["name"] for e in matched[:5])
    if len(matched) > 5:
        names_preview += ", ..."
    evidence = (
        f"{len(matched)} of {total_count} reporting APM services tagged `aiEnabledApp`"
        + (f" ({names_preview})" if matched else "")
    )

    return result_for(
        DIMENSION, LABEL, LENS, CONFIDENCE, REMEDIATION, score, evidence,
        raw_metrics={"total_apm_entities": total_count, "ai_adjacent_matches": len(matched)},
    )
