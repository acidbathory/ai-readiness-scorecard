"""Canned NerdGraph responses keyed by fixture_key, for --mock mode. Three
scenarios exercise the full tier range end-to-end without ever touching a
real account:

  none    -- every dimension should score 0/Absent
  mature  -- every dimension should score 3/Optimized
  partial -- a deliberate mix across tiers 1-2; also the only scenario where
             apm_coverage.entities is a *list* of page dicts, exercising the
             entitySearch pagination cursor loop (untested by either
             reference repo, so it needs its own fixture).
"""


def _apm_page(entities, next_cursor=None):
    return {"actor": {"entitySearch": {"results": {"entities": entities, "nextCursor": next_cursor}}}}


def _entity_count(n):
    return {"actor": {"entitySearch": {"count": n}}}


def _nrql_results(results):
    return {"actor": {"account": {"nrql": {"results": results}}}}


def _workflows(names, next_cursor=None):
    """Matches the confirmed live shape: workflows(cursor:) returns
    { nextCursor, results: [{ definition: { name } }] } -- there is no
    `enabled` field anywhere on a workflow definition."""
    return {
        "actor": {
            "account": {
                "workflowAutomation": {
                    "workflows": {
                        "nextCursor": next_cursor,
                        "results": [{"definition": {"name": n}} for n in names],
                    }
                }
            }
        }
    }


def _workflow_yaml(yaml_text):
    return {"actor": {"account": {"workflowAutomation": {"workflow": {"definition": {"yaml": yaml_text}}}}}}


def _alert_conditions(conditions):
    return {
        "actor": {
            "account": {
                "alerts": {
                    "nrqlConditionsSearch": {
                        "totalCount": len(conditions),
                        "nrqlConditions": conditions,
                    }
                }
            }
        }
    }


NONE = {
    "apm_coverage.entities": _apm_page([]),
    "infra_gpu.hosts": _entity_count(0),
    "infra_gpu.gpu_hosts": _nrql_results([{"uniqueCount.hostname": 0}]),
    "ai_monitoring.events": _nrql_results([{"count": 0}]),
    "ai_monitoring.entities": _nrql_results([{"uniqueCount.entity.guid": 0}]),
    "ai_monitoring.token_visibility": _nrql_results([{"percentage": 0}]),
    "ai_agent_tracing.tool_calls": _nrql_results([{"count": 0}]),
    "ai_agent_tracing.vector_search": _nrql_results([{"count": 0}]),
    "ai_quality_feedback.events": _nrql_results([{"count": 0}]),
    "security_vuln.vuln_domain": _entity_count(0),
    "security_vuln.nrai_vuln": _nrql_results([{"count": 0}]),
    "workflow_automation.workflows": _workflows([]),
    "alerting_anomaly.conditions": _alert_conditions([]),
    "dashboards_logs.dashboards": _entity_count(0),
    "dashboards_logs.log_volume": _nrql_results([{"GB": 0}]),
    "dashboards_logs.log_entities": _nrql_results([{"uniqueCount.entity.guid": 0}]),
}

_PARTIAL_WORKFLOW_NAMES = ["wf-a", "wf-b", "wf-c", "wf-d"]

