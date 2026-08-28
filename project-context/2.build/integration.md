# Integration Build Log — customer-support-agent

## Input Requirements

**PRD**: `project-context/1.define/prd.md` §4 (Chat inquiry intake & classification, Knowledge-grounded response, Sentiment-aware handling, Simulated escalation), FR-007/FR-008/FR-009/FR-010/FR-014, NFR-003, NFR-008
**SAD**: `project-context/1.define/sad.md` §3 (Frontend Architecture Specification), §4 (Backend Architecture Specification / API Architecture — request/response shapes for `POST /chat`, `POST /email`, `POST /escalations/{id}/resolve`, `GET /interactions`, `GET /review-queue`, `POST /review-queue/{id}/approve`, `POST /review-queue/{id}/reject`)
**Backend build**: `project-context/2.build/backend.md` (all endpoints implemented, §15's SAD §7 latency-spike results — directly relevant to this run's verification findings, see below)
**Frontend build**: `project-context/2.build/frontend.md` §1–§10 (mock client modules as the designated swap points, §9.5/§10.5 ambiguity-resolution convention followed here)
**Selected Runtime**: `crewai` (`AAMAD_TARGET_RUNTIME=crewai` env var and `aamad.config.yml runtime.target: crewai` agree — no conflict to record)
**Scope of this action**: `*integrate-api` → `*verify-messageflow` → `*log-integration`, on branch `integration`. Wire the existing React frontend to the existing FastAPI backend for `/chat`, `/inbox`, `/ops`. No new UI, no new endpoints, no authentication, no streaming (persona contract: "No external APIs or advanced integrations—MVP only!").

## Action Log (`*integrate-api`)

### 1. What was already in place (not redone)

Read in full before making changes: `backend/src/app/main.py` (all seven routes, error envelope conventions), all three mock client modules (`frontend/src/lib/mockInquiryClient.ts`, `mockEmailClient.ts`, `mockOpsData.ts`) and their consuming components (`ChatWindow.tsx`, `EmailInbox.tsx`, `InteractionLog.tsx`, `ReviewQueue.tsx`, `ReviewQueueItem.tsx`, `InteractionLogTable.tsx`), and the shared type files (`types/chat.ts`, `types/email.ts`, `types/ops.ts`). All three mock modules were built by `@frontend.eng` as explicit swap points with matching function signatures/return shapes for `/chat` and `/inbox`; `/ops` was flagged in advance (frontend.md §10.7) as needing real mapping work. Confirmed no other file touches `fetch`/`axios` directly.

### 2. CORS — added to `backend/src/app/main.py` (the only backend change this run)

