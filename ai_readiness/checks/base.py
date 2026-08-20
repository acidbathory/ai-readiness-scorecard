"""The per-check isolation contract: every check module exposes DIMENSION/
LABEL/LENS/CONFIDENCE constants and a run(ctx) -> CheckResult function.
run_check() wraps that call so one check's failure (expected for the two
UNVERIFIED dimensions) produces a single "Unknown" row instead of crashing
the whole scorecard.
"""

from dataclasses import dataclass, field

from .. import config as config_module


@dataclass
class Context:
    gql: object  # callable: (query, variables=None, fixture_key=None) -> dict
    account_id: int
    lookback_days: int
    config: dict


@dataclass
class CheckResult:
    dimension: str
    label: str
    lens: str
    confidence: str
    score: object  # int 0-3, or None if the check could not run
    tier: str
    evidence: str
    raw_metrics: dict = field(default_factory=dict)
    error: object = None  # str or None
    remediation: str = ""


def run_check(check_module, ctx):
    try:
        return check_module.run(ctx)
    except Exception as exc:  # noqa: BLE001 -- deliberate catch-all seam
        return CheckResult(
            dimension=check_module.DIMENSION,
            label=check_module.LABEL,
            lens=check_module.LENS,
            confidence=check_module.CONFIDENCE,
            score=None,
            tier=config_module.UNKNOWN_TIER_LABEL,
            evidence=f"Check failed: {exc}",
            error=str(exc),
            remediation=getattr(check_module, "REMEDIATION", ""),
        )