PARTIAL = {
    "apm_coverage.entities": [
        _apm_page(
            [
                {"guid": "a1", "name": "orders-service"},
                {"guid": "a2", "name": "ai-recommender"},
                {"guid": "a3", "name": "billing-service"},
                {"guid": "a4", "name": "agent-scheduler"},
                {"guid": "a5", "name": "shipping-service"},
            ],
            next_cursor="page2",
        ),
        _apm_page(
            [
                {"guid": "a6", "name": "rag-search"},
                {"guid": "a7", "name": "catalog-service"},
                {"guid": "a8", "name": "user-service"},
            ]
        ),
    ],
    "infra_gpu.hosts": _entity_count(6),
    "infra_gpu.gpu_hosts": _nrql_results([{"uniqueCount.hostname": 1}]),
    "ai_monitoring.events": _nrql_results([{"count": 1200}]),
    "ai_monitoring.entities": _nrql_results([{"uniqueCount.entity.guid": 2}]),
    "ai_monitoring.token_visibility": _nrql_results([{"percentage": 45}]),
    "ai_agent_tracing.tool_calls": _nrql_results([{"count": 150}]),
    "ai_agent_tracing.vector_search": _nrql_results([{"count": 5}]),
    "ai_quality_feedback.events": _nrql_results([{"count": 10}]),
    "security_vuln.vuln_domain": _entity_count(3),
    "security_vuln.nrai_vuln": _nrql_results([{"count": 3}]),
    "workflow_automation.workflows": _workflows(_PARTIAL_WORKFLOW_NAMES),
    "autopilot.yaml::wf-a": _workflow_yaml("steps:\n  - action: newrelic.autopilot.run\n"),
    "autopilot.yaml::wf-b": _workflow_yaml("# uses autopilot for RCA\nsteps: []\n"),
    "autopilot.yaml::wf-c": _workflow_yaml("steps:\n  - action: http.post\n"),
    "autopilot.yaml::wf-d": _workflow_yaml("steps:\n  - action: slack.chat.postMessage\n"),
    "alerting_anomaly.conditions": _alert_conditions(
        [
            {"id": str(i), "name": f"condition-{i}", "enabled": True,
             "type": "BASELINE" if i in (1, 2) else "STATIC"}
            for i in range(1, 8)
        ]
    ),
    "dashboards_logs.dashboards": _entity_count(4),
    "dashboards_logs.log_volume": _nrql_results([{"GB": 45}]),
    "dashboards_logs.log_entities": _nrql_results([{"uniqueCount.entity.guid": 15}]),
}

_MATURE_WORKFLOW_NAMES = [f"wf-{i}" for i in range(1, 8)]

MATURE = {
    "apm_coverage.entities": _apm_page(
        [
            {"guid": "g1", "name": "checkout-service"},
            {"guid": "g2", "name": "llm-gateway"},
            {"guid": "g3", "name": "rag-retriever"},
            {"guid": "g4", "name": "ai-agent-orchestrator"},
            {"guid": "g5", "name": "gpt-proxy"},
            {"guid": "g6", "name": "inference-server"},
            {"guid": "g7", "name": "model-server"},
            {"guid": "g8", "name": "agent-worker"},
            {"guid": "g9", "name": "ai-router"},
            {"guid": "g10", "name": "payments-service"},
        ]
    ),
    "infra_gpu.hosts": _entity_count(25),
    "infra_gpu.gpu_hosts": _nrql_results([{"uniqueCount.hostname": 6}]),
    "ai_monitoring.events": _nrql_results([{"count": 60000}]),
    "ai_monitoring.entities": _nrql_results([{"uniqueCount.entity.guid": 10}]),
    "ai_monitoring.token_visibility": _nrql_results([{"percentage": 95}]),
    "ai_agent_tracing.tool_calls": _nrql_results([{"count": 1500}]),
    "ai_agent_tracing.vector_search": _nrql_results([{"count": 50}]),
    "ai_quality_feedback.events": _nrql_results([{"count": 250}]),
    "security_vuln.vuln_domain": _entity_count(25),
    "security_vuln.nrai_vuln": _nrql_results([{"count": 25}]),
    "workflow_automation.workflows": _workflows(_MATURE_WORKFLOW_NAMES),
    **{
        f"autopilot.yaml::{n}": _workflow_yaml(
            "steps:\n  - action: newrelic.autopilot.run\n" if i < 5 else "steps:\n  - action: http.post\n"
        )
        for i, n in enumerate(_MATURE_WORKFLOW_NAMES)
    },
    "alerting_anomaly.conditions": _alert_conditions(
        [
            {"id": str(i), "name": f"condition-{i}", "enabled": True,
             "type": "BASELINE" if i <= 5 else "STATIC"}
            for i in range(1, 19)
        ]
    ),
    "dashboards_logs.dashboards": _entity_count(8),
    "dashboards_logs.log_volume": _nrql_results([{"GB": 450}]),
    "dashboards_logs.log_entities": _nrql_results([{"uniqueCount.entity.guid": 40}]),
}

SCENARIOS = {"none": NONE, "partial": PARTIAL, "mature": MATURE}