No `CORSMiddleware` existed. The Vite dev server (`http://localhost:5173`, falling back to `5174` if `5173` is taken — see frontend.md §9.7) and the FastAPI backend (`http://localhost:8000`) are different origins, so uncontrolled browser `fetch()` calls would fail at the CORS layer before ever reaching a route (this is invisible to `curl`-based manual testing, which is why `@backend.eng`'s own testing never surfaced it — CORS is enforced by the browser, not the server, for same-origin/non-browser clients).

Added `fastapi.middleware.cors.CORSMiddleware` immediately after `app = FastAPI(...)`:
- `allow_origins`: resolved from a new optional env var `CORS_ALLOWED_ORIGINS` (comma-separated), defaulting to `http://localhost:5173,http://localhost:5174` if unset. sad.md does not pin an allowed-origins list — this is an `@integration.eng` judgment call, documented inline in `main.py` and here, rather than a wildcard (`*`), to keep the default dev-safe and explicit.
- `allow_credentials=False` — this MVP has no authentication/cookies, so no credentialed cross-origin requests are needed.
- `allow_methods=["GET", "POST"]` — matches the full set of methods any route in `main.py` actually uses; no `PUT`/`DELETE`/`PATCH` exist.
- `allow_headers=["Content-Type"]` — the only non-simple header any client in this app sends.
- Added `CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174` to `backend/.env.example` for documentation (no value was added to `backend/.env` — the default already covers this environment's actual ports; not overriding an already-present, working file unnecessarily).

### 3. New shared file: `frontend/src/lib/apiClient.ts`

Not part of `@frontend.eng`'s original scaffold — introduced this run because all three swap targets need identical base-URL resolution (`VITE_API_BASE_URL`, with a same-value fallback + `console.warn` if unset, rather than a hard crash) and identical `{error_code, message}` error-envelope parsing (sad.md §4). Exports `apiFetch<T>(path, init)` and an `ApiError` class (`status`, `errorCode`, `message`). No existing component imports this file directly — only the three `lib/mock*.ts` modules do — so it does not change any component's contract, and is not itself one of "the three mock client modules," just infrastructure they share.

### 4. `frontend/src/lib/mockInquiryClient.ts` → real `POST /chat`

Filename and the `sendInquiry(message: string): Promise<InquiryResult>` export signature are **unchanged** — `ChatWindow.tsx` was not touched. Body replaced with a real `apiFetch("/chat", {method: "POST", body: JSON.stringify({message, session_id})})` call.

**Session id judgment call** (flagged as a gap in frontend.md, resolved here): the backend requires `session_id` but nothing in the frontend previously generated one. Resolved by generating a `crypto.randomUUID()` once per browser tab and caching it in `sessionStorage` (`csa_chat_session_id`), entirely inside `mockInquiryClient.ts` — not threaded through `ChatWindow.tsx`'s props/state, since a transport-level session id is not something the UI needs to own or display. Falls back to a fresh per-call UUID if `sessionStorage` throws (e.g. locked-down browser contexts) rather than crashing the chat flow — documented as an accepted MVP degradation in Assumptions.

**Error handling judgment call**: on a network failure or non-2xx response, `sendInquiry` no longer rejects — it resolves with `{reply: <honest "having trouble reaching support" message>, escalated: true}`, reusing the existing `EscalationNotice` UI (`ChatMessage.kind === "escalation"`) rather than building a new error component. This matches the mock's original contract (`sendInquiry` never rejected) so `ChatWindow.tsx` needed no changes, and it never fabricates a canned/grounded-looking answer on failure (AC-003).

### 5. `frontend/src/lib/mockEmailClient.ts` → real `POST /email`

Clean swap, as anticipated by both `@frontend.eng` and this run's task brief — `EmailComposeInput`/`EmailResult` already match the backend's `{from, subject, body}` → `{reply_body, escalated}` shape exactly, no field mapping needed. Same error-handling pattern as `sendInquiry` (never rejects; degrades to an honest escalation-shaped reply on failure, reusing `EmailEscalationNotice`). `EmailInbox.tsx` was not touched.

### 6. `frontend/src/lib/mockOpsData.ts` → real `GET /interactions`, `GET /review-queue`, `POST /review-queue/{id}/approve`, `POST /review-queue/{id}/reject`

Function signatures and the `InteractionLogEntry`/`ReviewQueueEntry` return shapes (`types/ops.ts`) are unchanged — no component contract changes — but the real backend's field names/types don't match those frontend types 1:1, so this module now does real mapping work the mock never needed. Two judgment calls here, written up in full below (§7, §8), mirroring frontend.md's §9.5/§10.5 convention.

`getInteractions`/`getReviewQueue` now call the real endpoints and map each row through `toInteractionLogEntry`/`toReviewQueueEntry`. `approveReviewQueueEntry`/`rejectReviewQueueEntry` call the real `POST` endpoints, then re-fetch `GET /review-queue` and return the freshly mapped entry for that `id` (see §8) rather than hand-synthesizing one from the narrower response the real endpoints return.

### 7. Judgment call — `InteractionLogEntry` mapping (`GET /interactions`)

The frontend's pre-existing `InteractionLogEntry` (`timestamp: number`, `query`, `classification`, `sentimentScore`, `sentimentLabel`, `piiRedacted: boolean`, `outcome: "resolved" | "escalated"`) doesn't match the backend's `InteractionRecord` (`created_at: string` (ISO), `query_text`, `intent`, `sentiment_score`, `sentiment_label`, `redaction_count: int`, `outcome: "responded" | "escalated" | "diagnostic_halt"`). Resolved in `toInteractionLogEntry` (`mockOpsData.ts`):
- `timestamp = Date.parse(created_at)`; `query = query_text`; `classification = intent ?? "Unclassified"` (nullable on diagnostic-halt/timeout rows — see §11 below); `sentimentScore = sentiment_score ?? 0`; `sentimentLabel = sentiment_label ?? "Neutral"` (same nullability).
- `piiRedacted = redaction_count > 0` — the frontend has no concept of a redaction *count*, only a boolean; any non-zero count is treated as "redacted."
- `outcome`: the frontend only models two states. Backend's third state, `"diagnostic_halt"` (a caught internal failure, distinct from the reasoning-agent-driven `escalation_gate` decision), is mapped to `"escalated"`, not `"resolved"` — a halted interaction is exactly the "needs a human to look at this" case the existing escalated-column UI treatment already communicates; collapsing it into `"resolved"` would misrepresent a failure as a successful response. `"responded"` maps to `"resolved"`.

### 8. Judgment call — `ReviewQueueEntry` mapping and the write-direction title/section mapping (`GET`/`POST /review-queue/...`)

The frontend's `ReviewQueueEntry` has `proposedTitle` — the backend has **no title field at all**, only `candidate_intent` (a technical classification/retrieval key — see `backend/src/app/domain/loader.py`'s `kb_search`: `ADR-005` filters candidate entries by `entry.intent == intent` *before* keyword-scoring) and `candidate_section` (a human-readable heading, e.g. `domain_config.json`'s `"section": "Cancellation policy"`).

**Read direction** (`toReviewQueueEntry`): `proposedTitle = candidate_section || candidate_intent || "Untitled candidate KB entry"` — prefer the human-readable section heading (what a Reviewer actually reads as a "title"); fall back to the intent slug only if no section was ever set (in practice, `EscalationResolutionFlow` always sets `candidate_section = "operator_resolution"`, confirmed live in §12 below, so this fallback is currently unreachable but kept for defensiveness); a final literal fallback so the column is never blank.

**Write direction** (`approveReviewQueueEntry`): the Edit UI's single `title` field (`ReviewQueueDecisionInput = {title, content}`) is submitted to the approve endpoint's `{intent?, section?, keywords?, content?}` body as `section`, **not** `intent`. `intent` is deliberately left unset (falls back to the stored `candidate_intent`) because it is the machine-facing filter key `kb_search` uses to select candidates before scoring — silently overwriting it from free-text "title" edits could make the approved entry unretrievable for its original intent, or retrievable under the wrong one. `content` maps directly. `keywords` is left unset (falls back to stored `candidate_keywords`, always `[]` per `EscalationResolutionFlow`'s own docstring) — the Edit UI has no keywords field, so there is nothing to map; this is a real, pre-existing retrievability gap (an approved entry with `keywords: []` can never be matched by `kb_search`'s scoring, per `main.py`'s own `ApproveReviewQueueRequest` docstring) that this run does not fix, since fixing it would mean adding a new keywords field to `ReviewQueueItem.tsx` — new UI, out of scope. Flagged in Open Questions below, not silently worked around.

**Response-shape mismatch on approve/reject**: the mock's `approveReviewQueueEntry`/`rejectReviewQueueEntry` returned the full updated `ReviewQueueEntry` directly. The real `POST /review-queue/{id}/approve` returns a `KBEntryResponse` (the newly written *KB* entry: `kb_entry_id`/`intent`/`section`/`keywords`/`content` — no `status`, no review-queue `id`-shaped record at all), and `POST .../reject` returns only `{id, status}`. Rather than hand-assembling a `ReviewQueueEntry` from either response (which would require assuming, not confirming, the resulting `status`), both functions re-fetch `GET /review-queue` after a successful action and return the freshly mapped entry for `id` — one extra round trip, but keeps client state as server-truth rather than a client-side guess, consistent with this MVP having no optimistic-update requirement anywhere else.

**`decidedAt` approximation**: the backend does not persist a real decision timestamp. For non-pending rows, `decidedAt = Date.parse(created_at)` (queue-creation time, not actual decision time) — chosen over `Date.now()` at fetch time specifically because `created_at` is stable across repeated fetches, so `ReviewQueue.tsx`'s "Recently decided" sort stays deterministic instead of reshuffling on every refetch. This is a known imprecision, documented rather than silently assumed.

### 9. Minimal, necessary component edits (deviation from "don't touch components")

Two components were edited, beyond the "don't touch unless a function signature genuinely must change" instruction — both changes are additive error-handling, not signature or structural changes, and were judged necessary to satisfy `*verify-messageflow`'s explicit requirement that "error responses ... surface sensibly ... rather than an unhandled promise rejection," which the mock-era code could not violate (the mocks never rejected) but the real backend calls can:

- **`InteractionLog.tsx`**: `getInteractions().then(...)` had no `.catch`. A real fetch failure would leave the component in a permanent "Loading…" state plus an unhandled promise rejection in the console. Added a `.catch` that sets a `loadError` string, rendered via the same plain-`<p>` pattern already used for the loading/empty states immediately below it — no new component, no new visual language.
- **`ReviewQueue.tsx`**: same gap on `getReviewQueue().then(...)`, plus `handleApprove`/`handleReject` had `try { ... } finally { ... }` with no `catch` — a 404/409/422 from the backend (all real, reachable cases — see §12) would silently clear the busy state with no visible feedback and an unhandled rejection. Added `catch` blocks that write a human-readable failure message into the component's **existing** `statusMessage` `role="status" aria-live="polite"` paragraph (previously only used for success confirmations) — reusing that exact element rather than adding a new error UI, per the task's explicit "reuse existing patterns" instruction.

`ChatWindow.tsx` and `EmailInbox.tsx` needed no equivalent edit — `sendInquiry`/`sendEmail` never reject (see §4/§5), so their existing `try { ... } finally { ... }` (no `catch`) is already correct.

## Action Log (`*verify-messageflow`)

### 10. Environment

Both backend (port 8000) and frontend (port 5173) were already running from an earlier manual start, confirmed via `curl http://localhost:8000/health` (`{"status":"ok"}`) and `curl -o /dev/null -w "%{http_code}" http://localhost:5173/` (`200`) before touching anything. Both were **restarted** (stopped the existing processes, started fresh with the same documented commands) after code changes: the backend to load the new `CORSMiddleware`, the frontend after creating `frontend/.env.local` (copied from `.env.example`, `VITE_API_BASE_URL=http://localhost:8000`) so Vite picks it up — `.env.local` did not previously exist; the app was running on the code's built-in default fallback (same value) until this point.

### 11. `/chat` round trip — including the specific "cancellation policy" scenario, and a blocker found

`curl -X POST http://localhost:8000/chat -H "Origin: http://localhost:5173" -d '{"message":"what is the cancellation policy?","session_id":"verify-session-1"}'` (repeated 4 times total, with minor phrasing variants, across ~10 minutes):

**Every single attempt** (4/4) returned, after **~10.3 seconds** each:
```json
{"reply":"Thanks for your patience. This is taking longer than expected, so I've flagged it for a team member to review personally.","escalated":true}
```
— the generic timeout-escalation message, **not** the grounded `kb-res-001` cancellation-policy answer the task brief expected this run to confirm. Cross-checked against `GET /interactions`: each of these calls logged a row with `outcome: "escalated"`, `intent: null`, `match_found: null`, `grounded: null`, and `query_text: "[UNAVAILABLE - FLOW EXCEEDED MAX_EXECUTION_TIME]"` — confirming `run_inquiry()`'s `ThreadPoolExecutor` 10-second hard ceiling (sad.md §7) was hit before `InquiryFlow` even finished classification, not a slow-but-eventually-grounded response.

**This is not an integration defect.** It is the exact outcome `project-context/2.build/backend.md` §15 (SAD §7 latency spike, 2026-08-22) already measured and flagged as a blocker: 14/14 valid sampled requests in that spike exceeded both the 5s target and the 10s ceiling (p50 13.12s, p95 17.29s), with the explicit finding "every one of these 14 requests would have hit the `FutureTimeoutError` path... escalate-on-timeout is the common case, not a rare degradation." This run's live verification reproduces that finding at 100% (4/4) for the specific chat scenario the task brief cared about. **The wiring itself is confirmed correct** — the real request reaches `POST /chat`, is processed by the real `InquiryFlow`, and a real (if degraded) response comes back over a working CORS-enabled connection — but the user-visible outcome for "what is the cancellation policy?" today is the timeout escalation, not the grounded KB answer, until `@backend.eng`/the operator address the latency-vs-ceiling gap already tracked in backend.md's Open Questions (fallback-ladder steps 1–3, not applied by design in that run). Flagged again here as a live, reproduced blocker — see Open Questions.

`POST /email` was also tested with an equivalent cancellation-policy question and hit the identical ~10.3s timeout path — confirming this is systemic to `InquiryFlow` (both channels share it), not `/chat`-specific.

### 12. `/ops` round trip — `GET /interactions`, escalation → review-queue → approve/reject, and error paths

- `GET /interactions` (with `Origin: http://localhost:5173`): 200, real rows returned, including the 4 timeout rows from §11 and older rows from `@backend.eng`'s own Phase 2/3 testing (some with `grounded: true`, confirming the KB-retrieval path itself works when the flow completes inside the ceiling — the timeout is a latency problem, not a KB/retrieval defect).
- `GET /review-queue`: 200, `[]` initially (no prior escalations resolved in this session).
- Used `POST /escalations/{id}/resolve` (not otherwise part of this run's scope — see Open Questions) as a test harness to populate the review queue, since nothing else in the app can. Resolved two prior escalated interactions with distinct resolution text.
- `POST /review-queue/{id}/approve` with an edited body (`{"section": "Housekeeping requests", "content": "..."}`, exercising the title→`section` mapping from §8): 200, returned a real `KBEntryResponse` with `kb_entry_id`, `section` reflecting the override, `intent` correctly preserved from the stored candidate (not overwritten by the edit) — confirms the write-direction mapping decision in §8 behaves as designed.
- `POST /review-queue/{id}/reject` on a second entry: 200, `{"id": ..., "status": "rejected"}`.
- **Error paths, all confirmed live**:
  - Re-approving an already-approved entry: `409 {"error_code":"review_queue_already_actioned", ...}`.
  - `POST /review-queue/does-not-exist/reject`: `404 {"error_code":"review_queue_entry_not_found", ...}`.
  - Approving an entry with a `null` `candidate_intent` and no override: `422 {"error_code":"invalid_kb_entry", ...}` — confirms `mockOpsData.ts`'s `apiFetch` correctly surfaces this through `ApiError`, and `ReviewQueue.tsx`'s new `catch` block (§9) would display it via the existing status paragraph.
  - `POST /chat` with a missing `session_id` field: `422`, but with FastAPI's **built-in** validation-error envelope (`{"detail": [...]}`), not the app's own `{error_code, message}` shape used by every other error case in `main.py`. `apiClient.ts`'s `ApiError` handles this gracefully (falls back to a generic "Request ... failed with status 422" message rather than crashing on the missing `message` field), but the two envelope shapes are inconsistent — noted in Open Questions, not fixed (would require a `main.py` change beyond CORS, out of this run's stated backend-touch scope).
- Test data left in place: this exercised the real, running `backend/data/app.db` (one new approved `kb-approved-*` KB entry, one rejected review-queue row, plus the interaction-log/review-queue rows from §11/this section). Not reset — consistent with this being live dev-environment verification, not an isolated test run; flagged in Assumptions.

### 13. CORS verification

- `OPTIONS /chat` preflight with `Origin: http://localhost:5173`, `Access-Control-Request-Method: POST`, `Access-Control-Request-Headers: Content-Type`: `200`, `access-control-allow-origin: http://localhost:5173`, `access-control-allow-methods: GET, POST`, `access-control-allow-headers: ... Content-Type`.
- Real `GET`/`POST` calls with `Origin: http://localhost:5173` set: all returned `access-control-allow-origin: http://localhost:5173` on the actual response, not just the preflight.
- **Not performed**: an actual browser-driven request from a page served at `localhost:5173` (no browser/Playwright tool was available in this execution environment — only `Bash`/`Read`/`Edit`/`Write`/`Grep`/`Glob`). The `curl`-with-`Origin`-header checks above reproduce exactly what a browser's CORS check inspects (the response headers for a given request `Origin`), and `npm run build`/`tsc -b` (below) confirm the client code type-checks against the real response shapes — but no literal click-through UI test was done. Flagged as a verification gap, not silently claimed as done.

### 14. Static verification

- `npx tsc -b` (frontend): clean, no errors.
- `npm run lint` (`oxlint`): clean, no errors/warnings.
- `npm run build` (`tsc -b && vite build`): succeeded — `dist/` produced (gitignored, not committed).
- `backend/.venv/Scripts/python.exe -m pytest` (full backend suite, run to confirm the CORS-only change didn't regress anything): **74 passed, 1 failed** (`tests/integration/test_inquiry_flow.py::test_run_inquiry_degrades_to_escalate_on_timeout`, error `RuntimeError: cannot schedule new futures after shutdown` inside `crewai`'s flow runtime). This failure is a real-Anthropic-API-call integration test hitting a timing/thread-pool-shutdown race under real API latency — the exact same class of issue documented in `backend.md` §11 ("`run_inquiry()` double-log fix... blocking `shutdown(wait=True)`") and consistent with §15's latency findings, not something this run's CORS-only `main.py` change could cause (the diff adds only an import and one `app.add_middleware(...)` call before any route/flow code; no flow, executor, or timeout logic was touched). Reported here rather than silently ignored; not investigated further as it is pre-existing `@backend.eng`-scope flakiness, out of this run's stated scope.

## Action Log (`*log-integration`)

This document. Follows `backend.md`/`frontend.md`'s structure (Input Requirements, Action Log, Sources, Assumptions, Open Questions, Audit) per `aamad-core.md`'s artifact contract, with the two shape-mismatch judgment calls (§7, §8) written up in the same style as frontend.md's §9.5/§10.5.

## Sources

- `project-context/1.define/prd.md` FR-007, FR-008, FR-009, FR-010, FR-014, NFR-003, NFR-008, §4, §6
- `project-context/1.define/sad.md` §3 (Frontend Architecture Specification), §4 (API Architecture, all seven route contracts), §7 (Performance & Scalability — 5s target / 10s ceiling, directly relevant to §11's finding)
- `project-context/2.build/backend.md` (all sections; §15 in particular — the SAD §7 latency spike this run's own live testing reproduces)
- `project-context/2.build/frontend.md` §1–§10 (mock client modules as swap points, §9.5/§10.5 ambiguity-resolution convention followed here, §10.7's advance flag of `/ops` mapping work)
- `backend/src/app/main.py` (read in full before and after editing — all route/error-envelope definitions)
- `backend/src/app/domain/loader.py` (`kb_search`/ADR-005 — informed the `intent` vs. `section` write-direction judgment call, §8)
- `backend/domain_config.json` (`kb-res-001`, confirming the real, correctly-configured cancellation-policy KB entry the task brief referenced)
- `.claude/rules/aamad-core.md`, `.claude/rules/adapter-crewai.md`, `.claude/rules/epics-index.md`, `.claude/rules/delivery-workflow.md` (not directly applicable — Deliver phase gate — but read for context)
- Live verification performed this run: real HTTP calls (`curl`) against `backend/.venv`'s running `uvicorn app.main:app` process with a real `ANTHROPIC_API_KEY` (`backend/.env`), and the real `frontend/` Vite dev server, both on this machine, as detailed in §10–§14 above

## Assumptions

- `CORS_ALLOWED_ORIGINS` defaults to the two Vite dev ports (`5173`/`5174`) rather than a wildcard — sad.md doesn't pin an allowed-origins policy; this default is scoped to local dev and documented in `backend/.env.example` for override in any other deployment target (Deliver-phase concern, not resolved here).
- Session id generation (crypto.randomUUID() in sessionStorage, inside `mockInquiryClient.ts`) falls back to a fresh per-call id if `sessionStorage` throws — an accepted MVP degradation (each call reads as a new backend session), not expected to occur in normal browser use.
- Error-shaped fallback replies for `/chat`/`/email` (`escalated: true` + an honest "having trouble reaching support" message) assume the existing `EscalationNotice`/`EmailEscalationNotice` components are an acceptable reuse target for *transport* failures, not just *content*-driven escalations — the task brief explicitly endorsed reusing existing escalation/error UI rather than building new UI, and this is the closest existing state to "a human needs to pick this up."
- Test data written to the live `backend/data/app.db` during `*verify-messageflow` (§12) was left in place, not reset — this is live dev-environment verification, not an isolated/ephemeral test run (unlike `@backend.eng`'s own scratch-DB-isolated latency spike, backend.md §15).
- The pre-existing `pytest` failure (§14) is assumed to be a live-API timing/race issue unrelated to this run's CORS-only `main.py` change, based on the diff being additive-only (one import, one middleware registration) with no flow/executor/timeout code touched — not independently re-verified by, e.g., re-running the suite against a pre-CORS commit, since that would mean re-running the full real-API suite a second time (~90s + API cost) for a change this narrow; flagged rather than silently asserted.

## Open Questions

- **`POST /escalations/{id}/resolve` has no frontend caller.** Confirmed out of scope for `*integrate-api` per the task brief ("no frontend UI currently calls this... don't build new UI for it") — used only as a test harness in `*verify-messageflow` (§12) to populate the review queue for testing, not wired to any component. Not silently dropped: this remains a real gap between backend capability and frontend surface, for a future `@frontend.eng`/`@integration.eng` action if an "Escalation Resolution" UI is ever scoped.
- **The `/chat`/`/email` 10-second-ceiling-vs-11–19-second-real-latency gap (§11) blocks the demo scenario the task brief specifically asked this run to confirm** ("what is the cancellation policy?" returning the real grounded answer). This run confirms the wiring is correct and the KB entry (`kb-res-001`) is correctly configured, but cannot confirm the user-facing outcome the task brief expected, because the backend's own documented latency (backend.md §15) exceeds its own timeout ceiling essentially every time. This is squarely `@backend.eng`'s/the operator's fallback-ladder decision (backend.md §15's three documented, not-yet-applied steps), not something `*integrate-api`/`*verify-messageflow` can or should fix — flagged here as a blocking finding for the operator, not silently worked around (e.g., by raising the client-side `curl -m` timeout, which would not help — the ceiling is server-side).
- **`candidate_keywords` is always `[]` on approval unless a Reviewer supplies keywords** (§8) — the current Edit UI (`ReviewQueueItem.tsx`) has no keywords field, so a Reviewer using Edit today still cannot make an approved entry retrievable via `kb_search`'s keyword-overlap scoring. A real gap, flagged rather than fixed (would require new UI, out of this run's "no new UI" scope) — candidate follow-up for `@frontend.eng`.
- **Two inconsistent error-envelope shapes exist across the API surface**: the app's own `{error_code, message}` (used by `ChatProcessingError`, `EscalationNotFoundError`, `ReviewQueueNotFoundError`, `ReviewQueueConflictError`, `InvalidApprovalError`) vs. FastAPI's built-in `{detail: [...]}` for Pydantic request-validation failures (e.g. a missing `session_id`). `apiClient.ts` handles both without crashing (falls back to a generic message when `message` is absent), but a Reviewer/guest-facing error message for a validation failure will currently read generically rather than pointing at the specific missing/invalid field. Not fixed here — would require a `main.py` change beyond the CORS addition this run's scope was limited to.
- **No literal browser/Playwright-driven UI test was performed** (§13) — no such tool was available in this execution environment. All three flows were verified via direct HTTP calls that exactly reproduce the client modules' request shapes (including `Origin` headers for CORS), plus `tsc -b`/`vite build` confirming the TypeScript client code type-checks against the real response DTOs. This is a reasonable proxy but not equivalent to an actual click-through; flagged for whoever has browser-automation tooling available (e.g. `@qa.eng`'s `*qa` action) to close.
- **`GET /interactions`/`GET /review-queue` pagination**: same open question `@frontend.eng` already flagged (frontend.md §10, Open Questions) — neither endpoint supports pagination/filtering; not revisited here, no new constraint added by this run.
- The pre-existing `pytest` failure noted in §14 (`test_run_inquiry_degrades_to_escalate_on_timeout`) was not independently root-caused or fixed — flagged for `@backend.eng` as a possibly-flaky live-API test, not confirmed as a regression from this run's CORS change (see Assumptions).

## Audit

- **Timestamp**: 2026-08-24
- **Persona**: `integration-eng`
- **Actions**: `*integrate-api`, `*verify-messageflow`, `*log-integration`
- **Resolved runtime**: `crewai` (`AAMAD_TARGET_RUNTIME=crewai` env var and `aamad.config.yml runtime.target: crewai` agree — no conflict, no adapter-registry default/warning needed)
- **Inputs used**: `.claude/rules/aamad-core.md`, `.claude/rules/adapter-crewai.md`, `.claude/rules/epics-index.md`, `project-context/1.define/prd.md`, `project-context/1.define/sad.md`, `project-context/2.build/backend.md`, `project-context/2.build/frontend.md`, `project-context/2.build/setup.md`, `aamad.config.yml`, live repo state of `backend/src/app/main.py` and all `frontend/src/lib`/`frontend/src/components`/`frontend/src/types` files touched or read
- **Tools/versions used**: `backend/.venv` (Python 3.11.16, `fastapi>=0.115`, `uvicorn`, existing `crewai==1.15.17` env — no new backend dependencies added, `fastapi.middleware.cors.CORSMiddleware` is part of the already-installed `fastapi` package). Frontend: existing scaffold (Vite v8.2.1, React 19.2.8, TypeScript ~6.0.2) — no new npm dependencies added. `npx tsc -b`, `npm run lint` (`oxlint`), `npm run build` for static verification; `curl` for all live HTTP/CORS verification (no browser-automation tool available this run — see Open Questions); `backend/.venv/Scripts/python.exe -m pytest` for backend regression check.
- **Prohibited actions confirmed avoided**: no new UI components/routes added; no new backend endpoints added; no authentication added; no streaming added; no external APIs beyond the already-configured Anthropic key; no component touched beyond the two additive, non-signature-changing error-handling edits in §9 (judged necessary and documented, not silent scope creep); no destructive `backend/data/app.db` reset.
- **Model/temperature/token controls**: not applicable to this run directly — this run made no LLM calls itself; live verification (§11, §12) exercised the backend's existing `InquiryFlow`/`EscalationResolutionFlow`, whose own model/temperature/token controls are documented in `backend.md` §7 and unchanged by this run.
