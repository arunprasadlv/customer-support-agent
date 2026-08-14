# Frontend Build Log — customer-support-agent

## Input Requirements

**PRD**: `project-context/1.define/prd.md` §4 (Chat inquiry intake & classification, Knowledge-grounded response, Sentiment-aware handling, Simulated escalation), §6 (User Experience Design)
**SAD**: `project-context/1.define/sad.md` §3 (Frontend Architecture Specification)
**Setup scaffold**: `project-context/2.build/setup.md` (Vite + React + TypeScript, routing, minimal CSS reset already in place)
**Selected Runtime**: `crewai` (not directly relevant to this epic — no runtime-specific UI constraint beyond non-streaming; see Traceability Notes below)
**Scope of this action**: `*develop-fe`, scoped to `/chat` only, per operator instruction. `/inbox` and `/ops` remain untouched "Coming soon" placeholders (`@project.mgr` scaffold).

## Action Log (`*develop-fe /chat`)

### 1. What was already in place (not redone)

Verified via `setup.md` and a direct read of the repo before making changes: `frontend/` is a working Vite + React + TS app, `react-router-dom` routing already wired in `main.tsx`/`App.tsx` with `/chat`, `/inbox`, `/ops`, and `/` redirecting to `/chat`. `frontend/src/routes/Chat.tsx` was a literal "Coming soon" placeholder — this is the only route file replaced. No changes were made to `App.tsx`, `main.tsx`, `Inbox.tsx`, `Ops.tsx`, or any backend file.

### 2. Component structure

```
frontend/src/
├── types/chat.ts                  # ChatMessage, ChatRole, ChatMessageKind, InquiryResult
├── lib/mockInquiryClient.ts       # MOCK ONLY — sendInquiry(message) -> Promise<InquiryResult>
├── components/
│   ├── ChatWindow.tsx             # Owns message list + loading state; the chat "container"
│   ├── MessageBubble.tsx          # Normal (non-escalation) message bubble, guest or assistant
│   ├── EscalationNotice.tsx       # Visually distinct escalation notice
│   ├── LoadingIndicator.tsx       # Animated "typing" bubble shown while awaiting a reply
│   └── ChatInput.tsx              # Free-text input + Send button, disabled while loading
├── styles/chat.css                # Plain CSS, scoped to the chat surface, imported by Chat.tsx
└── routes/Chat.tsx                # Route entry — renders <ChatWindow /> (REPLACED, was placeholder)
```

