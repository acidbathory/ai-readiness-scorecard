"""Human-readable table and JSON rendering. No `tabulate` dependency --
column widths computed in plain Python, matching the zero-dependency goal."""

import json

from . import config as config_module
from .scoring import tier_index_from_score


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
        header = f"{lens_label} (avg: {score if score is not None else 'n/a'} / 10)"
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

    lines.append(f"Overall AI Readiness score: {agg['overall_score']} / 10")
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
TIER_COLORS_BY_INDEX = {0: "#c0392b", 1: "#d68910", 2: "#2471a3", 3: "#1e8449"}

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


def _gauge(score_10, label):
    pct = max(0, min(100, score_10 * 10))
    color = TIER_COLORS_BY_INDEX[tier_index_from_score(score_10)]
    return f"""<div class="gauge-block">
      <div class="gauge-top"><span class="gauge-label">{_escape(label)}</span><span class="gauge-value">{score_10} / 10</span></div>
      <div class="gauge"><div class="gauge-fill" style="width:{pct}%;background:{color}"></div></div>
    </div>"""


def _dim_card(r):
    color = TIER_COLORS.get(r.tier, "#7f8c8d")
    return f"""<div class="dim-card">
      <div class="dim-card-header">
        <div><span class="dim-label">{_escape(r.label)}</span><div class="dim-key">{_escape(r.dimension)}</div></div>
        <div class="dim-card-badges">{_badge(r.tier)}<span class="pill">{_escape(r.confidence)}</span></div>
      </div>
      <p class="evidence">{_escape(r.evidence)}</p>
      <div class="action" style="border-left-color:{color}">
        <span class="action-icon">&#128161;</span>
        <div><strong>Recommended action:</strong> {_escape(r.remediation)}</div>
      </div>
    </div>"""


def render_html(results, agg, meta):
    generated_at = meta.get("generated_at", "")
    overall_score = agg["overall_score"]
    overall_tier = config_module.TIER_LABELS[tier_index_from_score(overall_score)]

    lens_gauges = "".join(
        _gauge(score, config_module.LENS_LABELS[lens]) for lens, score in agg["lens_scores"].items()
    )

    lens_sections = []
    for lens_key, lens_label in config_module.LENS_LABELS.items():
        lens_results = [r for r in results if r.lens == lens_key]
        if not lens_results:
            continue
        cards = "".join(_dim_card(r) for r in lens_results)
        lens_sections.append(f"<h2>{_escape(lens_label)}</h2><div class='dim-grid'>{cards}</div>")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AI Readiness Scorecard</title>
<style>
  :root {{
    --bg: #ffffff; --fg: #1c1c1c; --muted: #666; --card-bg: #fafafa;
    --card-border: #e2e2e2; --track: #ebebeb; --pill-bg: #eef0f2; --pill-fg: #445;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #14161a; --fg: #e8e8e8; --muted: #9a9a9a; --card-bg: #1c1f24;
      --card-border: #2c2f36; --track: #2a2d33; --pill-bg: #262a31; --pill-fg: #b8bfc8;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, Helvetica, Arial, sans-serif; margin: 2rem auto; max-width: 980px;
          padding: 0 1rem; color: var(--fg); background: var(--bg); }}
  h1 {{ margin-bottom: 0.2rem; }}
  h2 {{ margin-top: 2.2rem; border-bottom: 1px solid var(--card-border); padding-bottom: 0.4rem; }}
  .meta {{ color: var(--muted); font-size: 0.9rem; margin-bottom: 1.5rem; }}
  .summary {{ display: flex; gap: 1.5rem; align-items: flex-start; margin-bottom: 1.5rem; flex-wrap: wrap; }}
  .overall-block {{ min-width: 180px; }}
  .overall {{ font-size: 2.6rem; font-weight: 700; line-height: 1; }}
  .overall-label {{ color: var(--muted); font-size: 0.85rem; margin-top: 0.2rem; }}
  .gauge-block {{ min-width: 220px; flex: 1; }}
  .gauge-top {{ display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.3rem; }}
  .gauge-label {{ color: var(--muted); }}
  .gauge-value {{ font-weight: 600; }}
  .gauge {{ background: var(--track); border-radius: 6px; height: 10px; overflow: hidden; }}
  .gauge-fill {{ height: 100%; border-radius: 6px; }}
  .dim-grid {{ display: flex; flex-direction: column; gap: 0.9rem; margin-top: 1rem; }}
  .dim-card {{ background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 10px; padding: 1rem 1.2rem; }}
  .dim-card-header {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 0.75rem; flex-wrap: wrap; }}
  .dim-label {{ font-weight: 600; font-size: 1.02rem; }}
  .dim-key {{ font-weight: 400; color: var(--muted); font-size: 0.75rem; font-family: ui-monospace, monospace; }}
  .dim-card-badges {{ display: flex; gap: 0.4rem; align-items: center; white-space: nowrap; }}
  .badge {{ display: inline-block; color: white; border-radius: 12px; padding: 0.15rem 0.6rem; font-size: 0.8rem; font-weight: 600; }}
  .pill {{ display: inline-block; background: var(--pill-bg); color: var(--pill-fg); border-radius: 12px;
           padding: 0.15rem 0.6rem; font-size: 0.75rem; text-transform: capitalize; }}
  .evidence {{ font-size: 0.92rem; margin: 0.75rem 0; }}
  .action {{ display: flex; gap: 0.5rem; border-left: 3px solid #999; background: var(--track);
             border-radius: 0 6px 6px 0; padding: 0.5rem 0.75rem; font-size: 0.9rem; }}
  .action-icon {{ flex-shrink: 0; }}
  .legend {{ color: var(--muted); font-size: 0.8rem; border-top: 1px solid var(--card-border); padding-top: 1rem; margin-top: 2rem; }}
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
    <div class="overall-block">
      <div class="overall" style="color:{TIER_COLORS.get(overall_tier, '#7f8c8d')}">{overall_score} / 10</div>
      <div class="overall-label">Overall &middot; {_escape(overall_tier)}</div>
    </div>
    {lens_gauges}
  </div>
  {''.join(lens_sections)}
  <div class="legend">{CONFIDENCE_LEGEND}</div>
</body>
</html>
"""
