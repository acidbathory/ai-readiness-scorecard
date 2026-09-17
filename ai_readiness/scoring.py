"""Pure functions, no I/O -- the easiest module to unit-test in isolation."""

SCALE = 10.0 / 3.0  # internal tiers are 0-3; displayed lens/overall scores are 0-10


def tier_from_count(count, thresholds):
    """thresholds: {1: n1, 2: n2, 3: n3} mapping tier -> minimum count.
    Returns the highest tier whose minimum is met, or 0 if none/count is None.
    """
    tier = 0
    if count is None:
        return tier
    for t in sorted(thresholds):
        if count >= thresholds[t]:
            tier = t
    return tier


def combine_tiers(*tiers, method="min"):
    tiers = [t for t in tiers if t is not None]
    if not tiers:
        return 0
    return min(tiers) if method == "min" else max(tiers)


def aggregate(results):
    """results: list of CheckResult. Returns {lens_scores, overall_score} on a
    0-10 scale (internal tiers are 0-3; SCALE converts for display), averaging
    only dimensions with a non-None score (a failed/"Unknown" or not-
    applicable check doesn't silently drag the average toward zero).

    Also returns scored_count/total_count (and the same breakdown per lens in
    lens_counts) -- how many of the dimensions actually contributed a number,
    vs. how many exist. A run where most dimensions came back Unknown (e.g. a
    user key that can only read one NerdGraph capability) would otherwise
    render identically to a full, confident run: same-shaped lens_scores and
    overall_score, just averaged over far fewer inputs.

    Known scoring-model tradeoff, deliberately not "fixed" here since there's
    no single obviously-correct answer: overall_score averages the two LENS
    means, not a flat average across all 15 dimensions. That equalizes the
    two lenses' influence on the headline regardless of how many dimensions
    each has -- but since observability_for_ai currently has 8 dimensions and
    ai_for_observability has 7, each individual ai_for_observability dimension
    (e.g. ai_change_tracking) ends up with slightly more per-dimension weight
    on the headline than each observability_for_ai dimension (e.g. ai_monitoring).
    Dimensions within a lens are also correlated rather than independent --
    one missing capability (no LLM telemetry at all) can zero out several
    related dimensions at once, so the average isn't quite 8 (or 6)
    independent signals either. Both are real properties of "one score across
    14 correlated, unevenly-distributed signals," not bugs; changing them is
    a scoring-philosophy decision (flat 14-way average? per-dimension manual
    weights? something else?) that needs a human call, not a silent default
    picked here."""
    by_lens = {}
    lens_counts = {}
    for r in results:
        counts = lens_counts.setdefault(r.lens, {"scored": 0, "total": 0})
        counts["total"] += 1
        if r.score is None:
            continue
        counts["scored"] += 1
        by_lens.setdefault(r.lens, []).append(r.score)

    raw_lens_scores = {
        lens: sum(scores) / len(scores) for lens, scores in by_lens.items()
    }
    raw_overall = (
        sum(raw_lens_scores.values()) / len(raw_lens_scores) if raw_lens_scores else 0.0
    )
    lens_scores = {lens: round(v * SCALE, 1) for lens, v in raw_lens_scores.items()}
    overall = round(raw_overall * SCALE, 1)
    return {
        "lens_scores": lens_scores,
        "overall_score": overall,
        "scored_count": sum(c["scored"] for c in lens_counts.values()),
        "total_count": sum(c["total"] for c in lens_counts.values()),
        "lens_counts": lens_counts,
    }


def tier_index_from_score(score_10):
    """Inverse of SCALE, for the one place a 0-10 display score needs to map
    back to a 0-3 tier (e.g. to pick a badge color)."""
    return max(0, min(3, round(score_10 * 3 / 10)))
