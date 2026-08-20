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
    only dimensions with a non-None score (a failed/"Unknown" check doesn't
    silently drag the average toward zero)."""
    by_lens = {}
    for r in results:
        if r.score is None:
            continue
        by_lens.setdefault(r.lens, []).append(r.score)

    raw_lens_scores = {
        lens: sum(scores) / len(scores) for lens, scores in by_lens.items()
    }
    raw_overall = (
        sum(raw_lens_scores.values()) / len(raw_lens_scores) if raw_lens_scores else 0.0
    )
    lens_scores = {lens: round(v * SCALE, 1) for lens, v in raw_lens_scores.items()}
    overall = round(raw_overall * SCALE, 1)
    return {"lens_scores": lens_scores, "overall_score": overall}


def tier_index_from_score(score_10):
    """Inverse of SCALE, for the one place a 0-10 display score needs to map
    back to a 0-3 tier (e.g. to pick a badge color)."""
    return max(0, min(3, round(score_10 * 3 / 10)))
