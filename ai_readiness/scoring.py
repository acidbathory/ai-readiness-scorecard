"""Pure functions, no I/O -- the easiest module to unit-test in isolation."""


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
    """results: list of CheckResult. Returns {lens_scores, overall_score},
    averaging only dimensions with a non-None score (a failed/"Unknown"
    check doesn't silently drag the average toward zero)."""
    by_lens = {}
    for r in results:
        if r.score is None:
            continue
        by_lens.setdefault(r.lens, []).append(r.score)

    lens_scores = {
        lens: round(sum(scores) / len(scores), 2) for lens, scores in by_lens.items()
    }
    overall = (
        round(sum(lens_scores.values()) / len(lens_scores), 2) if lens_scores else 0.0
    )
    return {"lens_scores": lens_scores, "overall_score": overall}
