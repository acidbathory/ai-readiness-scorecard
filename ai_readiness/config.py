"""Every tunable number lives here, not scattered through checks/. Override
via `--config overrides.json` (deep-merged onto THRESHOLDS by cli.py) since
thresholds will need tuning per real customer and other SCs will reuse this.
"""

import hashlib
import json

LOOKBACK_DAYS_DEFAULT = 30

TIER_LABELS = {0: "Absent", 1: "Ad hoc", 2: "Managed", 3: "Optimized"}
UNKNOWN_TIER_LABEL = "Unknown"  # the check couldn't run/measure -- distinct from N/A below
NOT_APPLICABLE_TIER_LABEL = "Not Applicable"  # the check ran fine; there was nothing to measure

LENS_LABELS = {
    "observability_for_ai": "Observability for AI",
    "ai_for_observability": "AI for Observability",
}

THRESHOLDS = {
    "ai_monitoring": {
        "min_events_for_tier": {1: 100, 2: 5_000, 3: 50_000},
        "min_entities_for_tier": {1: 1, 2: 3, 3: 8},
        "min_token_visibility_pct_for_tier": {1: 1, 2: 50, 3: 90},
    },
    "ai_agent_tracing": {
        "min_tool_call_events_for_tier": {1: 1, 2: 100, 3: 1_000},
        "min_vector_search_events_for_tier": {1: 1, 2: 100, 3: 1_000},
    },
    "ai_quality_feedback": {
        "min_feedback_events_for_tier": {1: 1, 2: 25, 3: 200},
    },
    "human_approval_gates": {
        "min_gate_coverage_pct_for_tier": {1: 1, 2: 50, 3: 90},
    },
    "model_vendor_diversity": {
        "min_vendor_count_for_tier": {1: 1, 2: 2, 3: 3},
    },
    "ai_cost_governance": {
        "min_cost_conditions_for_tier": {1: 1, 2: 2, 3: 4},
    },
    "ai_change_tracking": {
        "min_ai_change_events_for_tier": {1: 1, 2: 3, 3: 8},
    },
    "apm_coverage": {
        "min_entities_for_tier": {1: 1, 2: 3, 3: 8},
    },
    "infra_gpu": {
        "min_hosts_for_tier": {1: 1, 2: 5, 3: 20},
        "min_gpu_hosts_for_tier": {1: 1, 2: 2, 3: 5},
    },
    "security_vuln": {
        "min_scanned_entities_for_tier": {1: 1, 2: 5, 3: 20},
    },
    "workflow_automation": {
        "min_workflows_for_tier": {1: 1, 2: 3, 3: 6},
    },
    "autopilot": {
        "min_autopilot_workflows_for_tier": {1: 1, 2: 2, 3: 4},
    },
    "alerting_anomaly": {
        "min_conditions_for_tier": {1: 1, 2: 5, 3: 15},
    },
    "dashboards_logs": {
        "min_dashboards_for_tier": {1: 1, 2: 3, 3: 6},
        "min_log_gb_per_day_for_tier": {1: 0.01, 2: 1, 3: 10},
    },
    "ai_coding_observability": {
        # No live-confirmed baseline yet -- placeholder numbers borrowed from
        # ai_agent_tracing's tool-call thresholds, the closest already-tuned
        # "event count over the lookback window" shape in this codebase.
        "min_tool_call_events_for_tier": {1: 1, 2: 100, 3: 1_000},
    },
}


def deep_merge(base, overrides):
    """Recursively merge `overrides` onto a copy of `base`. Dict values merge
    key-by-key; any other value type is replaced outright."""
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def config_fingerprint(thresholds):
    """Short, stable hash of the exact thresholds a run used -- so two
    scorecards from two engagements can be compared knowing whether they were
    scored against the same rules, without diffing every number by hand. Any
    `--config overrides.json` changes this; the default THRESHOLDS always
    hashes to the same value."""
    canonical = json.dumps(thresholds, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]
