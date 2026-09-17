# Changelog

## 0.2.0 — 2026-09-17

A VP-level code review (`ai-readiness-scorecard-review.md`, reviewed at commit `7363d31`)
flagged seven must-fix issues, several follow-up cleanups, and a handful of smaller
inconsistencies. This release closes all of them and adds a 15th dimension. 66 tests pass
(up from 36); every fix below has dedicated regression coverage, not just "doesn't crash."

### Fixed — correctness and safety

- **Customer names scrubbed from a public repo.** `continental-demo`, `SAP-DEMO`, and
  `conticonnect` — real customer names cited as provenance in docstrings and `prompt.md` —
  are now neutral placeholders (`reference-repo-a`/`reference-repo-b`). Also dropped specific
  real-account telemetry volumes quoted in a few docstrings (e.g. exact event counts), keeping
  the qualitative "confirmed live on `<date>`" provenance without the numbers.
- **Dashboard deploy no longer breaks its own link.** `--deploy-dashboard` used to delete the
  existing dashboard and create a new one on every run, so the GUID (and therefore the link
  handed to a customer) changed every time — and a failed create after the delete left nothing
  at all. It now calls `dashboardUpdate` on the existing GUID when one is found. The lookup is
  also now scoped to `accountId` (previously it could match a same-named dashboard in a
  different account on a multi-account key), and the dashboard name travels as a bound GraphQL
  variable instead of being spliced into the query text by hand.
- **Three unscoped `entitySearch` queries fixed.** `apm_coverage`, `infra_gpu`, and
  `security_vuln` counted entities across *every* account the user key could reach, not just
  the target account — a consultant's own multi-account key could inflate three tiers on a
  report headed with one specific account ID. All three now filter by `accountId`.
- **`apm_coverage` no longer false-positives on ordinary service names.** The old heuristic
  matched names against globs including `*ai*` — a bare substring match that silently counted
  `email-service`, `retail-checkout`, `maintenance-cron`, and similar names as "AI-adjacent"
  (they all contain the letters "ai"). It now checks the `aiEnabledApp` entity tag New Relic's
  own APM agents set when they detect an AI SDK — the same signal behind the Catalog "AI Assets"
  filter. Confidence dropped from `high` to `medium` accordingly (the tag's been confirmed live
  against only one account so far).
- **`ai_monitoring` no longer crashes on an account with zero AI telemetry.** NRQL's
  `percentage()` returns `null`, not `0`, over zero events — the single most common case in a
  first pitch — and the evidence-string formatter crashed trying to format `None` with `:.0f`.
  Now coerced to `0` before formatting.
- **`human_approval_gates` distinguishes "nothing to gate" from "an ungated gap."** Zero
  autonomous action-taking workflows used to score the same tier-0 `Absent` as "workflows exist
  and none of them are gated" — a real, scoreable risk. Added a `Not Applicable` tier
  (`score=None`, excluded from the average like `Unknown`, but rendered distinctly in every
  output) for the former case.
- **The headline score now discloses its own denominator.** A run where most dimensions come
  back `Unknown` (e.g. a user key that can only read one NerdGraph capability) used to render
  identically to a full, confident run. Every output (table, JSON, HTML, dashboard) now shows
  "scored N of 15 dimensions" next to every score, lens breakdowns included.

### Fixed — robustness

- Alert-condition pagination: `alerting_anomaly`/`ai_cost_governance` requested
  `nrqlConditionsSearch(...).totalCount` but never followed the cursor past page one, so an
  account with more conditions than fit on one page silently under-reported. Both now follow
  `nextCursor` via a shared `paginated_alert_conditions()` helper.
- `fetch_workflows()`'s pagination loop now raises after exhausting its page limit instead of
  silently returning a partial list — matching `paginated_entity_search()`'s existing behavior,
  which already did this correctly.
- The exact same workflow list is now fetched once per run and cached, instead of three times
  (once each from `workflow_automation`, `autopilot`, and `human_approval_gates`).
- The live NerdGraph client now retries a transient HTTP 429/5xx with exponential backoff
  before giving up. Some dimensions make 100+ sequential calls in one run (one per Workflow
  Automation canvas on a workflow-heavy account) — previously, one rate-limit blip on call 80 of
  100 discarded the whole dimension's result, not just that one call.

### Changed

- `infra_gpu`'s confidence dropped from `high` to `medium`: its GPU sub-signal is explicitly
  unverified in its own docstring, but was combined via `max` — meaning that unverified signal
  could independently lift the tier while the dimension-level badge claimed `high` confidence.
- The README's confidence legend and the HTML report's on-page legend described `medium`
  differently. Unified to one definition in both places.
- Eight check modules each declared an identical NRQL query document by hand; consolidated into
  one `GENERIC_NRQL_QUERY` constant in `nerdgraph.py`.
- Added a `result_for()` helper (`checks/base.py`) that builds a scored `CheckResult`, pairing
  `tier=TIER_LABELS[score]` with the module's `remediation_map[score]` — the exact pairing all
  14 (now 15) check modules previously hand-repeated at their own final `return` statement.
  Applied across every check module.
- The HTML report no longer loads Google Fonts — system font stack only, so "works fully
  offline" is now true of the rendered artifact too, not just the scoring itself.
- `meta` now carries `tool_version` and `config_fingerprint` (a short hash of the exact
  thresholds a run used), shown in every output — so two scorecards from two engagements can be
  compared knowing whether they were scored against the same rules and tool version.
- Documented, rather than silently changed, a real scoring-model tradeoff: the overall score
  averages the two *lens* means (not a flat average across all 15 dimensions), which gives each
  lens equal say regardless of size — but since the lenses currently hold 8 and 7 dimensions,
  each individual dimension in the smaller lens carries slightly more per-dimension weight on
  the headline. See `scoring.aggregate()`'s docstring and the README's "What it scores" section.

### Added

- **15th dimension: `ai_coding_observability`.** Measures AI *in the SDLC* — is AI
  coding-assistant usage across the engineering org even being tracked — rather than AI *in
  production*, which is what the other 14 dimensions measure. Checks New Relic's AI coding
  observability event types: `AiToolCall` (adoption/usage, gates the tier), `AiCodingTask`
  (task completion, evidence-only), and `AiAntiPattern` (anti-patterns flagged in AI-generated
  code, evidence-only). `unverified` confidence — no account tested so far has this integration
  enabled, so a query failure reports an honest `Unknown`, never a false `Absent`. This was the
  origin idea behind the project (see the AI coding observability announcement cited in
  `prompt.md`) and is added last now that the rest of the scorecard is solid.
- 9 new test files covering every fix above with real regression coverage: pagination
  cursor-following, retry/backoff timing (no real sleeps or network calls), the caching dedup,
  tag-filter scoping, the `Not Applicable` vs `Absent` distinction, and the config fingerprint's
  determinism.

## 0.1.0 and earlier

See git history prior to this file's introduction.
