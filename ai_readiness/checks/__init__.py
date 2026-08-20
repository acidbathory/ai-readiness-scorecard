from . import (
    ai_agent_tracing,
    ai_monitoring,
    ai_quality_feedback,
    alerting_anomaly,
    apm_coverage,
    autopilot,
    dashboards_logs,
    infra_gpu,
    security_vuln,
    workflow_automation,
)

# Order here is the report/display order: Observability for AI first,
# then AI for Observability.
ALL_CHECKS = [
    apm_coverage,
    infra_gpu,
    ai_monitoring,
    ai_agent_tracing,
    ai_quality_feedback,
    security_vuln,
    workflow_automation,
    autopilot,
    alerting_anomaly,
    dashboards_logs,
]

CHECKS_BY_DIMENSION = {c.DIMENSION: c for c in ALL_CHECKS}
