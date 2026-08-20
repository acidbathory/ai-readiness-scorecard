"""Confidence: HIGH. entitySearch domain-filter mechanism is proven
(continental-demo/scripts/bootstrap.py:233), domain-based filtering (vs
name-based) is new but the same primitive. Needs full entity list (not just
count) to locally pattern-match names, hence the pagination helper.
"""

from fnmatch import fnmatch

from ..nerdgraph import paginated_entity_search
from ..scoring import tier_from_count
from .base import CheckResult

DIMENSION = "apm_coverage"
LABEL = "APM coverage of AI-adjacent services"
LENS = "observability_for_ai"
CONFIDENCE = "high"
REMEDIATION = (
    "Instrument AI-adjacent services with a New Relic APM agent and name/tag them "
    "so they're identifiable as part of the AI workload, not just generic services."
)

QUERY = """
query($cursor: String) {
  actor {
    entitySearch(query: "domain = 'APM' AND reporting = 'true'") {
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
    entities = paginated_entity_search(ctx.gql, QUERY, fixture_key="apm_coverage.entities")
    patterns = thresholds["ai_adjacent_patterns"]
    matched = [
        e for e in entities
        if any(fnmatch((e.get("name") or "").lower(), p) for p in patterns)
    ]
    score = tier_from_count(len(matched), thresholds["min_entities_for_tier"])
    names_preview = ", ".join(e["name"] for e in matched[:5])
    if len(matched) > 5:
        names_preview += ", ..."
    evidence = (
        f"{len(matched)} of {len(entities)} reporting APM services match "
        f"AI-adjacent name patterns"
        + (f" ({names_preview})" if matched else "")
    )
    from .. import config as config_module

    return CheckResult(
        dimension=DIMENSION,
        label=LABEL,
        lens=LENS,
        confidence=CONFIDENCE,
        score=score,
        tier=config_module.TIER_LABELS[score],
        evidence=evidence,
        raw_metrics={"total_apm_entities": len(entities), "ai_adjacent_matches": len(matched)},
        remediation=REMEDIATION,
    )
