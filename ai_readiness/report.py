"""Human-readable table and JSON rendering. No `tabulate` dependency --
column widths computed in plain Python, matching the zero-dependency goal."""

import json

from . import config as config_module


def render_table(results, agg, meta):
    lines = []
    lines.append(
        f"AI Readiness Scorecard -- account {meta['account_id']} ({meta['region']}), "
        f"lookback {meta['lookback_days']}d"
    )
    lines.append("")

    for lens_key, lens_label in config_module.LENS_LABELS.items():
        lens_results = [r for r in results if r.lens == lens_key]
        if not lens_results:
            continue
        score = agg["lens_scores"].get(lens_key)
        header = f"{lens_label} (avg: {score if score is not None else 'n/a'})"
        lines.append(header)
        lines.append("-" * len(header))

        dim_w = max(len(r.dimension) for r in lens_results)
        tier_w = max(len(r.tier) for r in lens_results)
        for r in lens_results:
            conf = f"[{r.confidence}]"
            lines.append(
                f"  {r.dimension.ljust(dim_w)}  {r.tier.ljust(tier_w)}  {conf:12s}  {r.evidence}"
            )
        lines.append("")

    lines.append(f"Overall AI Readiness score: {agg['overall_score']} / 3")
    return "\n".join(lines)


def render_json(results, agg, meta):
    payload = {
        "meta": meta,
        "dimensions": [
            {
                "dimension": r.dimension,
                "label": r.label,
                "lens": r.lens,
                "confidence": r.confidence,
                "score": r.score,
                "tier": r.tier,
                "evidence": r.evidence,
                "raw_metrics": r.raw_metrics,
                "error": r.error,
                "remediation": r.remediation,
            }
            for r in results
        ],
        "lens_scores": agg["lens_scores"],
        "overall_score": agg["overall_score"],
    }
    return json.dumps(payload, indent=2)


TIER_COLORS = {
    "Absent": "#c0392b",
    "Ad hoc": "#d68910",
    "Managed": "#2471a3",
    "Optimized": "#1e8449",
    config_module.UNKNOWN_TIER_LABEL: "#7f8c8d",
}

CONFIDENCE_LEGEND = (
    "high = query shape confirmed against a working reference pattern &middot; "
    "medium = confirmed primitive + an unverified heuristic layered on top &middot; "
    "unverified = no prior art; if this shows Unknown, the query shape needs "
    "confirming against a real account, not treated as Absent"
)


def _escape(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _badge(tier):
    color = TIER_COLORS.get(tier, "#7f8c8d")
    return f'<span class="badge" style="background:{color}">{_escape(tier)}</span>'


def _lens_table(lens_results):
    rows = []
    for r in lens_results:
        rows.append(
            "<tr>"
            f"<td class='dim'>{_escape(r.label)}<div class='dim-key'>{_escape(r.dimension)}</div></td>"
            f"<td>{_badge(r.tier)}</td>"
            f"<td class='conf'>{_escape(r.confidence)}</td>"
            f"<td>{_escape(r.evidence)}</td>"
            f"<td>{_escape(r.remediation)}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Dimension</th><th>Tier</th><th>Confidence</th><th>Evidence</th><th>Remediation</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def render_html(results, agg, meta):
    generated_at = meta.get("generated_at", "")
    overall_tier = config_module.TIER_LABELS.get(
        round(agg["overall_score"]), config_module.UNKNOWN_TIER_LABEL
    )

    lens_summary_cards = "".join(
        f"<div class='card'><div class='card-label'>{_escape(config_module.LENS_LABELS[lens])}</div>"
        f"<div class='card-score'>{score}</div></div>"
        for lens, score in agg["lens_scores"].items()
    )

    lens_sections = []
    for lens_key, lens_label in config_module.LENS_LABELS.items():
        lens_results = [r for r in results if r.lens == lens_key]
        if not lens_results:
            continue
        lens_sections.append(f"<h2>{_escape(lens_label)}</h2>" + _lens_table(lens_results))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AI Readiness Scorecard</title>
<style>
  body {{ font-family: -apple-system, Helvetica, Arial, sans-serif; margin: 2rem auto; max-width: 960px; color: #1c1c1c; }}
  h1 {{ margin-bottom: 0.2rem; }}
  .meta {{ color: #666; font-size: 0.9rem; margin-bottom: 1.5rem; }}
  .summary {{ display: flex; gap: 1rem; align-items: center; margin-bottom: 2rem; flex-wrap: wrap; }}
  .overall {{ font-size: 2.5rem; font-weight: 700; }}
  .overall-label {{ color: #666; font-size: 0.9rem; }}
  .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 0.75rem 1rem; min-width: 160px; }}
  .card-label {{ font-size: 0.8rem; color: #666; }}
  .card-score {{ font-size: 1.4rem; font-weight: 600; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 2rem; }}
  th, td {{ text-align: left; padding: 0.5rem 0.6rem; border-bottom: 1px solid #eee; vertical-align: top; font-size: 0.9rem; }}
  th {{ color: #666; font-weight: 600; font-size: 0.8rem; text-transform: uppercase; }}
  .dim {{ font-weight: 600; }}
  .dim-key {{ font-weight: 400; color: #999; font-size: 0.75rem; }}
  .conf {{ text-transform: capitalize; }}
  .badge {{ display: inline-block; color: white; border-radius: 12px; padding: 0.15rem 0.6rem; font-size: 0.8rem; font-weight: 600; white-space: nowrap; }}
  .legend {{ color: #888; font-size: 0.8rem; border-top: 1px solid #eee; padding-top: 1rem; }}
</style>
</head>
<body>
  <h1>AI Readiness Scorecard</h1>
  <div class="meta">
    Account {_escape(meta.get('account_id'))} ({_escape(meta.get('region'))}) &middot;
    lookback {_escape(meta.get('lookback_days'))}d
    {f"&middot; generated {_escape(generated_at)}" if generated_at else ""}
  </div>
  <div class="summary">
    <div>
      <div class="overall" style="color:{TIER_COLORS.get(overall_tier, '#7f8c8d')}">{agg['overall_score']} / 3</div>
      <div class="overall-label">Overall &middot; {_escape(overall_tier)}</div>
    </div>
    {lens_summary_cards}
  </div>
  {''.join(lens_sections)}
  <div class="legend">{CONFIDENCE_LEGEND}</div>
</body>
</html>
"""
