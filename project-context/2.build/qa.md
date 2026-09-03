# QA Report — customer-support-agent

> **This file now contains two dated QA passes.** The original 2026-09-01 pass (below, unmodified) is preserved for history. A fresh, current pass follows it, dated **2026-09-02** — read that section for the current state of the build; do not treat the 2026-09-01 numbers (75 backend tests, mypy broken, no dispute-language feature) as still accurate. This mirrors `backend.md`'s own repeated-dated-entry convention rather than overwriting history.

---

# Fresh QA Pass — 2026-09-02

## Scope and Trigger

Re-run of `*qa` from scratch, not a re-read of the 2026-09-01 report above. Triggered by a full round of new work landing since that report: a new Trace Log (`backend/src/app/persistence/trace_log.py`) with per-interaction correlation and a `GET /interactions/{id}/trace` endpoint; per-step (LLM/tool-call) latency pass/fail fields reusing sad.md §7's thresholds; a new `/ops` trace-timeline UI (`InteractionTracePanel.tsx`); and a real bug fix — a dispute/chargeback threat message that was not escalating — specified in a new **ADR-002 Addendum (2026-09-02)** in `sad.md` and implemented in `escalation_gate.py`/`inquiry_flow.py`. All of the below was independently re-verified against the actual current codebase and a live backend instance (`http://localhost:8000`, confirmed via `GET /health` → `{"status":"ok"}` before use), not taken on the strength of any other persona's own report.

**Working tree**: branch `devops`, uncommitted changes present (`git status`/`git diff --stat` reviewed directly) spanning `backend/src/app/{agents,flows,main.py}`, new `backend/src/app/persistence/trace_log.py`, new `backend/tests/unit/test_trace_log.py`, extended `test_escalation_gate.py`/`test_inquiry_flow.py`/`test_chat_endpoint.py`, frontend `InteractionLogTable.tsx`/`mockOpsData.ts`/`ops.css`/`types/ops.ts`, new `InteractionTracePanel.tsx`, and `sad.md`/`backend.md`/`frontend.md`. This report evaluates that working tree as it stands, not a specific commit.

## 1. Backend automated suite — run fresh this session

```
pytest -q       -> 150 passed, 0 failed, 0 skipped, ~136s (real live Anthropic API calls; real key present in backend/.env, no skips observed)
ruff check .    -> 1 pre-existing nit (task_outputs.py:44, E501, 102>100 chars) — unchanged, not a regression, not in any file touched this round
mypy src        -> Success: no issues found in 20 source files (was 19 — +1 for trace_log.py)
```

**150 vs. the 2026-09-01 report's 75** is explained in full by `backend.md`'s own dated Audit entries (read directly, not taken on faith): +15 for the first Trace Log wiring, +13 for interaction correlation + the trace endpoint (9 unit + 4 integration), +16 for per-step latency, +31 for the ADR-002 Addendum (30 in `test_escalation_gate.py`, 1 in `test_inquiry_flow.py`). Recounted independently via `pytest --collect-only`, not by trusting the changelog arithmetic: `test_trace_log.py` = 40 tests, `test_escalation_gate.py` = 42 tests, `test_inquiry_flow.py` = 7 tests — all match `backend.md`'s stated running totals exactly. **mypy's environment defect from the 2026-09-01 report is resolved** — `backend.md`'s 2026-09-01 entry records the fix (`pip uninstall -y mypy mypy_extensions && pip install --no-cache-dir "mypy>=1.11"`), and this session's independent `mypy src` run confirms it clean. Known Defect #3 from the prior pass is closed.

## 2. Frontend static verification — run fresh this session

```
npm run lint    (oxlint)               -> clean, 0 errors/warnings
npm run build   (tsc -b + vite build)  -> succeeded, dist/ produced (12.28 kB CSS, 261.61 kB JS), 467ms
```

**Gap, unchanged, confirmed still open**: `frontend/package.json`'s `scripts` block has no `test` entry (`dev`, `build`, `lint`, `preview` only) — read directly, not assumed. Zero automated frontend tests still exist for `InteractionTracePanel.tsx` or any other component; `frontend.md` §13/§14's own Open Questions sections flag this again for the new trace-panel code, same unresolved gap as every prior section. Known Defect #4 from the 2026-09-01 pass carries forward unchanged.

## 3. Live end-to-end verification of the dispute-language fix — confirmed live, not just via unit tests

A real `ANTHROPIC_API_KEY` is present in `backend/.env` and the local backend was live (`GET /health` → `{"status":"ok"}`). Posted the exact real-world message from the bug report directly to the running `POST /chat`:

```
POST /chat {"session_id": "qa-dispute-test-1", "message": "I am not looking to reschedule. As I wasnt given cancellation policy I would not want me to be charged like I said - I will dispute that charge"}
-> {"reply": "Thanks for reaching out. I've flagged this for a team member to review personally, and someone will follow up with you shortly.", "escalated": true}
```

Cross-checked via `GET /interactions` for this session's persisted record: `confidence: 0.92`, `sentiment_score: 0.68`, `sentiment_label: "frustrated"`, `grounded: true`, `outcome: "escalated"`. **This is the load-bearing confirmation**: confidence is well above the 0.70 escalate line, sentiment (0.68) is below the 0.75 escalate line, and grounded is true — none of the three original ADR-002 conditions would have escalated this message on their own (reproducing almost exactly the 2026-09-02 bug-report values of confidence=0.92/sentiment=0.70). The only condition that can explain `escalated: true` here is the new 4th condition, `dispute_language_detected`.

Also fetched `GET /interactions/{id}/trace` for this same interaction (real, not synthetic): 28 events returned, chronologically ordered, covering `pii_guard`'s task/LLM/tool events followed by all four reasoning-Crew tasks, each `llm_call_completed`/`tool_call_finished` record carrying non-null `duration_ms`/`latency_pass`/`meets_target` (all `true` in this run — every step finished well under both the 5s target and 10s ceiling). This confirms, live: (a) the Trace Log + interaction-correlation feature works end-to-end against real traffic, (b) the per-step latency fields are populated and correctly derived, and (c) `GET /interactions/{id}/trace` returns real data — not just what the unit/integration test suite asserts in isolation. This also resolves `frontend.md` §14's own Open Question ("the shared backend dev server process must be restarted to pick up the uncommitted `main.py`/`trace_log.py` changes before `/ops` can show real (non-synthetic) latency data") — the backend instance live during this QA session is already serving the current code; real (non-synthetic) latency data is confirmed flowing.

