# AI Readiness Scorecard

Scores a New Relic account's AI readiness across **14 dimensions**, via NerdGraph. Produces a
table, JSON, a CIS-benchmark-style HTML report, and a live dashboard inside New Relic itself.

Zero dependencies — stdlib-only Python, nothing to `pip install` unless you want the packaged
`ai-readiness` command.

## Quick start

```bash
git clone <this repo> && cd ai-readiness-scorecard
python3 -m ai_readiness --mock --mock-scenario mature   # no credentials needed
```

Against a real account:

```bash
cp .env.example .env              # fill in NEW_RELIC_USER_KEY, NEW_RELIC_ACCOUNT_ID, NEW_RELIC_REGION
set -a && source .env && set +a
python3 -m ai_readiness --report html --report-file scorecard.html
```

Or install it as a real command: `pip install -e . && ai-readiness --mock`. `make setup`,
`make test`, `make demo` also work — see the [Makefile](Makefile).

Progress for each dimension prints to stderr as it runs (useful since a live scan makes many
sequential NerdGraph/NRQL calls and can take a while — `autopilot` and `human_approval_gates`
each make one YAML fetch per Workflow Automation canvas, so together they can be 100+ calls on
an account with many canvases; budget more than the default 2-minute shell timeout for a full
live run on such an account). Pass `--quiet`/`-q` to suppress the progress lines.

## What it scores

Two lenses, 14 dimensions, each tiered **Absent → Ad hoc → Managed → Optimized**. Lens and
overall scores are displayed on a **0-10 scale** (the 4 internal tiers are what's actually
measured; 0-10 is just the display convention for the roll-up numbers). Each dimension's
remediation text is tier-specific — a concrete next step to move up a level, not one generic
sentence regardless of where you're starting from.

| Lens | Dimension | Confidence | Signal |
|---|---|---|---|
| Observability for AI | `apm_coverage` | high | APM services with AI-adjacent names |
| | `infra_gpu` | high | Infra hosts + GPU utilization metrics |
| | `ai_monitoring` | medium | LLM generation events + token/cost visibility (NR *and* OTel GenAI paths) |
| | `ai_agent_tracing` | high | Tool-call & RAG/retrieval span tracing (NR *and* OTel GenAI paths) |
| | `ai_quality_feedback` | unverified | AI output feedback/eval scoring |
| | `human_approval_gates` | medium | Human-approval step before autonomous agent actions (OWASP LLM08) |
| | `model_vendor_diversity` | high | LLM provider diversity — single-vendor lock-in risk |
| | `security_vuln` | unverified | Vulnerability-management coverage |
| AI for Observability | `workflow_automation` | high | Workflow Automation canvases configured |
| | `autopilot` | medium | Canvases that invoke Autopilot |
| | `alerting_anomaly` | high | Enabled alert conditions |
| | `dashboards_logs` | high | Dashboard count + log volume |
| | `ai_cost_governance` | high | Alert conditions targeting AI token/cost spend |
| | `ai_change_tracking` | medium | Change Tracking events referencing AI/prompt/model changes |

Run `python3 -m ai_readiness --list-dimensions` to see this live, with each dimension's exact
label.

The three AI-specific dimensions (`ai_monitoring`, `ai_agent_tracing`, `ai_quality_feedback`)
are modeled on what mature open-source LLM observability tools (Langfuse, in particular) treat
as signals of a mature setup — not just "some LLM call happened," but token/cost visibility,
tool-call/agent-step tracing, retrieval tracing, and feedback scoring.

`ai_monitoring` and `ai_agent_tracing` each check **two independent telemetry paths and take
whichever is stronger**: New Relic's own `Llm*` custom events, and OpenTelemetry's GenAI
semantic-convention `gen_ai.*` attributes on plain `Span` events (emitted by backend-agnostic
OTel instrumentation like OpenLLMetry/Traceloop). An account using only one path still scores
correctly. `ai_monitoring` also flags — as evidence, not a score penalty — whether raw
prompt/completion content is being captured into spans (`gen_ai.prompt`/`gen_ai.input.messages`),
since OpenLLMetry captures that content **by default**; worth a PII/data-governance conversation
if it's nonzero. Note: the `gen_ai.*` convention itself is still spec-flagged *Development*
status, not Stable — expect attribute renames over time (`gen_ai.system` → `gen_ai.provider.name`
already happened in v1.37.0).