`index.css` (global reset, owned by `@project.mgr`'s scaffold) received one small addition: a `.sr-only` utility class, used by `ChatInput`'s hidden `<label>` and `LoadingIndicator`'s live-region text — generic enough to belong in the global reset rather than the chat-scoped stylesheet.

### 3. The four required UI states, and how each is triggered/demoed

1. **Input state** — `ChatInput.tsx` renders a single-line text input + Send button below a scrollable message history (`ChatWindow.tsx`'s `.chat-messages` list, auto-scrolls to the newest message via a `scrollIntoView` ref effect). This is the default/idle state, present from first load (a canned welcome message from the assistant seeds the conversation so the UI never looks empty — see Assumptions).
2. **Loading state** — the moment a guest submits a message, `ChatWindow`'s `handleSend` appends the guest's message, sets `isLoading = true`, and renders `LoadingIndicator.tsx` (an animated three-dot "typing" bubble, `aria-live="polite"`) at the bottom of the message list while `sendInquiry(...)` (the mock, see §4) is in flight. The input is disabled during this window. Demo: type anything and press Send — the loading bubble appears for ~1.1s before the reply lands.
3. **Normal response state** — `MessageBubble.tsx` renders the assistant's reply as a standard chat bubble (left-aligned, neutral grey) once `sendInquiry` resolves with `escalated: false`. Demo: send a message containing a recognized keyword group (e.g. "What time is check-in for my **reservation**?", "Can I get a breakdown of my **bill**?", "Is the **spa** open today?") to get a topic-matched canned reply, or any other message to get the generic "grounded, not fabricated" fallback reply.
4. **Escalation state** — `EscalationNotice.tsx` renders instead of `MessageBubble` whenever `sendInquiry` resolves with `escalated: true`. Visually distinct by design (PRD AC-003 / SAD §3 requirement): warm amber background, left accent bar, warning icon, and an explicit bold header — "Escalated — a human is being looped in (simulated)" — followed by body text that honestly states a human hand-off is simulated (never a fabricated resolution). Demo: send a message containing an escalation-trigger word/phrase — easiest is literally typing **"escalate"**, or a frustration word like "furious"/"unacceptable"/"speak to a manager". `ChatWindow` picks the bubble vs. notice renderer per-message based on each message's `kind: "text" | "escalation"` field, so a single conversation can show both types cleanly.

### 4. The mock boundary left for `@integration.eng`

All mock logic lives in **`frontend/src/lib/mockInquiryClient.ts`**, exporting one function:

```ts
export function sendInquiry(message: string): Promise<InquiryResult>
// InquiryResult = { reply: string; escalated: boolean }
```

This shape was deliberately chosen to mirror the real `POST /chat` contract already defined in `sad.md` §4 (`{message, session_id} -> {reply, escalated: bool}`) — `@integration.eng`'s `*integrate-api` should be able to replace the body of `sendInquiry` with a real `fetch(`${VITE_API_BASE_URL}/chat`, ...)` call (env var already scaffolded in `frontend/.env.example`) **without changing the function's name, signature, or return type**, and therefore without touching `ChatWindow.tsx` or any other component. No component imports fetch/axios or references a URL/env var directly — `ChatWindow` is the only caller of `sendInquiry`, and it only imports the function, not implementation details.

The mock itself does not call any network endpoint. It resolves after a fixed `setTimeout` (1100ms, tunable via `MOCK_LATENCY_MS`), then applies a simple keyword heuristic (documented in-file as "demo-only, not a stand-in for the real `sentiment_analyzer`/escalation gate") to decide between a topic-matched canned reply, a generic non-fabrication fallback reply, or the escalation notice text.

### 5. PRD/SAD ambiguities resolved (this persona's own judgment, recorded per Workflow Notes)

- **SAD §3 says "loading state while `InquiryFlow` runs" but doesn't specify a visual form.** Resolved as an animated three-dot typing-style bubble (a common, low-effort chat-UI convention) rather than a spinner or skeleton screen, since it reads as "the assistant is composing a reply" and requires no extra dependency — consistent with `ui.visual_style: minimal`.
- **PRD AC-003 / SAD §3 require the escalation notice to be "clear, distinct" but don't mandate a specific treatment.** Resolved with a warning-color-coded card (amber/orange, left accent bar, icon, bold label) rather than merely a different text color inside the same bubble shape — chosen so the distinction is legible even at a glance or in a screenshot, not just on close reading.
- **Neither PRD nor SAD specifies what a first-load empty chat should show.** Resolved by seeding one canned assistant "welcome" message on mount (client-side constant, not a network call) so a non-technical demo audience (NFR-001) isn't presented with a completely blank box and no cue of what to do.
- **No specific escalation-trigger logic exists yet** (real logic is `sentiment_analyzer` + `escalation_gate`, owned by `@backend.eng`/`@system-arch`, per SAD §2 ADR-002). For a demo-only mock, a small keyword list (e.g. "escalate", "furious", "speak to a manager") was chosen so the escalation state is trivially reproducible by a demo presenter without needing to know real sentiment-scoring internals. This is explicitly commented in `mockInquiryClient.ts` as demo-only and not a design surface `@backend.eng`/`@integration.eng` should treat as a spec.

### 6. Traceability notes (runtime-choice UI-visible constraints)

- SAD §1 confirms **non-streaming** request/response for MVP (no token-level streaming). The mock's single `await sendInquiry(...)` → one reply arrives atomically, matches this — no partial/incremental rendering logic was built, and none should be assumed by `@integration.eng` when wiring the real endpoint.
- SAD §4's `POST /chat` contract returns `{reply, escalated: bool}` only (no confidence score, no classification/sentiment detail surfaced to the guest chat UI — those are `/ops`-view concerns per SAD §3, out of scope here). The mock and `InquiryResult` type intentionally expose nothing more than that pair, to avoid the UI assuming fields the real API may not send on `/chat` (as opposed to `/interactions`).

### 7. Validation performed

- `npm run build` (`tsc -b && vite build`) — succeeded, no TypeScript errors, `dist/` produced (2.49 kB CSS, 235.20 kB JS) then removed (already gitignored).
- `npm run dev` — booted successfully (`ready in 292 ms`, `http://localhost:5173/`), then stopped after confirming clean startup (no console errors surfaced in the dev-server log).
- No unit/component tests were added — `aamad.config.yml`/`setup.md` don't currently define a frontend test runner, and none was introduced in this action (out of scope for `*develop-fe`; flagged as an Open Question below for whoever picks up frontend test tooling).

## Sources

- `project-context/1.define/prd.md` §4, §6
- `project-context/1.define/sad.md` §3 (Frontend Architecture Specification), §4 (`POST /chat` contract), §1 (non-streaming decision)
- `project-context/2.build/setup.md` (existing scaffold — routing, styling convention, `.env.example`)
- `.claude/agents/frontend-eng.md` (persona contract, Workflow Notes)
- `.claude/rules/aamad-core.md` (artifact contract: Sources/Assumptions/Open Questions/Audit)
- `aamad.config.yml` (`ui.visual_style: minimal`)
- Repo state at time of this action: files under `frontend/src/{types,lib,components}` did not exist before this action; `frontend/src/routes/Chat.tsx` existed as a placeholder (read before edit)

## Assumptions

- A canned client-side "welcome" assistant message on first load is in-scope UI polish, not a fabricated backend response — it's a static constant, never presented as a real answer to a real question, and doesn't call `sendInquiry`.
- The escalation-trigger keyword list in `mockInquiryClient.ts` is demo convenience only; it is explicitly commented as such and is not intended to influence or be reused by `@backend.eng`'s real `sentiment_analyzer`/escalation-gate implementation (SAD §2 ADR-002).
- Single guest session per browser tab, no persistence — chat history lives only in React state (`ChatWindow`) and resets on page reload. PRD/SAD don't require session persistence for the MVP demo; `session_id` (referenced in the real `POST /chat` contract) is not yet generated/tracked anywhere in this UI — left for `@integration.eng` to introduce when wiring the real client, since it has no UI-visible behavior today.
- No accessibility audit tooling was run; basic practices were followed (labeled input via `.sr-only` label, `aria-live` on the loading indicator, `role="status"` on the escalation notice) per PRD §6 "basic usability... formal WCAG certification is not an MVP requirement."
- Styling stayed within plain CSS (`frontend/src/styles/chat.css`, scoped to `/chat` only) — no CSS modules, no Tailwind, consistent with the existing `index.css` global-reset convention and `aamad.config.yml ui.visual_style: minimal` / SAD §3 "no heavy component library."

## Open Questions

- No frontend test runner (e.g. Vitest/React Testing Library) is currently configured in `package.json` — `aamad.config.yml`'s `testing.require_unit_tests` requirement (confirmed already satisfied on the backend per `setup.md`) doesn't yet have a frontend equivalent. Flagged for `@project.mgr`/`@qa.eng` to decide whether/when frontend component tests are required before Deliver.
- `session_id` handling (present in the real `POST /chat` contract per SAD §4) has no home yet in the frontend — `@integration.eng` will need to decide where it's generated/stored (e.g. `crypto.randomUUID()` in `sessionStorage`) when wiring the real API client; no UI change should be needed since `sendInquiry`'s current single-argument signature can be extended additively.
- Whether the escalation notice should eventually expose any operator-facing detail (e.g. an escalation/ticket ID) once a real backend exists is undecided — PRD/SAD only require the guest-facing notice to state a human is being looped in; no ID surfacing was built here, and none was implied by SAD §3 for the guest widget specifically (ops-facing detail lives in `/ops`, out of scope this run).

## Audit

- **Timestamp**: 2026-08-13
- **Persona**: `frontend-eng`
- **Action**: `develop-fe /chat`
- **Resolved runtime**: `crewai` (`aamad.config.yml runtime.target`, no `AAMAD_TARGET_RUNTIME` override observed) — recorded per `aamad-core.md`; not directly load-bearing for this frontend-only, backend-agnostic UI action beyond the non-streaming traceability note in §6 above.
- **Inputs used**: `project-context/1.define/prd.md`, `project-context/1.define/sad.md`, `project-context/2.build/setup.md`, `.claude/agents/frontend-eng.md`, `.claude/rules/aamad-core.md`, `aamad.config.yml`
- **Tools/versions used**: existing scaffold (Vite v8.2.1, React 19.2.8, TypeScript ~6.0.2, react-router-dom ^7.18.2) — no new dependencies added. `npm run build` and `npm run dev` executed for validation (see §7).
- **Prohibited actions confirmed avoided**: no `fetch`/`axios` call to a real backend endpoint; no changes to `/inbox` or `/ops` routes; no new UI component library or Tailwind introduced; no changes under `backend/`.