**Also ran the backend's own automated regression for this fix** (not relying on the live probe alone): `test_escalation_gate.py`'s `contains_dispute_language()` fixtures (17 true positives including the exact bug-report message, 8 true negatives including ordinary "charge" phrasing and two word-boundary negatives for "disputed"/"undisputed") and `test_inquiry_flow.py::test_dispute_message_now_escalates_end_to_end_reproducing_2026_09_02_false_negative` (monkeypatches the Crew to the exact observed confidence/sentiment/grounded values and asserts `escalated=True, reason=["dispute_language_detected"]` through the real `InquiryFlow`) — both pass. **Verdict: the fix is verified both live end-to-end and via unit/integration tests — not unit-tests-only.**

## 4. `sad.md` internal consistency — re-checked directly, not assumed from the addendum's own text

Read `sad.md`'s ADR-002 Addendum in full, plus the surrounding §2 step 4 prose and the "Typed Task Outputs" closing paragraph, via `git diff`. Confirmed:

- §2 step 4's bullet list now reads "**four** independent OR'd conditions" (was "three"), lists `dispute_language_detected == true` as the 4th bullet, and its closing sentence now says "the three numeric thresholds are MVP starting values... `dispute_language_detected` is a pinned phrase-list match, not a numeric threshold" (was "all three numbers").
- The "Typed Task Outputs" paragraph now reads "`escalation_gate` (step 4) reads exactly **four** inputs... nothing else" (was "exactly three typed fields").
- Both edits are attributed in `sad.md`'s own Audit trail (2026-09-02 entry, `amend-sad --adr-002-addendum`), and `backend.md`'s matching 2026-09-02 Audit entry explicitly states it made this exact `sad.md` §2 edit as instructed by the addendum, "so §2 and this addendum do not drift the way `MAX_EXECUTION_TIME_SECONDS` did" — a direct, explicit citation of this QA persona's own 2026-09-01 finding.

**This is the SAD-drift problem from the prior pass, deliberately not repeated.** Confirmed by direct text comparison (not by trusting the addendum's own claim that it did this): code (`escalation_gate.py`'s 4-parameter `evaluate_escalation()`, `inquiry_flow.py`'s `escalation_gate()` router), tests, and `sad.md` prose all now agree on "four conditions." No drift found.

**Separately, the pre-existing `MAX_EXECUTION_TIME_SECONDS` drift flagged in the 2026-09-01 pass is unchanged and NOT newly resolved this round**: `inquiry_flow.py` line 75 still reads `MAX_EXECUTION_TIME_SECONDS = 30`; `sad.md` §7 still states a 10s hard ceiling with no ADR recorded for the 30s deviation. This was out of scope for this round's work (confirmed via `backend.md`'s 2026-09-02 entries, each of which explicitly lists "`MAX_EXECUTION_TIME_SECONDS` untouched" under Prohibited Actions Confirmed Avoided) — carried forward as Known Defect #2, unchanged, not newly introduced.

## 5. New-round provenance check — no new gaps found

Read `backend.md`'s four new 2026-09-01/2026-09-02 dated entries and `frontend.md`'s new §13/§14 in full, specifically hunting for the same class of gap flagged in the 2026-09-01 pass (undocumented code changes, SAD drift, missing Audit attribution). Both files follow the Audit-block convention consistently for every change this round: each entry names its trigger, exact files touched, tools/versions, verification performed (including live pytest/ruff/mypy numbers matching what this pass independently reproduced), and an explicit "Prohibited actions confirmed avoided" list. `frontend.md` §14 additionally self-reports a real process/tooling issue transparently rather than silently working around it (the shared dev server initially predated the latency-field code — flagged as an Open Question, not faked past) — that gap is resolved by this session's own live verification in §3 above, since the currently-running instance now demonstrably serves current code. No undocumented deviation, no missing Audit trail, and no SAD-vs-code disagreement was found in this round's new work.

## 6. SAD §7 latency-spike gate — status confirmed unchanged, not re-run this session

Not part of this round's changes and not re-probed by this action (a full clean 20+-request/4-category spike is a separate, larger undertaking than this fresh-QA pass's scope, and nothing in this round's work touched the reasoning Crew's latency profile). `backend.md`'s Open Questions still show the 2026-08-22 spike at 14/20 valid measurements (0/5 for `general_complaints`), never completed cleanly since. **Known Defect #1 from the 2026-09-01 pass carries forward unchanged** — still open, still an operator decision.

## 7. Updated Known Defects / Gaps (2026-09-02)