Four more dimensions target modern, 2025-2026-era AI risk patterns rather than plain telemetry
coverage: **`human_approval_gates`** (OWASP LLM08, Excessive Agency — is an autonomous action
gated by a human checkpoint, or does the agent just act?), **`model_vendor_diversity`** (single-
provider lock-in risk — a real business-continuity exposure given how often providers deprecate
models or change pricing), **`ai_cost_governance`** (alert conditions that actually target AI
token/cost spend, not just generic infra cost), and **`ai_change_tracking`** (are prompt/model
changes tracked as Change Tracking events, the same way a code deploy is, so an AI regression is
traceable back to "what changed"). Two adjacent ideas were considered and deliberately **not**
built yet: shadow-AI detection (unsanctioned LLM tool usage via network egress) and MCP-server-
specific tracing — both need more groundwork on what's actually queryable before they'd be
more than a guess.

## Confidence legend

| Level | Meaning |
|---|---|
| `high` | Query shape confirmed against a working, live-tested pattern |
| `medium` | Confirmed live against one real account — not yet proven across multiple engagements |
| `unverified` | Best-effort guess, no confirmed populated example on any account tested yet |

An `unverified` check that fails outright reports an honest `Unknown` — never a false `Absent`.
See each `ai_readiness/checks/*.py` file's docstring for exactly what's been confirmed and how.

## Deliverables

**HTML report** — executive summary + a per-lens table (tier badge, confidence, evidence,
remediation). Works fully offline with `--mock`.

```bash
python3 -m ai_readiness --report html --report-file scorecard.html
```

**Live New Relic dashboard** — deploys the same content as a dashboard inside the target
account (Executive Summary page + one page per lens). Re-running upserts by name, so nothing
duplicates.

```bash
python3 -m ai_readiness --dashboard-dry-run       # preview the payload, no network call
python3 -m ai_readiness --deploy-dashboard        # writes to the account -- requires a live account, not --mock
```

This is a point-in-time snapshot, not a live/trend dashboard — the score is computed in
Python, not stored in NRDB. See **What's next** below.

## Using this for a new customer

1. Copy `.env.example` → `.env`, fill in that customer's `NEW_RELIC_USER_KEY` / `ACCOUNT_ID` / `REGION`.
2. Run the validation sequence below once against their account to catch any dimension that
   needs a query-shape fix before you're in front of them.
3. `--report html` for the leave-behind; `--deploy-dashboard --dashboard-name "<Customer> — AI Readiness"` for the live artifact.
4. Tune scoring thresholds per engagement with `--config overrides.json` (below) — no code changes needed.

### Validating against a real account

Run one dimension at a time, high-confidence ones first, so a wrong query only ever touches
its own file:

```bash
python3 -m ai_readiness --only workflow_automation,alerting_anomaly,dashboards_logs,apm_coverage,ai_agent_tracing
python3 -m ai_readiness --only autopilot,infra_gpu,ai_monitoring,model_vendor_diversity,ai_cost_governance
python3 -m ai_readiness --only ai_change_tracking,human_approval_gates  # human_approval_gates is slow: one YAML fetch per canvas
python3 -m ai_readiness --only security_vuln        # expect this may need a query-shape fix
python3 -m ai_readiness --only ai_quality_feedback  # expect Absent even when the query is right
```

### Tuning thresholds

Every threshold lives in `ai_readiness/config.py` (`THRESHOLDS`). Override without touching
code via `--config overrides.json`, deep-merged onto the defaults:

```json
{"workflow_automation": {"min_workflows_for_tier": {"1": 1, "2": 2, "3": 4}}}
```

## Tests

```bash
make test   # or: python3 -m unittest discover tests
```

## Architecture, in one paragraph

`ai_readiness/checks/*.py` — one file per dimension, each fully isolated (`checks/base.py`'s
`run_check()` catches any failure into an `Unknown` row instead of crashing the run).
`nerdgraph.py` is the only thing that talks to the network, with a `--mock` swap-in for
credential-free testing. `config.py` holds every scoring number. `report.py`/`dashboard.py`
consume the same `CheckResult` list generically — adding a new dimension means adding one file
and one registry line, nothing else changes.

## What's next

- Push scorecard runs into a custom NerdGraph event type so the live dashboard can show
  trend-over-time instead of a point-in-time snapshot.
- Confirm `security_vuln` against an account with Security RX enabled — a zero result there is
  ambiguous (real Absent vs. a wrong filter value silently matching nothing).
- Confirm `ai_quality_feedback`'s `LlmFeedbackMessage` event type against an account that
  actually captures AI output feedback — every account tested so far has zero.
- Watch for OTel GenAI attribute renames (`gen_ai.system` → `gen_ai.provider.name` already
  happened) and add the new name alongside the old one rather than replacing it outright, since
  older instrumentation will keep emitting the deprecated name for a while.
