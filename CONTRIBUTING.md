# Contributing

Issues and pull requests are welcome — this started as one SC's internal tool and is meant
to be reused/extended by others doing the same kind of engagement.

## Before opening a PR

```bash
make test    # or: python3 -m unittest discover tests
```

CI runs the same suite on Python 3.9 and 3.12 for every push and PR (see
[.github/workflows/test.yml](.github/workflows/test.yml)), plus one live `--mock` smoke run.
Both must pass.

## Adding a new dimension

Each dimension is fully isolated in one file under `ai_readiness/checks/`. Adding one means:

1. Create `ai_readiness/checks/<dimension_name>.py`. Copy the shape of an existing check
   closest to what you're building:
   - A single NRQL count query → `ai_readiness/checks/ai_quality_feedback.py`.
   - Two independent detection paths combined via `combine_tiers(..., method="max")` (either
     proves readiness) → `ai_readiness/checks/ai_agent_tracing.py`.
   - An `entitySearch` count/list → `ai_readiness/checks/apm_coverage.py` or `infra_gpu.py`.
   - A dimension where "nothing to measure" is a legitimate outcome, not a failure →
     `ai_readiness/checks/human_approval_gates.py`'s `Not Applicable` handling.
   Every module exposes `DIMENSION`, `LABEL`, `LENS`, `CONFIDENCE`, `REMEDIATION` (a `{0,1,2,3:
   str}` dict), `REMEDIATION_UNKNOWN`, and a `run(ctx) -> CheckResult`. Use
   `checks.base.result_for(...)` to build the final scored result — it pairs
   `tier=TIER_LABELS[score]` with `remediation_map[score]` for you.
2. Add one line to `ai_readiness/checks/__init__.py`: import the module and add it to
   `ALL_CHECKS` in the position you want it displayed (Observability for AI first, then AI for
   Observability).
3. Add its thresholds to `THRESHOLDS` in `ai_readiness/config.py`.
4. Add fixtures for all three `--mock` scenarios (`none`/`partial`/`mature`) in
   `ai_readiness/fixtures/mock_responses.py`, keyed by the `fixture_key` strings your `run()`
   passes to `ctx.gql(...)`. `none` should score 0 for your dimension, `mature` should score 3.
5. Add its expected score to `EXPECTED_SCORES` in `tests/test_checks_mock.py` for all three
   scenarios.

Nothing else changes — `report.py`/`dashboard.py` consume the same `CheckResult` list
generically regardless of how many dimensions exist.

### Confidence levels

Pick honestly, not optimistically — see the README's "Confidence legend" for the exact
definitions. In short: `high` needs a live-tested query shape; `medium` covers both "confirmed
on only one account so far" and "a confirmed primitive with an unverified heuristic on top";
`unverified` means no prior art at all. An `unverified` (or any) check that fails outright
should report `Unknown`, never guess `Absent` — see `security_vuln.py`/`ai_quality_feedback.py`
for the try/except pattern that keeps those two honest.

## Testing against a real account

If you have a real New Relic account to validate a new or changed dimension against, run it in
isolation first:

```bash
python3 -m ai_readiness --only <your_dimension>
```

Update the check's docstring with what you actually confirmed (event type populated, field
names, date) — every existing check's docstring records this, and it's what determines whether
the confidence level above is honest.

## Style

- No dependencies beyond the stdlib. If you're tempted to add one, there's almost certainly a
  stdlib way to do it (see `nerdgraph.py`'s hand-rolled `urllib` client).
- No comments explaining *what* code does — name things so that's obvious. A comment should
  only exist for a non-obvious *why* (a workaround, an invariant, a decision that would
  surprise a reader).
- Match the existing docstring convention at the top of each check file: what's confirmed vs.
  guessed, and against which account/date.

## Releasing

Bump `version` in `pyproject.toml` and `__version__` in `ai_readiness/__init__.py` together,
add an entry to `CHANGELOG.md`, then tag and push:

```bash
git tag v0.X.0
git push origin v0.X.0
gh release create v0.X.0 --title "v0.X.0" --notes-file <(sed -n '/^## 0.X.0/,/^## /p' CHANGELOG.md | sed '$d')
```