1. **SAD §7 latency gate still open** — unchanged from 2026-09-01 (see §6 above). Operator decision still needed.
2. **Undocumented SAD §7 ceiling deviation (`MAX_EXECUTION_TIME_SECONDS = 30` vs. `sad.md`'s stated 10s)** — unchanged from 2026-09-01. Not touched or resolved by this round's work (confirmed via `backend.md`'s explicit "untouched" attestations). Still needs an operator/`@backend.eng` decision: revert to 10s, or formally amend `sad.md` and backfill the Audit trail.
3. ~~mypy environment broken~~ **RESOLVED** — confirmed fixed in `backend.md`'s 2026-09-01 entry and independently reconfirmed clean (`Success: no issues found in 20 source files`) by this session's own fresh run.
4. **Zero automated frontend tests** — unchanged from 2026-09-01, now also covering the new `InteractionTracePanel.tsx`/`InteractionLogTable.tsx` trace-toggle logic (§14's own Open Questions confirm this explicitly). Still no Vitest/RTL or equivalent configured.
5. `POST /escalations/{id}/resolve` still does not validate the target interaction was actually escalated — unchanged, not touched this round.
6. Approved KB entries still default to `candidate_keywords: []` absent manual Reviewer edit — unchanged, not touched this round.
7. Two inconsistent API error-envelope shapes — unchanged; the new `GET /interactions/{id}/trace` 404 uses the `{error_code, message}` shape (consistent with the newer convention), so this endpoint doesn't add to the inconsistency, but the pre-existing split elsewhere in the API is not resolved.
8. No literal browser/Playwright click-through test is committed to the repo — `frontend.md` §13.6/§14.6 record real Playwright sessions were run manually during development (scratch scripts, not committed), same pattern as before; still no persisted, repeatable browser test suite.
9. Un-killable background thread on `run_inquiry()` timeout — unchanged, MVP-acceptable.
10. `ruff`: same 1 pre-existing cosmetic nit (`task_outputs.py:44`) — unchanged, confirmed still present, still not a regression.
11. **New, minor**: `contains_dispute_language`'s pinned phrase list is a single-incident-driven MVP starting set (per `sad.md`'s own Assumptions) — not exhaustively tuned against a larger corpus of real guest phrasing. Not a defect, but flagged (as `sad.md` itself already does) as a likely future `@qa-eng` tuning task once more real traffic/fixtures exist.

## 8. Acceptance criteria — incremental note

AC-002 (sentiment/frustration measurably affects response path) and AC-003 (no-fabrication, always flag escalation) both gain additional passing evidence this round: the dispute-language condition is a new, independent, deterministic escalation path that is neither sentiment- nor grounding-based, and is now directly unit- and live-verified (§3 above). No AC's pass/fail status changes from the 2026-09-01 pass's table (still 9/11 pass on direct automated evidence; AC-005/AC-009 remain out of automated-QA scope per `sad.md`'s own framing) — this round added strength to existing passes, not a new AC.

## Overall QA Verdict (2026-09-02)

**Functional acceptance criteria: still 9/11 pass on direct automated evidence** (unchanged from 2026-09-01; AC-005/AC-009 remain architectural-review-only per `sad.md`). The backend automated suite has grown from 75 to **150 passing tests, 0 failures**, with the previously-broken mypy environment now fixed and re-verified clean (20 source files). The specific bug this round targeted — a dispute/chargeback threat message failing to escalate — is fixed, and was verified **both live end-to-end (`POST /chat` → `GET /interactions` → `GET /interactions/{id}/trace`, real Anthropic API calls) and via the automated test suite**, not unit-tests-only. `sad.md`'s ADR-002 Addendum and its downstream §2/Typed-Task-Outputs edits are internally consistent with the shipped code — the exact SAD-drift failure mode flagged in the 2026-09-01 pass was not repeated. No new provenance/process gaps were found in this round's `backend.md`/`frontend.md` entries. **The report's outstanding blockers for a clean Deliver sign-off are unchanged from 2026-09-01**: the SAD §7 latency-spike gate (Known Defect #1) and the undocumented `MAX_EXECUTION_TIME_SECONDS` deviation (Known Defect #2) are both still open and still require an explicit operator decision; the zero-frontend-tests gap (Known Defect #4) also persists. This report does not itself authorize proceeding to Deliver.

**Recommendation, per this persona's standing instruction**: `@security.eng` should run `*assess-security` next. `aamad.config.yml` still sets `security.require_security_assessment: true`, `delivery-workflow.md` prefers a security assessment before Deliver, and `project-context/2.build/security.md` still does not exist (confirmed via directory listing this session) — this is now the sole remaining gate-blocking artifact this QA action can identify as fully missing (as opposed to open-but-documented, like Defects #1/#2/#4 above).

## Sources (2026-09-02 pass)

- `project-context/1.define/sad.md` (full `git diff` read — ADR-002 Addendum in full, §2 step 4, Typed Task Outputs, Sources/Assumptions/Open Questions/Audit additions)
- `project-context/2.build/backend.md` (four new dated Audit entries, 2026-09-01/2026-09-02, read in full via `git diff`)
- `project-context/2.build/frontend.md` (new §13/§14, read in full via `git diff`)
- `backend/src/app/flows/escalation_gate.py`, `backend/src/app/flows/inquiry_flow.py`, `backend/src/app/persistence/trace_log.py`, `backend/src/app/main.py`, `backend/src/app/agents/pii_guard.py`, `backend/src/app/agents/reasoning_crew.py` (read directly, current working-tree content)
- `frontend/src/components/InteractionTracePanel.tsx`, `frontend/src/lib/mockOpsData.ts`, `frontend/src/types/ops.ts` (read directly)
- `backend/tests/unit/test_escalation_gate.py`, `backend/tests/unit/test_trace_log.py`, `backend/tests/integration/test_inquiry_flow.py` (read directly, plus fresh `pytest --collect-only` counts)
- Live verification performed this session (2026-09-02): `curl http://localhost:8000/health`; `pytest -q` (150 passed); `ruff check .`; `mypy src` (clean, 20 files); `npm run lint`; `npm run build`; a real `POST /chat` with the exact bug-report dispute message; `GET /interactions` and `GET /interactions/{id}/trace` against the resulting live interaction; `pytest --collect-only` on the three test files central to this round's changes
- `aamad.config.yml` (`security.require_security_assessment: true`, `runtime.target: crewai`, testing requirements)
- `project-context/3.deliver/deploy.md` (re-read; unchanged 2026-09-01 halt state, still lists `qa.md`/`security.md` as its two blockers)
- The 2026-09-01 QA pass above (used only to identify what changed since, not cited as current evidence for anything in this section)

## Assumptions (2026-09-02 pass)

- Anthropic account credits remain available (inferred from this session's live `pytest -q` run completing 150/150 with zero skips/errors, and the live `/chat` probe completing successfully) — consistent with the 2026-09-01 pass's same inference, not independently billing-confirmed.
- The backend instance live at `http://localhost:8000` during this session is treated as running the current on-disk code, based on direct evidence (the live `/trace` response included the new `duration_ms`/`latency_pass`/`meets_target` fields and the dispute-language escalation behaved correctly) rather than assumed from process start time alone.
- This report evaluates the working tree as found (branch `devops`, multiple uncommitted files per `git status`) — no code changes were made by this action, and no assumption is made about when or whether this tree will be committed.
- AC-005/AC-009 remain treated as out of automated-QA scope, unchanged rationale from the 2026-09-01 pass.

## Open Questions (2026-09-02 pass)

- All Open Questions from the 2026-09-01 pass that remain unresolved are carried forward unchanged: the SAD §7 latency-spike operator decision; the `MAX_EXECUTION_TIME_SECONDS` revert-vs-formally-amend decision; whether to introduce a frontend test runner; whether a persisted (not just ad hoc/scratch) browser-automation test suite should be built; mypy reinstallation is no longer needed (resolved) so that item is removed.
- **New, raised by `sad.md`'s own ADR-002 Addendum**: should the dispute/chargeback phrase list move into `domain_config.json` instead of staying a hardcoded Python constant? `sad.md` itself frames this as unresolved and leaning against — not decided here either, just surfaced again since it is still open.
- **New, raised by this pass**: `contains_dispute_language`'s phrase list is tuned from a single observed incident. Should `@qa.eng`/the operator define a small held-out fixture set of real or synthetic guest messages (beyond the current unit-test fixtures, which were written by the same action that implemented the fix) to independently validate the false-positive/false-negative rate before this is considered calibrated rather than provisional?
- `@security.eng`'s `security.md` still does not exist. This is now the single fully-missing (not just open-and-documented) gate-blocking artifact this QA pass can identify — recommended as the next action per this persona's standing instruction.

## Audit (2026-09-02 pass)

- **Timestamp**: 2026-09-02
- **Persona**: `@qa.eng`
- **Action**: `*qa` (fresh pass, superseding the 2026-09-01 pass's currency, not its historical record)
- **Resolved runtime**: `crewai` (`AAMAD_TARGET_RUNTIME` not set in this session's environment; resolved from `aamad.config.yml` `runtime.target: crewai`, no conflict)
- **Inputs read in full this session**: `sad.md` (full ADR-002 Addendum, §2 step 4, Typed Task Outputs, Sources/Assumptions/Open Questions/Audit diffs), `backend.md` (all four new 2026-09-01/2026-09-02 Audit entries), `frontend.md` (new §13/§14 in full), `escalation_gate.py`, `inquiry_flow.py`, `trace_log.py`, `main.py` (diff), `pii_guard.py`/`reasoning_crew.py` (diffs), `InteractionTracePanel.tsx`, `mockOpsData.ts` (diff), `ops.ts` (diff), `test_escalation_gate.py` (diff), `test_inquiry_flow.py` (diff), `deploy.md`, `aamad.config.yml`
- **Live verification performed**: `curl http://localhost:8000/health`; full `pytest -q` (150 passed, 0 failed, real Anthropic API calls); `ruff check .` (1 pre-existing nit, unchanged); `mypy src` (clean, 20 files — confirms the 2026-09-01 environment defect is fixed); `npm run lint` (clean); `npm run build` (clean); a real `POST /chat` with the exact bug-report dispute message against the live backend, cross-checked via `GET /interactions` (confidence=0.92/sentiment=0.68/grounded=true/outcome=escalated) and `GET /interactions/{id}/trace` (28 real chronologically-ordered events with populated per-step latency fields); `pytest --collect-only` on `test_trace_log.py` (40), `test_escalation_gate.py` (42), `test_inquiry_flow.py` (7) to independently confirm `backend.md`'s stated test-count arithmetic
- **Files changed/added**: `project-context/2.build/qa.md` (this section, appended — the 2026-09-01 section above is preserved verbatim, not edited or removed). No application code, `agents.yaml`, or other build-phase artifact was modified.
- **Prohibited actions confirmed avoided**: no fixes applied to any open defect (latency gate, ceiling deviation, phrase-list tuning, frontend test gap); no application code, test file, or non-qa.md build artifact modified; the live `/chat` probe used a scratch `sender_id` (`qa-dispute-test-1`) and no scratch database/log files were committed.
- **Model/temperature/token controls**: n/a for this persona — no LLM calls were made by the QA action itself; the live `/chat` probe and `pytest` run exercise the application's own configured agents, whose model/temperature/token controls are documented in `backend.md` §7, unchanged by this action.

---

# Original QA Pass — 2026-09-01 (preserved for history; superseded by the fresh pass above)

## Input Requirements

**PRD**: `project-context/1.define/prd.md` §4 (Functional Requirements), §5 (Non-Functional Requirements), §7 (Success Metrics)
**SAD**: `project-context/1.define/sad.md` §7 (Performance & Scalability — p95 ≤ 5s target, 10s hard ceiling, mandatory latency-spike gate), §9 (Testing & QA — AC-001 through AC-011 acceptance suite)
**System Description**: `project-context/1.define/system-description.md` (AC-001–AC-009 definitions)
**Build artifacts reviewed**: `project-context/2.build/backend.md`, `backend-test-report.md`, `frontend.md`, `integration.md`, `setup.md`
**`aamad.config.yml`**: `security.require_security_assessment: true`; `testing.require_unit_tests/require_integration_tests/map_to_acceptance_criteria: true`
**Selected Runtime**: `crewai` (`aamad.config.yml` `runtime.target: crewai`; `AAMAD_TARGET_RUNTIME` not set in this session's environment — no conflict)
**Scope of this action**: `*qa` — validate the MVP build against AC-001–AC-011, run the available automated test suites live (not just cite historical logs), and produce this artifact so the Deliver-phase Phase Gate (`delivery-workflow.md`) can evaluate readiness. QA is read/verify/report only — no application code, `agents.yaml`, or other build-phase artifact was modified by this action.
**Trigger**: `project-context/3.deliver/deploy.md` (untracked, written 2026-09-01 by `@devops.eng`) halted at the Deliver Phase Gate specifically because `qa.md` did not exist, and named `@qa.eng` (`*qa`) as the unblock step. This document is that handoff.

## Action Log

### 1. Backend automated suite — run live this session (2026-09-01), not cited from history

Ran from `backend/` inside `backend/.venv` (Python 3.11.16), with a real `ANTHROPIC_API_KEY` present in `backend/.env`:

```
pytest -q                 -> 75 passed, 0 failed, 0 skipped, 135.62s (real live Anthropic API calls — no skips observed)
ruff check .              -> 1 pre-existing nit (task_outputs.py:44, E501, 102>100 chars) — not a regression
mypy src                  -> COULD NOT RUN (environment defect, see §4 below) — not verified fresh this session
```

The 75-passed/0-failed pytest result matches `backend-test-report.md` (2026-08-21, also 75/75) and improves on `integration.md`'s §14 finding (74 passed / 1 failed, a live-API timing race in `test_run_inquiry_degrades_to_escalate_on_timeout`, 2026-08-24) — that flake is not reproducing today. Full breakdown (7 integration test files + 5 unit test files, all passing) is unchanged from `backend-test-report.md`'s inventory; not re-transcribed here — see that file for the full per-test list.

### 2. Frontend static verification — run live this session

```
npm run lint    (oxlint)      -> clean, 0 errors/warnings
npm run build   (tsc -b + vite build) -> succeeded, dist/ produced, 490ms
```

Matches `integration.md` §14's 2026-08-24 result (`tsc -b` clean, `oxlint` clean, `vite build` succeeded) — no regression across the three commits since (`35d742e`, `0a71239`, `73a5063`, all pre-dating this session).

**Gap, not new**: no frontend automated unit/component test suite exists (`package.json` has no `test` script; no Vitest/RTL configured). `frontend.md` flags this gap at every feature addition (§7, §9, §10, §11, §12 Open Questions) and it was never resolved. This means `aamad.config.yml`'s `testing.require_unit_tests: true` / `require_integration_tests: true` is satisfied on the backend (75 automated tests, all mapped to AC IDs below) but **not** on the frontend — there is no automated frontend test evidence, only manual/live `curl` + build/type-check verification (`integration.md` §10–§14).

### 3. Fresh live latency probe (2026-09-01) — partial re-run of the still-open SAD §7 gate

`backend.md` §15 (2026-08-22) recorded the mandatory SAD §7 latency spike as incomplete: 14/20 valid measurements (6 failed on real Anthropic account credit exhaustion), with the `general_complaints` category at 0/5 valid — short of the SAD's 20+-request, all-categories requirement. This session's task explicitly allowed for that gap to still be blocking; however, the live pytest run in §1 above completed with **zero skips and zero credit-exhaustion errors**, indicating Anthropic account credits are available again today. Given that, a small fresh probe was run to get current data rather than relying solely on the 2026-08-22 numbers, using the same method as `backend.md` §15 (direct `InquiryFlow().kickoff()` calls, bypassing `run_inquiry()`'s timeout wrapper so durations are real/uncapped; scratch `INTERACTION_LOG_DB_PATH`, not `backend/data/app.db`; scratch script written to the QA scratchpad, not committed).

**8 requests, 2 per FR-013 scenario category** (a partial refresh, not a full 20+ re-run — see Open Questions):

| # | Category | Duration (s) | Outcome |
|---|---|---|---|
| 1 | reservations_booking | 14.00 | responded |
| 2 | reservations_booking | 11.68 | responded |
| 3 | checkin_checkout_billing | 11.95 | responded |
| 4 | checkin_checkout_billing | 14.39 | responded |
| 5 | room_service_amenities | 11.47 | responded |
| 6 | room_service_amenities | 12.86 | responded |
| 7 | general_complaints | 30.02 | responded |
| 8 | general_complaints | 14.25 | **escalated** (real `escalation_gate` decision on a frustrated-tone message, not a timeout) |

**Stats (n=8)**: min 11.47s / p50 13.43s / max 30.02s / mean 15.08s. **8/8 (100%) exceeded the SAD §7 5s p95 target and the SAD-documented 10s hard ceiling.** This is consistent with every prior measurement in `backend.md` (informal timings, §10/§11/§14) and the formal 2026-08-22 spike (n=14: min 11.13s/p50 13.12s/p95 17.29s/max 19.25s) — the latency problem is real, reproducible, and unresolved. This probe also produced the first-ever valid `general_complaints` data points (that category had 0/5 in the 2026-08-22 spike), and the one `escalated` result there is a correct, non-timeout `escalation_gate` decision — anecdotal confirmation that AC-002 (sentiment measurably affecting the response path) behaves correctly live, not just in unit tests.

**This does not close the SAD §7 gate.** 8 requests (2/category) is smaller than the spec's 20+/4-category requirement, and is reported as a fresh data point supplementing, not replacing, a proper follow-up spike. See Open Questions.

### 4. Finding — undocumented deviation from the SAD §7 hard ceiling, found during this review

While reading `backend/src/app/flows/inquiry_flow.py` to run the probe in §3, its module docstring was found to state: *"DEVIATION FROM SAD §7 (recorded, not silent — operator-directed, 2026-08-24): ... The ceiling was raised to 30s as a crude, immediate unblock..."* — `MAX_EXECUTION_TIME_SECONDS = 30`, not the `10` that `sad.md` §7 (line 227, unedited) still specifies and that every build artifact (`backend.md`, `backend-test-report.md`, `integration.md`) describes as the live ceiling.

Traced via `git log -p --follow -- backend/src/app/flows/inquiry_flow.py`: the change landed in commit `624ae19` ("Wire frontend to real backend; add escalation-resolution queue", 2026-08-24), the same commit `integration.md` documents. The commit message itself is transparent about the change ("Also raises InquiryFlow's max_execution_time from 10s to 30s... Documented as a deliberate deviation, not a fix"), but:

- **`integration.md` §2 states "CORS — added to `backend/src/app/main.py` (the only backend change this run)"** — this is incomplete: the same commit also modified `backend/src/app/flows/inquiry_flow.py`'s SAD-pinned timeout constant. Neither `integration.md` nor `frontend.md` (also touched in this commit, documenting the new `EscalationResolutionQueue.tsx` feature in §11) records this change anywhere in their Action Log/Assumptions/Sources/Audit sections.
- **`sad.md` itself was not amended** — it still reads "10s" with no recorded ADR update, so the codebase and the SAD are now silently out of sync.
- The claimed justification ("operator-directed") exists only as a code comment, with no artifact's Audit trail attributing *who* directed it or *when* it was confirmed, contrary to `aamad-core.md`'s Reproducibility/Provenance principle ("every artifact includes Sources, Assumptions... Agents MUST read only declared inputs and write only to declared outputs").

**Practical effect, not previously documented**: because the real ceiling is 30s (not 10s), 7 of the 8 requests in §3's probe completed with a real `responded`/`escalated` outcome rather than the generic timeout-escalation message — a materially better user-facing result than `backend.md`'s Open Questions and `integration.md` §11/§13 predicted under the (still textually current) 10s ceiling. This is a genuine improvement in observed behavior, but it was achieved by quietly loosening the safety ceiling rather than by fixing the underlying latency, and it means `integration.md`'s reproduced "escalate-on-timeout is the common case" finding (2026-08-24) is now stale relative to the code as it currently stands — flagged here so a future reader isn't misled by either artifact alone. Not fixed or reverted by this action (QA is read/verify/report only) — see Open Questions/Known Gaps.

### 5. mypy could not be verified this session — environment defect, not an app-code finding

`mypy src` (both `python -m mypy` and the `.venv`'s `mypy.exe` directly) fails immediately with `ModuleNotFoundError: No module named '<hash>__mypyc'` — mypy's own compiled (`mypyc`) extension module is missing/corrupted in `backend/.venv`. Reproduced twice, including after deleting `.mypy_cache`. This is a tooling/installation defect in this environment, not a code defect — `backend-test-report.md`'s last verified-clean mypy run (2026-08-21, "Success: no issues found in 19 source files") is the most recent real evidence available and is cited here rather than fabricated. **Recommendation**: reinstall mypy in `backend/.venv` (`pip install --force-reinstall mypy`) before the next QA/CI run that needs a fresh type-check result.

### 6. Acceptance criteria mapping (AC-001 through AC-011)

| AC | Requirement (abridged) | Evidence | Result |
|---|---|---|---|
| AC-001 | Chat response grounded in mock KB | `test_chat_endpoint.py` (5 passed, incl. live e2e), `test_inquiry_flow_end_to_end_per_scenario_category` (4 passed), §3 probe (6/8 `responded` with real composed replies) | **PASS** |
| AC-002 | Negative/frustrated sentiment measurably affects response path | `test_escalation_gate.py` (12 passed — all threshold boundaries), §3 probe (`general_complaints` frustrated message → real `escalated` decision, not timeout) | **PASS** |
| AC-003 | No-KB-match → simulated escalation, never fabricated | `ComposedResponse.grounded` structural enforcement (`compose_response_task`), `escalation_gate`'s `grounded == false` non-tunable branch, unit-tested via `test_escalation_gate.py` | **PASS** |
| AC-004 | Every processed interaction logs query/classification/sentiment/outcome | `test_interaction_log.py` (6 passed), `test_chat_endpoint.py::test_interactions_shows_record_after_chat_call` | **PASS** |
| AC-005 | New agent/tool integrates without rewriting existing agents | Architectural review criterion (`sad.md`: "reviewed structurally by `@system-arch`, not an automated test") | **Not automated-testable by QA** — structurally plausible (`config_loader.py`'s generic YAML→Agent/Task factory, per-agent YAML config) but this is a design review, not a test result; deferred to `@system.arch` sign-off |
| AC-006 | Simulated email inbox, same pipeline as chat | `test_email_endpoint.py` (5 passed, incl. live e2e), `integration.md` §11 live `/email` verification | **PASS** |
| AC-007 | PII (email/phone/account #) redacted before logging/LLM use | `test_pii_detector.py` (9 passed), `test_pii_redact_is_fail_closed_on_pii_guard_failure` | **PASS** |
| AC-008 | Hotel domain config drives classification/retrieval/response, not hardcoded | `test_knowledge_base.py` (8 passed), `domain_config.json`/`domain/loader.py` design | **PASS** |
| AC-009 | No domain-specific strings/logic hardcoded outside domain config layer | Architectural review criterion (`sad.md`: not an automated test for MVP) | **Not automated-testable by QA** — deferred to `@system.arch`/`@security.eng` review, consistent with `sad.md`'s own framing |
| AC-010 | Escalation resolution recorded, queued as candidate KB entry | `test_escalation_resolution_flow.py` (4 passed), `test_escalation_resolve_endpoint.py` (3 passed) | **PASS** |
| AC-011 | Reviewer approve(+edit)/reject gates every live-KB write | `test_review_queue_endpoints.py` (11 passed), `test_review_queue.py` (5 passed) | **PASS** |

**9 of 11 ACs pass on automated evidence; the remaining 2 (AC-005, AC-009) are architectural-review criteria the SAD itself scopes outside automated testing** — not a gap this action can close, and not treated as a failure.

### 7. Non-functional requirements

| NFR | Requirement | Result |
|---|---|---|
| NFR-001 (Usability) | Non-technical demo audience can use chat UI without instructions | Qualitative per PRD (no quantitative MVP target); not automated-tested — no reported usability issues in `frontend.md`/`integration.md` |
| NFR-002 (Performance) | Single-query resolution "within a few seconds" | **NOT MET** — see §3; every measured live request (22 across the 2026-08-22 spike + this session's probe) exceeds 10s, most exceed 15s |
| NFR-003 (Observability) | Interaction log inspectable | **PASS** — `GET /interactions`, `test_interaction_log.py` |
| NFR-004/NFR-006 (PII security) | PII minimized/redacted, redaction actions logged | **PASS** — `test_pii_detector.py`, fail-closed `pii_redact` design |
| NFR-005/NFR-007 (Scalability/Reliability, MVP-scoped) | New roles/tools addable without rewrite; domain swap via config only | Structurally supported by design (per-agent YAML config, `domain/loader.py`); not independently stress-tested (MVP scope, no throughput target) |
| NFR-008 (Data integrity) | Live KB mutable only via Reviewer approval | **PASS** — `test_review_queue_endpoints.py`, no code path bypasses the approve endpoint |

## Known Defects / Gaps (carried into Deliver, not fixed by this action)

1. **SAD §7 latency gate still open (Must-fix or must-waive before a clean Deliver sign-off).** p95 target (≤5s) and hard ceiling (10s, per `sad.md` text) are both missed by every real measurement to date (22 total data points across two sessions, 0% compliance). The formal 20+-request/4-category spike required by `sad.md` §7 has still never been completed cleanly (14/20 in 2026-08-22, 8 more via this session's supplementary probe — different methodology/sample, not a substitute for one clean 20+-request run). **Operator decision needed**: run a full clean spike, apply the pre-agreed fallback ladder (`backend.md` §15), formally raise the SAD's target/ceiling to match reality, or explicitly accept the gap for MVP demo purposes.
2. **Undocumented SAD §7 ceiling deviation in code** (§4 above): `inquiry_flow.py`'s `MAX_EXECUTION_TIME_SECONDS` is `30`, not the `10` every artifact and `sad.md` itself still state. Recorded only in a code comment and a commit message, not in any persona's Action Log/Audit, and `sad.md` was never amended. **Recommend**: either revert to 10s pending a real fix, or formally amend `sad.md` §7 and record the change in `backend.md`'s Audit trail — currently it is neither.
3. **mypy environment is broken** in `backend/.venv` (`ModuleNotFoundError` on mypy's own `mypyc` extension) — type-check cleanliness could not be freshly verified this session; last verified-clean run is 2026-08-21.
4. **Zero automated frontend tests** — no Vitest/RTL or equivalent configured; `aamad.config.yml`'s `testing.require_unit_tests`/`require_integration_tests` is fully satisfied on the backend only. Flagged repeatedly in `frontend.md`, never resolved.
5. **`POST /escalations/{id}/resolve` does not validate that the target interaction was actually escalated** — accepts any valid interaction id (documented, deliberate-but-unenforced, `backend-test-report.md` #4).
6. **Approved KB entries default to `candidate_keywords: []`** unless a Reviewer manually supplies keywords via edit — no keywords field exists in the Edit UI, so most approved entries are unretrievable by `kb_search`'s keyword-overlap scoring until this UI gap closes (`integration.md` §8/Open Questions).
7. **Two inconsistent API error-envelope shapes** (`{error_code, message}` vs. FastAPI's default `{detail: [...]}`) across the API surface — not fixed (`integration.md` Open Questions).
8. **No literal browser/Playwright-driven click-through test exists** for `/chat`, `/inbox`, or `/ops` — all frontend↔backend verification to date is `curl` + `tsc`/`vite build`, which reproduces request/response shapes but not actual browser rendering/interaction. No such tooling was available in this QA session either — carried forward as an open gap.
9. **Un-killable background thread on `run_inquiry()` timeout** (Python/stdlib limitation) — acceptable for MVP's no-concurrent-traffic scope, would need a real cancellation strategy before production/concurrent use.
10. `ruff`: 1 pre-existing cosmetic nit (`task_outputs.py:44`, line 2 chars over limit) — not a regression, not fixed (predecessor file, confirmed correct, not to be diverged from per its own build history).

## Defects Resolved Since Earlier Build Phases (confirmed still holding)

- `claude-sonnet-5` rejecting the `temperature` parameter (400 error) — fixed 2026-08-20 (`agents.yaml`), reconfirmed clean in this session's live 75/75 run.
- `run_inquiry()` blocking past its timeout ceiling + duplicate interaction-log rows — fixed 2026-08-20 (`inquiry_flow.py`/`interaction_log.py`), reconfirmed clean in this session's live 75/75 run.
- The intermittent `test_run_inquiry_degrades_to_escalate_on_timeout` flake `integration.md` §14 reported (2026-08-24, 74 passed/1 failed) did not reproduce in this session's clean 75/75 run.

## Overall QA Verdict

**Functional acceptance criteria (AC-001–AC-011): 9/11 pass on direct automated evidence; the remaining 2 are architectural-review criteria the SAD itself scopes outside automated testing — no automated-test failures found.** Backend automated test suite is comprehensive (75 tests, all currently passing, all traceable to AC IDs above) and satisfies `aamad.config.yml`'s testing requirements on the backend. The Deliver-phase Phase Gate's own wording ("qa.md... documents MVP verification results, pass or explicitly scoped known gaps") is satisfiable by this report **only if the gaps above — most importantly item 1 (unmet NFR-002/SAD §7 latency) and item 2 (undocumented ceiling deviation) — are explicitly accepted by the operator**, not silently carried forward. This report does not itself authorize proceeding to Deliver; per `delivery-workflow.md`, that is the operator's/`@devops.eng`'s call once these gaps are seen and accepted (or acted on).

## Sources

- `project-context/1.define/prd.md` (§4 Functional Requirements, §5 NFRs, §7 Success Metrics)
- `project-context/1.define/sad.md` (§7 Performance & Scalability, §9 Testing & QA, MVP Build Sequencing)
- `project-context/1.define/system-description.md` (AC-001–AC-009 definitions)
- `project-context/2.build/backend.md` (full build history; §15 2026-08-22 latency spike; Assumptions/Open Questions re: temperature, timeout/double-log fixes)
- `project-context/2.build/backend-test-report.md` (2026-08-21, 75/75 passed baseline)
- `project-context/2.build/frontend.md` (frontend build history; repeated "no frontend test runner" Open Questions)
- `project-context/2.build/integration.md` (2026-08-24 live wiring/verification; §11/§13 latency and browser-test gaps; §14 static verification)
- `project-context/2.build/setup.md`
- `project-context/3.deliver/deploy.md` (untracked, 2026-09-01 — `@devops.eng`'s Phase Gate halt that triggered this action)
- `aamad.config.yml` (testing/security requirements)
- `.claude/rules/aamad-core.md`, `.claude/rules/delivery-workflow.md`, `.claude/rules/adapter-crewai.md`
- Live verification performed this session (2026-09-01): `pytest -q` (75 passed), `ruff check .`, `mypy src` (failed — environment defect), `npm run lint`, `npm run build`, and an 8-request live `InquiryFlow` latency probe (scratch script, not committed; scratch SQLite db, not `backend/data/app.db`) — `git log -p --follow -- backend/src/app/flows/inquiry_flow.py` to trace the `MAX_EXECUTION_TIME_SECONDS` history

## Assumptions

- **Working-tree drift noted mid-session, not evaluated by this report.** Partway through this session (after §1's pytest run, §2's frontend checks, and §3's probe had already completed), `git status` showed new uncommitted changes not made by this action: `backend/src/app/persistence/trace_log.py` (new), `backend/tests/unit/test_trace_log.py` (new), and edits to `backend/src/app/agents/pii_guard.py`/`reasoning_crew.py` wiring in a CrewAI event-bus listener (adapter-crewai.md's "Trace Log" Logging requirement). File modification times (~17:22–17:25, this session) postdate this report's pytest/lint/build runs, so those results reflect the tree *before* this drift, not the current working-tree state. This looks like concurrent work by another process/persona rather than anything from this QA action — it was not reverted, re-tested, or otherwise acted on here (re-running against a possibly-still-in-progress concurrent edit seemed likelier to produce a misleading result than a useful one). Whoever picks this up next should re-run `pytest` fresh before relying on this report's exact pass count if `trace_log.py`/`test_trace_log.py` are still present and uncommitted.
- Anthropic account credits are currently available (inferred from this session's live pytest run completing 75/75 with zero skips/errors, and the 8-request probe completing with zero credit-exhaustion errors) — the 2026-08-22 spike's credit exhaustion appears to have been resolved (top-up or reset) between then and 2026-09-01, though no billing confirmation was directly observed; this is an inference from behavior, not a verified fact.
- The 8-request supplementary probe in §3 is treated as informative, real, unmodified data — but explicitly *not* a substitute for the SAD §7-mandated clean 20+-request/4-category spike, given its smaller sample size and different session/conditions than the 2026-08-22 run.
- `mypy`'s failure is assumed to be a local environment/installation defect (a corrupted or partially-installed `mypyc`-compiled binary in `backend/.venv`) rather than a code issue, based on the error occurring before any source file is even read and on `backend-test-report.md`'s prior clean run against the same source tree lineage.
- AC-005 and AC-009 are treated as out of automated-QA scope per `sad.md`'s own explicit framing ("reviewed structurally... not an automated test") — not scored as failures, not fabricated as passes either.
- This report evaluates the codebase as of `HEAD` on branch `devops` (commit `2eada3d`) plus the untracked `project-context/3.deliver/deploy.md`; no code changes were made by this action.

## Open Questions

- **Operator decision required**: how to resolve the SAD §7 latency gate — run a full clean 20+-request spike now that credits appear available, apply the fallback ladder (`backend.md` §15's 3 steps), formally revise the SAD's 5s/10s targets to match observed reality, or explicitly accept the gap for MVP-demo purposes and record that acceptance before Deliver proceeds.
- **Operator/`@backend.eng` decision required**: what to do about the undocumented `MAX_EXECUTION_TIME_SECONDS = 30` deviation (§4) — revert to the SAD's stated 10s, or formally amend `sad.md` §7 and backfill the missing Audit trail entry in `backend.md`/`integration.md` attributing the decision. Leaving it as-is means the SAD and the shipped code disagree with no recorded resolution.
- Whether `@qa.eng`/the operator wants a dedicated frontend test runner (Vitest/RTL) introduced before Deliver, given `aamad.config.yml`'s `testing.require_unit_tests`/`require_integration_tests` currently has zero frontend coverage — this report does not resolve that, only surfaces it (carried from `frontend.md`, not newly discovered).
- Whether someone with a supported browser-automation tool should perform an actual click-through UI verification of `/chat`, `/inbox`, and `/ops` before Deliver — no such tool was available in this or the prior (`integration.md`) session.
- mypy should be reinstalled in `backend/.venv` and re-run before the next artifact that needs a fresh type-check attestation.
- Carried, unresolved from earlier artifacts (not this persona's to resolve): actual project budget; which PII regulation (if any) applies; MVP hosting/infrastructure target (`@devops.eng`).
- `@security.eng`'s `security.md` still does not exist — `aamad.config.yml` sets `security.require_security_assessment: true`, and `delivery-workflow.md` prefers it before Deliver. This qa.md unblocks one of `deploy.md`'s two stated blockers; the security assessment is the other, and remains outstanding.

## Audit

- **Timestamp**: 2026-09-01
- **Persona**: `@qa.eng`
- **Action**: `*qa`
- **Resolved runtime**: `crewai` (`AAMAD_TARGET_RUNTIME` not set; resolved from `aamad.config.yml` `runtime.target: crewai`, no conflict)
- **Inputs read in full**: `backend.md`, `backend-test-report.md`, `frontend.md`, `integration.md`, `setup.md`, `prd.md`, `sad.md` (relevant sections), `system-description.md` (AC definitions), `aamad.config.yml`, `project-context/3.deliver/deploy.md`, `backend/src/app/flows/inquiry_flow.py`, `backend/tests/integration/test_inquiry_flow.py`
- **Live verification performed**: `pytest -q` (75 passed, 0 failed, 135.62s, real Anthropic API calls), `ruff check .` (1 pre-existing nit), `mypy src` (failed — environment defect, not app code), `npm run lint` (clean), `npm run build` (clean), 8-request live `InquiryFlow` latency probe (scratch, not committed), `git log -p --follow` on `inquiry_flow.py` to trace the undocumented timeout-ceiling change
- **Files changed/added**: `project-context/2.build/qa.md` (this file, new). No application code, `agents.yaml`, or other build-phase artifact was modified.
- **Prohibited actions confirmed avoided**: no fixes applied to the latency gap, the undocumented ceiling deviation, the mypy environment, or any other defect found — all recorded as findings for the appropriate persona/operator, per QA's read/verify/report scope.
- **Model/temperature/token controls**: n/a for this persona — no LLM calls were made by the QA action itself (the live pytest run and latency probe exercise the *application's* configured agents, whose model/temperature/token controls are documented in `backend.md` §7, unchanged by this action).
