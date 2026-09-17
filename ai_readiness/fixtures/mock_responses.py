"""Canned NerdGraph responses keyed by fixture_key, for --mock mode. Three
scenarios exercise the full tier range end-to-end without ever touching a
real account:

  none    -- every dimension should score 0/Absent
  mature  -- every dimension should score 3/Optimized
  partial -- a deliberate mix across tiers 1-2; also the only scenario where
             apm_coverage.entities is a *list* of page dicts, exercising the
             entitySearch pagination cursor loop (untested by either
             reference repo, so it needs its own fixture).

apm_coverage.entities simulates the server having already applied the
`tags.aiEnabledApp = 'true'` filter -- it lists only tagged entities.
apm_coverage.total is the separate, unfiltered reporting-APM count (the
evidence denominator), deliberately including untagged services with
AI-adjacent-sounding names (e.g. a hypothetical `email-service` would count
toward the total but never appear in .entities without the tag) to prove the
tag filter, not a name pattern, is what gates the count.
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
    "apm_coverage.total": _entity_count(0),
    "infra_gpu.hosts": _entity_count(0),
    "infra_gpu.gpu_hosts": _nrql_results([{"uniqueCount.hostname": 0}]),
    "ai_monitoring.events": _nrql_results([{"count": 0}]),
    "ai_monitoring.entities": _nrql_results([{"uniqueCount.entity.guid": 0}]),
    "ai_monitoring.token_visibility": _nrql_results([{"percentage": 0}]),
    "ai_monitoring.genai.events": _nrql_results([{"count": 0}]),
    "ai_monitoring.genai.entities": _nrql_results([{"uniqueCount.entity.guid": 0}]),
    "ai_monitoring.genai.token_visibility": _nrql_results([{"percentage": 0}]),
    "ai_monitoring.content_capture": _nrql_results([{"count": 0}]),
    "ai_agent_tracing.tool_calls": _nrql_results([{"count": 0}]),
    "ai_agent_tracing.genai_tool_calls": _nrql_results([{"count": 0}]),
    "ai_agent_tracing.vector_search": _nrql_results([{"count": 0}]),
    "ai_agent_tracing.genai_retrieval": _nrql_results([{"count": 0}]),
    "ai_quality_feedback.events": _nrql_results([{"count": 0}]),
    # human_approval_gates: NONE scenario has zero workflows (see
    # workflow_automation.workflows below), so fetch_workflows() returns []
    # and the per-workflow YAML loop never runs -- no yaml:: fixture needed.
    "model_vendor_diversity.llm_vendors": _nrql_results([{"uniqueCount.vendor": 0}]),
    "model_vendor_diversity.genai_vendors": _nrql_results([{"uniqueCount.gen_ai.system": 0}]),
    "security_vuln.vuln_domain": _entity_count(0),
    "security_vuln.nrai_vuln": _nrql_results([{"count": 0}]),
    "workflow_automation.workflows": _workflows([]),
    "alerting_anomaly.conditions": _alert_conditions([]),
    "dashboards_logs.dashboards": _entity_count(0),
    "dashboards_logs.log_volume": _nrql_results([{"GB": 0}]),
    "dashboards_logs.log_entities": _nrql_results([{"uniqueCount.entity.guid": 0}]),
    "ai_cost_governance.conditions": _alert_conditions([]),
    "ai_change_tracking.total": _nrql_results([{"count": 0}]),
    "ai_change_tracking.events": _nrql_results([]),
    "ai_coding_observability.tool_calls": _nrql_results([{"count": 0}]),
    "ai_coding_observability.tasks": _nrql_results([{"count": 0}]),
    "ai_coding_observability.anti_patterns": _nrql_results([{"count": 0}]),
}

_PARTIAL_WORKFLOW_NAMES = ["wf-a", "wf-b", "wf-c", "wf-d"]

PARTIAL = {
    # 3 of 8 reporting APM services carry the aiEnabledApp tag; the other 5
    # (orders-service, billing-service, shipping-service, catalog-service,
    # user-service -- untagged, not returned here at all) count toward
    # apm_coverage.total below but never toward this tagged list.
    "apm_coverage.entities": [
        _apm_page(
            [
                {"guid": "a2", "name": "ai-recommender"},
                {"guid": "a4", "name": "agent-scheduler"},
            ],
            next_cursor="page2",
        ),
        _apm_page(
            [
                {"guid": "a6", "name": "rag-search"},
            ]
        ),
    ],
    "apm_coverage.total": _entity_count(8),
    "infra_gpu.hosts": _entity_count(6),
    "infra_gpu.gpu_hosts": _nrql_results([{"uniqueCount.hostname": 1}]),
    "ai_monitoring.events": _nrql_results([{"count": 1200}]),
    "ai_monitoring.entities": _nrql_results([{"uniqueCount.entity.guid": 2}]),
    "ai_monitoring.token_visibility": _nrql_results([{"percentage": 45}]),
    # gen_ai path deliberately weaker than the LlmChatCompletionSummary path
    # here (events below the tier-1 threshold) so combine_tiers(..., "max")
    # still resolves to the same tier the LLM path alone gives -- no need to
    # recompute EXPECTED_SCORES for this scenario.
    "ai_monitoring.genai.events": _nrql_results([{"count": 50}]),
    "ai_monitoring.genai.entities": _nrql_results([{"uniqueCount.entity.guid": 1}]),
    "ai_monitoring.genai.token_visibility": _nrql_results([{"percentage": 20}]),
    "ai_monitoring.content_capture": _nrql_results([{"count": 0}]),
    "ai_agent_tracing.tool_calls": _nrql_results([{"count": 150}]),
    "ai_agent_tracing.genai_tool_calls": _nrql_results([{"count": 20}]),
    "ai_agent_tracing.vector_search": _nrql_results([{"count": 5}]),
    "ai_agent_tracing.genai_retrieval": _nrql_results([{"count": 2}]),
    "ai_quality_feedback.events": _nrql_results([{"count": 10}]),
    "security_vuln.vuln_domain": _entity_count(3),
    "security_vuln.nrai_vuln": _nrql_results([{"count": 3}]),
    "workflow_automation.workflows": _workflows(_PARTIAL_WORKFLOW_NAMES),
    "autopilot.yaml::wf-a": _workflow_yaml("steps:\n  - action: newrelic.autopilot.run\n"),
    "autopilot.yaml::wf-b": _workflow_yaml("# uses autopilot for RCA\nsteps: []\n"),
    "autopilot.yaml::wf-c": _workflow_yaml("steps:\n  - action: http.post\n"),
    "autopilot.yaml::wf-d": _workflow_yaml("steps:\n  - action: slack.chat.postMessage\n"),
    # human_approval_gates: wf-a/wf-c take an action AND are gated, wf-b takes
    # an action with no gate, wf-d takes no action at all -> 2 of 3
    # action-taking workflows gated (66.7%).
    "human_approval_gates.yaml::wf-a": _workflow_yaml(
        "steps:\n  - action: http.post\n  - action: slack.chat.getReactions\n"
    ),
    "human_approval_gates.yaml::wf-b": _workflow_yaml("steps:\n  - action: aws.lambda.invoke\n"),
    "human_approval_gates.yaml::wf-c": _workflow_yaml(
        "steps:\n  - action: http.post\n  - name: waitForApproval\n"
    ),
    "human_approval_gates.yaml::wf-d": _workflow_yaml("steps:\n  - action: slack.chat.postMessage\n"),
    "model_vendor_diversity.llm_vendors": _nrql_results([{"uniqueCount.vendor": 1}]),
    "model_vendor_diversity.genai_vendors": _nrql_results([{"uniqueCount.gen_ai.system": 2}]),
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
    "ai_cost_governance.conditions": _alert_conditions(
        [
            {"id": "c1", "name": "token spend spike", "enabled": True,
             "nrql": {"query": "SELECT sum(response.usage.total_tokens) FROM LlmChatCompletionSummary"}},
            {"id": "c2", "name": "generic-error-rate", "enabled": True,
             "nrql": {"query": "SELECT count(*) FROM Transaction WHERE error IS true"}},
            {"id": "c3", "name": "llm cost budget", "enabled": True,
             "nrql": {"query": "SELECT sum(costUsd) FROM CostSample"}},
            {"id": "c4", "name": "checkout latency", "enabled": True,
             "nrql": {"query": "SELECT average(duration) FROM Transaction"}},
        ]
    ),
    "ai_change_tracking.total": _nrql_results([{"count": 5}]),
    "ai_change_tracking.events": _nrql_results(
        [
            {"description": "Bumped gpt-4o-mini to gpt-4.1-mini for the recommender prompt"},
            {"description": "Updated system prompt for support-triage model"},
            {"description": "Restarted billing-service pod after OOM"},
            {"description": "Rotated database credentials"},
            {"description": "Scaled up checkout-service replicas"},
        ]
    ),
    "ai_coding_observability.tool_calls": _nrql_results([{"count": 150}]),
    "ai_coding_observability.tasks": _nrql_results([{"count": 40}]),
    "ai_coding_observability.anti_patterns": _nrql_results([{"count": 6}]),
}

_MATURE_WORKFLOW_NAMES = [f"wf-{i}" for i in range(1, 8)]

MATURE = {
    # 8 of 10 reporting APM services carry the aiEnabledApp tag; the other 2
    # (checkout-service, payments-service -- untagged) count toward
    # apm_coverage.total below but never toward this tagged list.
    "apm_coverage.entities": _apm_page(
        [
            {"guid": "g2", "name": "llm-gateway"},
            {"guid": "g3", "name": "rag-retriever"},
            {"guid": "g4", "name": "ai-agent-orchestrator"},
            {"guid": "g5", "name": "gpt-proxy"},
            {"guid": "g6", "name": "inference-server"},
            {"guid": "g7", "name": "model-server"},
            {"guid": "g8", "name": "agent-worker"},
            {"guid": "g9", "name": "ai-router"},
        ]
    ),
    "apm_coverage.total": _entity_count(10),
    "infra_gpu.hosts": _entity_count(25),
    "infra_gpu.gpu_hosts": _nrql_results([{"uniqueCount.hostname": 6}]),
    "ai_monitoring.events": _nrql_results([{"count": 60000}]),
    "ai_monitoring.entities": _nrql_results([{"uniqueCount.entity.guid": 10}]),
    "ai_monitoring.token_visibility": _nrql_results([{"percentage": 95}]),
    "ai_monitoring.genai.events": _nrql_results([{"count": 55000}]),
    "ai_monitoring.genai.entities": _nrql_results([{"uniqueCount.entity.guid": 9}]),
    "ai_monitoring.genai.token_visibility": _nrql_results([{"percentage": 92}]),
    # nonzero here specifically to exercise the PII content-capture evidence
    # branch -- none/partial leave it at 0 to exercise the no-flag branch.
    "ai_monitoring.content_capture": _nrql_results([{"count": 4200}]),
    "ai_agent_tracing.tool_calls": _nrql_results([{"count": 1500}]),
    "ai_agent_tracing.genai_tool_calls": _nrql_results([{"count": 1200}]),
    "ai_agent_tracing.vector_search": _nrql_results([{"count": 50}]),
    "ai_agent_tracing.genai_retrieval": _nrql_results([{"count": 30}]),
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
    # human_approval_gates: every workflow both takes an action and is gated
    # -> 100% coverage, guaranteeing tier 3 (keeps the "mature = all
    # Optimized" invariant intact).
    **{
        f"human_approval_gates.yaml::{n}": _workflow_yaml(
            "steps:\n  - action: http.post\n  - action: slack.chat.getReactions\n"
        )
        for n in _MATURE_WORKFLOW_NAMES
    },
    "model_vendor_diversity.llm_vendors": _nrql_results([{"uniqueCount.vendor": 3}]),
    "model_vendor_diversity.genai_vendors": _nrql_results([{"uniqueCount.gen_ai.system": 2}]),
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
    "ai_cost_governance.conditions": _alert_conditions(
        [
            {"id": "c1", "name": "token spend spike", "enabled": True,
             "nrql": {"query": "SELECT sum(response.usage.total_tokens) FROM LlmChatCompletionSummary"}},
            {"id": "c2", "name": "llm cost budget breach", "enabled": True,
             "nrql": {"query": "SELECT sum(costUsd) FROM CostSample"}},
            {"id": "c3", "name": "per-model spend anomaly", "enabled": True,
             "nrql": {"query": "SELECT sum(response.usage.total_tokens) FACET request.model FROM LlmChatCompletionSummary"}},
            {"id": "c4", "name": "gen_ai usage ceiling", "enabled": True,
             "nrql": {"query": "SELECT sum(gen_ai.usage.output_tokens) FROM Span"}},
            {"id": "c5", "name": "checkout latency", "enabled": True,
             "nrql": {"query": "SELECT average(duration) FROM Transaction"}},
        ]
    ),
    "ai_change_tracking.total": _nrql_results([{"count": 10}]),
    "ai_change_tracking.events": _nrql_results(
        [
            {"description": "Bumped gpt-4o-mini to gpt-4.1-mini for the recommender prompt"},
            {"description": "Updated system prompt for support-triage model"},
            {"description": "Rolled back claude model version after eval regression"},
            {"description": "Added gemini as a fallback provider for the chat model"},
            {"description": "Tuned gen_ai temperature for the summarizer prompt"},
            {"description": "Retired legacy llm gateway route"},
            {"description": "Updated RAG retrieval prompt template"},
            {"description": "Adjusted gpt model max_tokens setting"},
            {"description": "Restarted billing-service pod after OOM"},
            {"description": "Rotated database credentials"},
        ]
    ),
    "ai_coding_observability.tool_calls": _nrql_results([{"count": 5000}]),
    "ai_coding_observability.tasks": _nrql_results([{"count": 400}]),
    "ai_coding_observability.anti_patterns": _nrql_results([{"count": 50}]),
}

SCENARIOS = {"none": NONE, "partial": PARTIAL, "mature": MATURE}
