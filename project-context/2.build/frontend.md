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

### 8. Accessibility remediation pass (WCAG 2.2 AA, ADA Title III target)

Follow-up action, same scope (`/chat` plus the shared app shell it depends on: `App.tsx`, `index.css`, `index.html`). Operator directive: treat WCAG 2.2 Level AA as the target conformance level (ADA Title III doesn't mandate a specific technical standard for private businesses, so AA was adopted as the working bar). This supersedes the informal "basic usability... formal WCAG certification is not an MVP requirement" framing in PRD §6/NFR-001 as the *implementation* target — no formal third-party certification was performed or claimed, only conformant implementation.

**Violations found and fixed** (contrast ratios computed via the WCAG relative-luminance formula, not estimated):

| Issue | SC | Before | After |
|---|---|---|---|
| `.chat-bubble__meta` timestamp used `opacity: 0.7`, dropping white-on-`#2563eb` text to ~3.34:1 | 1.4.3 Contrast (Minimum) | ~3.34:1 (fail) | Solid color, same as message text: ~5.16:1 (guest), ~15.6:1 (assistant) |
| `.chat-input input` border `#ccc` on `#fafafa` | 1.4.11 Non-text Contrast | ~1.54:1 (fail) | `#6b7280`: ~4.6:1 |
| `.escalation-notice` border `#f0a94f`/`#d9822b` on `#fff4e5` | 1.4.11 Non-text Contrast | ~1.84:1 / ~2.69:1 (fail) | Unified `#b45f18`: ~4.2:1 |
| No skip-navigation link | 2.4.1 Bypass Blocks | missing | `<a href="#main-content" class="skip-link">` in `App.tsx`, visually hidden until focused |
| No reliable focus indicator across all backgrounds (default UA ring risks blue-on-blue on `#2563eb` buttons) | 2.4.7 Focus Visible, 2.4.11 Focus Not Obscured | browser default (untested against blue bg) | Global `:focus-visible { outline: 3px solid #1a1a1a; outline-offset: 2px; }` — verified ≥3:1 against every background in the app (white, `#2563eb`, `#f1f3f5`, `#fff4e5`) |
| Auto-scroll (`scrollIntoView({behavior:"smooth"})`) and `.typing-dot` animation ignored motion preference | 2.3.3 / general Operable motion requirement | always animated | `ChatWindow` checks `matchMedia("(prefers-reduced-motion: reduce)")` before choosing `smooth`/`auto`; global CSS reset neutralizes animation/transition duration under the same media query |
| Normal assistant replies had no live-region announcement (only the loading bubble and escalation notice did) | 4.1.3 Status Messages | partial | `.chat-messages` now `role="log" aria-live="polite" aria-relevant="additions" aria-label="Chat conversation"` — covers all appended messages |
| Escalation notice used `role="status"` (polite) despite the requirement that urgent/escalation content be assertive | 4.1.3 Status Messages | polite | `role="alert"` (implicit assertive + atomic) — see Open Questions re: nested-live-region interop |
| SPA route never updated `document.title` | 2.4.2 Page Titled | static title for all routes | `Chat.tsx` sets `document.title` on mount |
| `color-scheme: light dark` combined with hardcoded light-mode-only text colors (e.g. `.chat-page__subtitle { color: #555 }`), risking contrast failure under OS dark mode | 1.4.3 Contrast (Minimum) | latent conflict, not yet triggered by any real dark palette | Flagged conflict (see below); `color-scheme` constrained to `light` only pending a real dark palette |

**Already compliant, no change needed** (noted so this isn't re-litigated later): `ChatInput`'s message field already used a real associated `<label>` (visually hidden, not placeholder-only) — SC 1.3.1/3.3.2, 4.1.2; Send is a real `<button type="submit">`, not a clickable div — SC 4.1.2, 2.1.1; the escalation notice already paired its icon (`aria-hidden="true"`) with a bold text label rather than relying on color alone — SC 1.4.1; `<html lang="en">` already present in `index.html` — SC 3.1.1; body text uses `rem` units throughout, no fixed-px sizes blocking zoom/OS text-size — SC 1.4.4/1.4.12.

**Conflict flagged rather than silently resolved**: `aamad.config.yml` declares `ui.theme: system` (implying light+dark support), but no dark palette has ever been designed for this project — several colors (`.chat-page__subtitle`, escalation text/background) are hardcoded light-mode values with no `prefers-color-scheme: dark` counterparts. Shipping `color-scheme: light dark` as-is would let the browser auto-flip UA backgrounds to dark while this text stayed light-mode-colored, risking real 1.4.3 failures for any guest using OS dark mode. **Recommendation applied**: constrained `color-scheme` to `light` only (removes the mismatch entirely) rather than attempting a partial/untested dark theme. Building a real dark palette is deferred — see Open Questions.

**Verification**:
- **Automated**: `npx @axe-core/cli http://localhost:5173/chat` (axe-core 4.13.0, chrome-headless) — **0 violations** after the fixes above. Per axe's own disclaimer, automated tools catch only ~20–50% of issues; the items below still need manual AT verification.
- **Keyboard-only Tab path**: skip link → "Chat"/"Inbox"/"Ops" nav links → chat message input → Send button. No modals/dropdowns exist in this component, so there is no keyboard trap to test. All five stops show the new `:focus-visible` ring.
- **Accessible names** (what a screen reader announces): skip link — "Skip to main content"; nav links — "Chat" / "Inbox" / "Ops" (current route additionally announced via `NavLink`'s automatic `aria-current="page"`); message input — "Type your message, edit text"; Send — "Send button"; chat transcript region — "Chat conversation" (log region, polite); escalation notice — announced immediately/assertively via `role="alert"`, content is its full text (header + body).

Not yet run: NVDA/JAWS/VoiceOver manual pass (no Windows/macOS AT available in this execution environment) — see Open Questions.

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
- **Superseded by §8 below**: this bullet originally read "No accessibility audit tooling was run... per PRD §6 'basic usability... formal WCAG certification is not an MVP requirement.'" A follow-up operator directive raised the working target to WCAG 2.2 AA implementation (not formal certification) and a remediation pass was performed — see §8.
- `color-scheme` was constrained to `light` only (removed `dark` from `index.css`'s `:root`) rather than building a dark palette — `aamad.config.yml`'s `ui.theme: system` is not yet fully honored for this reason; flagged as an Open Question, not silently decided as final.
- Styling stayed within plain CSS (`frontend/src/styles/chat.css`, scoped to `/chat` only) — no CSS modules, no Tailwind, consistent with the existing `index.css` global-reset convention and `aamad.config.yml ui.visual_style: minimal` / SAD §3 "no heavy component library."

## Open Questions

- No frontend test runner (e.g. Vitest/React Testing Library) is currently configured in `package.json` — `aamad.config.yml`'s `testing.require_unit_tests` requirement (confirmed already satisfied on the backend per `setup.md`) doesn't yet have a frontend equivalent. Flagged for `@project.mgr`/`@qa.eng` to decide whether/when frontend component tests are required before Deliver.
- `session_id` handling (present in the real `POST /chat` contract per SAD §4) has no home yet in the frontend — `@integration.eng` will need to decide where it's generated/stored (e.g. `crypto.randomUUID()` in `sessionStorage`) when wiring the real API client; no UI change should be needed since `sendInquiry`'s current single-argument signature can be extended additively.
- Whether the escalation notice should eventually expose any operator-facing detail (e.g. an escalation/ticket ID) once a real backend exists is undecided — PRD/SAD only require the guest-facing notice to state a human is being looped in; no ID surfacing was built here, and none was implied by SAD §3 for the guest widget specifically (ops-facing detail lives in `/ops`, out of scope this run).
- **Dark mode**: `aamad.config.yml ui.theme: system` implies dark-mode support, but no dark palette exists. `color-scheme` was constrained to `light` only as a stopgap (see §8) — needs a stakeholder/`@frontend.eng` decision on whether dark mode is truly required for MVP, and if so, a real dark token set for `chat.css`/`index.css`.
- **Nested live-region interop** (`role="log" aria-live="polite"` on `.chat-messages` containing a `role="alert"` `EscalationNotice`): this is a documented tricky area in ARIA/AT interop — some screen readers may announce an escalation twice (once as a log addition, once as an alert) or the reverse (alert suppressed by the ancestor's polite queue). `axe-core` cannot detect this; it requires manual NVDA/JAWS/VoiceOver verification, which was not available in this execution environment. Flagged rather than silently assumed correct.
- No frontend accessibility regression test (e.g. `axe-core`/`jest-axe` wired into a test runner) exists yet — ties into the pre-existing "no frontend test runner configured" open question above; recommend adding an automated a11y check once a runner exists so this doesn't silently regress.
- `/inbox` and `/ops` are still literal "Coming soon" placeholders and were not audited — they'll need the same WCAG 2.2 AA pass (skip link/landmarks already covered by the shared `App.tsx` shell, but their own content will not be) once built.

## Audit

- **Timestamp**: 2026-08-13
- **Persona**: `frontend-eng`
- **Action**: `develop-fe /chat`
- **Resolved runtime**: `crewai` (`aamad.config.yml runtime.target`, no `AAMAD_TARGET_RUNTIME` override observed) — recorded per `aamad-core.md`; not directly load-bearing for this frontend-only, backend-agnostic UI action beyond the non-streaming traceability note in §6 above.
- **Inputs used**: `project-context/1.define/prd.md`, `project-context/1.define/sad.md`, `project-context/2.build/setup.md`, `.claude/agents/frontend-eng.md`, `.claude/rules/aamad-core.md`, `aamad.config.yml`
- **Tools/versions used**: existing scaffold (Vite v8.2.1, React 19.2.8, TypeScript ~6.0.2, react-router-dom ^7.18.2) — no new dependencies added. `npm run build` and `npm run dev` executed for validation (see §7).
- **Prohibited actions confirmed avoided**: no `fetch`/`axios` call to a real backend endpoint; no changes to `/inbox` or `/ops` routes; no new UI component library or Tailwind introduced; no changes under `backend/`.

---

- **Timestamp**: 2026-08-14
- **Persona**: `frontend-eng`
- **Action**: accessibility remediation pass (WCAG 2.2 AA target, operator-directed) — see §8
- **Resolved runtime**: `crewai` (unchanged, not load-bearing for this action)
- **Inputs used**: operator-supplied WCAG 2.2 AA / ADA Title III POUR checklist; `project-context/1.define/prd.md` §5/§6 (NFR-001); `aamad.config.yml` (`ui.theme: system`, `ui.visual_style: minimal`); the `/chat` component tree built in the prior action (§1–§7 above)
- **Tools/versions used**: `@axe-core/cli` 4.13.0 via `npx` (chrome-headless), `npm run build` (Vite v8.2.1, TypeScript ~6.0.2) for regression check. No new runtime dependencies added to `package.json` — axe-core was invoked ad hoc via `npx`, not installed.
- **Prohibited actions confirmed avoided**: no changes to `/inbox`, `/ops`, or `backend/`; no new UI component library introduced; no real backend wiring added.
- **Conflict recorded, not silently resolved**: `aamad.config.yml ui.theme: system` vs. no existing dark palette — see §8 and Open Questions.

---

## 9. `/inbox` build (`*develop-fe /inbox`)

Follow-up action, scoped to `/inbox` only per operator instruction. Mirrors the `/chat` build (§1–§8 above) rather than redoing accessibility work from scratch — the WCAG 2.2 AA bar established in §8 (real labels, live regions, verified-safe color tokens, reduced-motion handling, `document.title` per route, the global `:focus-visible`/skip-link/`prefers-reduced-motion` shell already in `App.tsx`/`index.css`) was applied from the start of this action, not retrofitted.

### 9.1 What was already in place (not redone)

Verified via a direct read of the repo before making changes: `frontend/src/routes/Inbox.tsx` was a literal "Coming soon" placeholder — this is the only route file replaced. `App.tsx`, `main.tsx`, `index.css`, `Chat.tsx`, `Ops.tsx`, and everything under `/chat`'s component tree were read for pattern-matching only and left untouched. No backend file was touched.

### 9.2 Component structure

```
frontend/src/
├── types/email.ts                   # EmailThreadEntry, EmailComposeInput, EmailResult
├── lib/mockEmailClient.ts           # MOCK ONLY — sendEmail(input) -> Promise<EmailResult>
├── components/
│   ├── EmailInbox.tsx                # Owns thread state + loading state; the inbox "container"
│   ├── EmailComposeForm.tsx          # Labeled from/subject/body fields + Send Email button
│   ├── EmailSentItem.tsx             # Renders a guest's outbound "sent" email
│   ├── EmailReplyItem.tsx            # Renders a normal (non-escalation) reply
│   ├── EmailEscalationNotice.tsx     # Visually distinct escalation reply (role="alert")
│   └── EmailLoadingIndicator.tsx     # Typing-dot loading row shown while awaiting a reply
├── styles/inbox.css                  # Plain CSS, scoped to the inbox surface, imported by Inbox.tsx
└── routes/Inbox.tsx                  # Route entry — renders <EmailInbox /> (REPLACED, was placeholder)
```

No new files were added under `types/chat.ts`, `lib/mockInquiryClient.ts`, or any `/chat` component — `/inbox` has its own fully independent type/mock/component set, deliberately not sharing imports with `/chat` (see §9.4). `index.css`'s `.sr-only` utility (already added in the `/chat` build) is reused as-is by `EmailLoadingIndicator`'s hidden live-region text; nothing else in the shared shell was touched.

### 9.3 The four required states, and how each is triggered/demoed

1. **Compose form state** — `EmailComposeForm.tsx` renders three real labeled fields (`from` — `type="email"`, `subject`, `body` — `<textarea>`), each with a visible `<label for>` (not sr-only, unlike `/chat`'s single-field input — see §9.5 for why) plus a `Send Email` submit button, disabled until all three fields are non-empty. This is the default/idle state, present from first load; the thread panel shows an italic empty-state message ("No messages yet…") rather than a blank box, so a non-technical demo audience (NFR-001) has a cue of what to do.
2. **Loading state** — on submit, `EmailInbox.handleSend` appends a "sent" entry to the thread, sets `isLoading = true`, and renders `EmailLoadingIndicator.tsx` (the same typing-dot visual language as `/chat`'s `LoadingIndicator`, re-implemented locally in `inbox.css` rather than imported, to keep `/inbox` self-contained) while `sendEmail(...)` (the mock, §9.4) is in flight. The compose form is disabled during this window. Demo: fill in all three fields and click Send Email — the loading row appears for ~1.3s before the reply lands.
3. **Normal reply state** — `EmailReplyItem.tsx` renders a left-aligned thread card once `sendEmail` resolves with `escalated: false`. Demo: use a subject/body containing a recognized keyword group (e.g. subject "Question about my **reservation**", body mentioning **billing**/**spa**/etc.) for a topic-matched canned reply, or any other content for the generic non-fabrication fallback reply.
4. **Escalation state** — `EmailEscalationNotice.tsx` (`role="alert"`) renders instead of `EmailReplyItem` whenever `sendEmail` resolves with `escalated: true`. Demo: include an escalation-trigger word/phrase in the subject or body — easiest is literally "escalate", or a frustration word like "furious"/"unacceptable"/"speak to a manager" (independent keyword list from `/chat`'s, see §9.4, but intentionally overlapping for consistent demo behavior across channels).

Sent items are right-aligned and labeled "Sent"; replies/escalations are left-aligned and labeled "Reply" or the escalation header — the sent-vs-reply distinction is conveyed by alignment + text label, not by color alone (avoids a "use of color" issue in addition to the ones already tracked in §8's table).

### 9.4 The mock boundary left for `@integration.eng`

All mock logic lives in **`frontend/src/lib/mockEmailClient.ts`**, exporting one function:

```ts
export function sendEmail(input: EmailComposeInput): Promise<EmailResult>
// EmailComposeInput = { from: string; subject: string; body: string }
// EmailResult = { reply_body: string; escalated: boolean }
```

This shape was deliberately chosen to mirror the real `POST /email` contract already defined in `sad.md` §4 (`{from, subject, body} -> {reply_body, escalated: bool}`) — note the field is `reply_body`, not `reply` (that's `/chat`'s field name); the two mock clients are independent modules with independent (if overlapping) escalation-keyword lists and canned-reply content, so `@integration.eng`'s `*integrate-api` can replace the body of `sendEmail` with a real `fetch(`${VITE_API_BASE_URL}/email`, ...)` call **without changing the function's name, signature, or return type**, and therefore without touching `EmailInbox.tsx` or any other component. No component imports fetch/axios or references a URL/env var directly — `EmailInbox` is the only caller of `sendEmail`.

The mock resolves after a fixed `setTimeout` (1300ms, tunable via `MOCK_LATENCY_MS` in `mockEmailClient.ts`), then applies the same style of simple keyword heuristic as `/chat`'s mock (documented in-file as "demo-only, not a stand-in for the real `sentiment_analyzer`/escalation gate") to decide between a topic-matched canned reply, a generic non-fabrication fallback reply, or the escalation notice text — honoring AC-003's "never silently drop or fabricate" intent even in mock form.

### 9.5 PRD/SAD ambiguities resolved (this persona's own judgment, recorded per Workflow Notes)

- **SAD §4's `POST /email` contract doesn't specify how a reply is threaded back to its originating message.** Resolved by giving each thread entry (`EmailThreadEntry`) a `kind` (`sent` | `reply` | `escalation`) and rendering the whole thread as one ordered, append-only list — a reply's `subject` is prefixed `Re: ` client-side for readability. No thread/message ID linking was built since neither PRD nor SAD requires it for the guest-facing MVP surface (ops-facing traceability lives in `/ops`, out of scope here).
- **Whether compose-form labels should be visible or visually hidden (sr-only), unlike `/chat`'s single sr-only-labeled input.** Resolved in favor of visible labels: `/chat` has one obvious text field where a placeholder alone reads clearly, but a 3-field email form (from/subject/body) benefits from visible field labels for a non-technical demo audience (NFR-001) — this is an enhancement over the `/chat` pattern, not a regression, and both approaches satisfy SC 1.3.1/3.3.2/4.1.2 (a real associated `<label for>` either way).
- **PRD AC-003/SAD §3 "clearly distinct" escalation treatment, applied to an email-shaped reply rather than a chat bubble.** Resolved by reusing `/chat`'s exact escalation color tokens/role="alert" pattern rather than inventing a new treatment, per the operator's explicit instruction not to regress the contrast/role work already done — the only change from `/chat`'s `EscalationNotice` is the surrounding markup (email subject/body fields instead of a single bubble `<p>`), not the visual/ARIA treatment.
- **No specific empty-inbox-state guidance in PRD/SAD.** Resolved the same way as `/chat`'s empty state — an inline message rather than a blank panel — but text-only (no canned "welcome" thread entry was seeded, since an unprompted fake "sent"/"reply" pair in an inbox context would read as a fabricated interaction in a way a client-side assistant greeting in chat does not).

### 9.6 Accessibility approach — tokens/patterns reused vs. newly introduced

**Reused, no new computation needed** (see inline comments at the top of `inbox.css` for the full rationale):
- `#b45f18` border / `#fff4e5` background / `#6b3d00` text for `.email-escalation` — identical to `/chat`'s `.escalation-notice`, verified ~4.2:1 border-vs-background in the §8 remediation pass.
- `#6b7280` form-field borders for the compose form's `input`/`textarea` — identical to `/chat`'s `.chat-input input`, verified ~4.6:1 against `#fafafa`; this form sits on the same `#fafafa` background, so the ratio carries over unchanged.
- `#2563eb` background / `#ffffff` text for the `Send Email` button — same pairing as `/chat`'s Send button (established via the §8 table's white-on-`#2563eb` computation, ~5.16:1 for comparable text).
- Global `:focus-visible` ring, `prefers-reduced-motion` CSS reset, skip-link, `<main id="main-content">` — all inherited from `App.tsx`/`index.css`, nothing route-specific needed.
- `role="log" aria-live="polite" aria-relevant="additions"` on the thread container and `role="alert"` on the escalation card — directly mirrors `/chat`'s `ChatWindow`/`EscalationNotice` pattern (same nested-live-region caveat applies here too — see Open Questions).

**Newly introduced, not previously computed — ratio stated here rather than guessed:**
- `#d0d0d0` used for `.email-item`/`.inbox-window`/`.email-compose-form` container borders. This exact color was already present in `/chat`'s `.chat-window` and `.chat-input` top border and was *not* flagged in the §8 remediation table. Treated here the same way: these are decorative panel/card boundaries (thread item outlines, form section divider), not form controls, buttons, or other elements the WCAG 1.4.11 "Non-text Contrast" success criterion classifies as a required "UI component" — so no 3:1 computation was performed, consistent with how this token was already (silently) treated for the equivalent `/chat` elements. Flagged explicitly here in case that reading is revisited.
- `#f1f3f5` background for `.email-item--sent` — identical value to `/chat`'s `.chat-bubble--assistant` background; reused, not new, and paired only with `#1a1a1a` text (the app's default body-text color, already implicitly high-contrast against every light background in use).
- Sent-vs-reply distinction was deliberately built as alignment + text label rather than a color-coded left accent bar, specifically to avoid needing to introduce and justify a new "meaningful" border/accent color (see §9.3) — a scope-reduction decision, not an oversight.

**Verification**:
- **Automated**: `npx @axe-core/cli http://localhost:5174/inbox` (axe-core 4.13.0, chrome-headless) — **0 violations**.
- **Keyboard-only Tab path**: skip link → "Chat"/"Inbox"/"Ops" nav links → From field → Subject field → Message field → Send Email button. No modals/dropdowns exist in this component tree, so there is no keyboard trap to test. All stops show the shared `:focus-visible` ring.
- **Accessible names**: skip link — "Skip to main content"; nav links — "Chat" / "Inbox" / "Ops" (current route via `NavLink`'s automatic `aria-current="page"`); From field — "Your email or name, edit text"; Subject field — "Subject, edit text"; Message field — "Message, edit text"; Send Email — "Send Email button"; thread region — "Email thread" (log region, polite); escalation card — announced assertively via `role="alert"`.
- Not yet run (same gap as `/chat`, §8): NVDA/JAWS/VoiceOver manual pass — no Windows/macOS AT available in this execution environment.

### 9.7 Validation performed

- `npm run build` (`tsc -b && vite build`) — succeeded, no TypeScript errors (5.13 kB CSS, 242.34 kB JS for the combined `/chat` + `/inbox` bundle), `dist/` produced then removed (already gitignored).
- `npm run dev` — booted successfully (port 5173 was already in use by another process in this environment, so Vite auto-selected 5174; `ready in 614 ms`), used for the axe-core run below, then stopped afterward (only the process this action started was stopped; the pre-existing process on 5173 was left untouched).
- `npx @axe-core/cli http://localhost:5174/inbox` — 0 violations (§9.6).
- No unit/component tests were added — same pre-existing gap as `/chat` (§7 Open Questions; no frontend test runner configured yet).

## Sources (§9 additions)

- `project-context/1.define/prd.md` FR-009, FR-010, FR-011, §6 (User Experience Design)
- `project-context/1.define/sad.md` §3 (Frontend Architecture Specification, lines ~135–145 Application Structure/Interface Requirements), §4 (`POST /email` contract, line ~152)
- `project-context/2.build/frontend.md` §1–§8 (the `/chat` build and its accessibility remediation pass — pattern source for this action)
- Repo state at time of this action: `frontend/src/routes/Inbox.tsx` existed as a placeholder (read before edit); no `types/email.ts`, `lib/mockEmailClient.ts`, or `Email*` components existed before this action.

## Assumptions (§9 additions)

- No thread/message ID linking a "sent" entry to its reply was built (see §9.5) — PRD/SAD don't require it for the guest-facing `/inbox` surface; ops-facing traceability is `/ops`'s concern (out of scope here).
- The `/inbox` mock's escalation-keyword list intentionally overlaps with `/chat`'s (same trigger words like "escalate", "furious") for a consistent demo experience across channels, but the two lists live in fully independent files (`mockEmailClient.ts` vs. `mockInquiryClient.ts`) with no shared import — this is duplication by design (module independence per the mock-boundary requirement), not an oversight.
- `#d0d0d0` card/container borders were treated as decorative (not subject to SC 1.4.11) consistent with how this same color was already (silently) treated for `/chat`'s `.chat-window`/`.chat-input` borders in the §8 remediation pass — see §9.6 for the explicit reasoning, since that reading was implicit rather than stated outright in §8.
- No thread persistence — inbox state lives only in `EmailInbox`'s React state and resets on page reload, same posture as `/chat`'s `ChatWindow` (§ Assumptions above).

## Open Questions (§9 additions)

- Same nested-live-region caveat as `/chat` (§ Open Questions above) applies identically to `.email-thread`'s `role="log"` containing a `role="alert"` `EmailEscalationNotice` — not yet manually verified with a screen reader.
- Whether `#d0d0d0` decorative card/container borders should be formally exempted from SC 1.4.11 or upgraded to a 3:1-verified token is unresolved as a project-wide policy — flagged here and cross-referenced from §9.6; would benefit from a single decision applied consistently across `/chat` and `/inbox` rather than being re-litigated per route.
- `/ops` remains an unbuilt "Coming soon" placeholder and was not touched by this action.
- Same frontend-test-runner gap as `/chat` (no Vitest/RTL configured) — `/inbox`'s components have no unit/component tests, consistent with the existing project-wide gap tracked in §7's Open Questions above.

## Audit (§9 entry)

- **Timestamp**: 2026-08-13
- **Persona**: `frontend-eng`
- **Action**: `develop-fe /inbox`
- **Resolved runtime**: `crewai` (`aamad.config.yml runtime.target`, no `AAMAD_TARGET_RUNTIME` override observed) — recorded per `aamad-core.md`; not directly load-bearing for this frontend-only, backend-agnostic UI action.
- **Inputs used**: `.claude/agents/frontend-eng.md`, `project-context/1.define/prd.md` (FR-009/010/011, §6), `project-context/1.define/sad.md` §3/§4, `project-context/2.build/setup.md`, `project-context/2.build/frontend.md` §1–§8 (pattern source), `aamad.config.yml`
- **Tools/versions used**: existing scaffold (Vite v8.2.1, React 19.2.8, TypeScript ~6.0.2, react-router-dom ^7.18.2) — no new dependencies added. `npm run build` for TypeScript/build validation; `npm run dev` + `npx @axe-core/cli` 4.13.0 (chrome-headless) for the accessibility check (§9.6/§9.7).
- **Prohibited actions confirmed avoided**: no `fetch`/`axios` call to a real backend endpoint; no changes to `/chat`, `/ops`, `App.tsx`, `index.css`, or `backend/`; no new UI component library or Tailwind introduced; no Future-Work placeholder widgets (real-email settings etc.) bundled into this action.

---

## 10. `/ops` build (`*develop-fe /ops`)

Follow-up action, scoped to `/ops` only per operator instruction. Builds the two ops-facing sections named in `sad.md` SS3 (line ~138, line ~144) and PRD FR-007/FR-008/FR-014/NFR-003/NFR-008/SS2/SS6: a read-only **interaction log** and the **KB review queue** (approve/edit/reject) — the sole path that can mutate the live knowledge base (NFR-008). Applies the WCAG 2.2 AA bar established in SS8 and carried into SS9, extended to one new element type not yet used elsewhere in this app: a real data `<table>`.

### 10.1 What was already in place (not redone)

Verified via a direct read of the repo before making changes: `frontend/src/routes/Ops.tsx` was a literal "Coming soon" placeholder — this is the only route file replaced. `App.tsx`, `main.tsx`, `index.css`, and everything under `/chat`'s and `/inbox`'s component trees were read for pattern-matching only and left untouched. No backend file was touched.

### 10.2 Component structure

```
frontend/src/
├── types/ops.ts                      # InteractionLogEntry, ReviewQueueEntry, ReviewQueueDecisionInput
├── lib/mockOpsData.ts                # MOCK ONLY — getInteractions, getReviewQueue,
│                                      #   approveReviewQueueEntry, rejectReviewQueueEntry
├── components/
│   ├── InteractionLog.tsx            # Owns interaction-log fetch/loading state
│   ├── InteractionLogTable.tsx       # Real <table>/<th scope="col"> markup, read-only
│   ├── ReviewQueue.tsx               # Owns review-queue state, approve/reject handlers, status live region
│   └── ReviewQueueItem.tsx           # One candidate entry: original query + proposed KB entry
│                                      #   side by side, Approve/Edit/Reject actions
├── styles/ops.css                    # Plain CSS, scoped to the ops surface, imported by Ops.tsx
└── routes/Ops.tsx                    # Route entry — two <section>s (REPLACED, was placeholder)
```

No new files were added under `/chat`'s or `/inbox`'s type/lib/component trees — `/ops` has its own fully independent type/mock/component set, deliberately not sharing imports (same module-independence convention as `/inbox` SS9.4). `index.css`'s shared shell (skip-link, `<main id="main-content">`, global `:focus-visible`, `prefers-reduced-motion` reset) is reused as-is; nothing route-specific was added there.

### 10.3 How to demo the interaction log

`InteractionLog.tsx` fetches via `getInteractions()` on mount (~500ms mock latency, shows "Loading interaction log…" briefly) and renders `InteractionLogTable.tsx` — a real `<table>` with a `<caption>` naming the table's purpose, `<thead>`/`<tbody>` structure, and `<th scope="col">` column headers (Time, Channel, Query, Classification, Sentiment, PII Redacted, Outcome). Seeded with 6 realistic hotel-domain records (mix of chat/email, escalated/resolved, PII-redacted/not — see `mockOpsData.ts`). Escalated rows show "⚠ Escalated" (icon + text, `#6b3d00` color); resolved rows show "✓ Resolved" (default text color) — outcome is never conveyed by color alone. PII-redaction column likewise pairs an icon with "Redacted"/"None detected" text. Demo: load `/ops` — the table is populated immediately, no interaction required.

### 10.4 How to demo the approve/edit/reject flow

`ReviewQueue.tsx` fetches via `getReviewQueue()` on mount, seeded with 3 pending candidate KB entries (see `mockOpsData.ts`), each generated from an escalation resolution (FR-008) and linked back to its `sourceInteractionId`. Each `ReviewQueueItem` renders the original query and proposed KB entry (title + content) in a two-column `.review-item__columns` layout (single column on narrow viewports), per `sad.md`'s "side by side" requirement.

- **Approve**: click "Approve" on any pending card — calls `approveReviewQueueEntry(id)`, the card moves out of the pending list into "Recently decided" ("✓ Approved: <title>"), and a `role="status" aria-live="polite"` message announces "Approved: "<title>" added to the knowledge base."
- **Edit then Approve**: click "Edit" — the proposed title/content switch to a real labeled `<input>`/`<textarea>` pair (draft state, pre-filled from the stored proposal). Change either field, then click "Approve" — this calls `approveReviewQueueEntry(id, { title, content })`, which overwrites the stored proposal with the edited values as part of the same commit (see SS10.5 below), and the status message notes "...added to the knowledge base with your edits." "Cancel Edit" reverts the draft to the stored values and exits edit mode without submitting anything.
- **Reject**: click "Reject" — calls `rejectReviewQueueEntry(id)`, the card moves to "Recently decided" ("✕ Rejected: <title>"), status message announces "Rejected: "<title>" discarded — knowledge base unchanged." No live KB is mutated on this path (there is no live KB in this mock at all — see SS10.7 Open Question).

Buttons are disabled (`<fieldset disabled>`) while that specific item's request is in flight (`busy` prop keyed by id), so a Reviewer can't double-submit a decision on the same card while its mock network call resolves.

### 10.5 Edit-endpoint ambiguity — resolution recorded

`sad.md` SS4's endpoint list (line ~154) only names `POST /review-queue/{id}/approve` and `.../reject` — no explicit edit endpoint — while PRD FR-014/SS6 requires an edit capability ("approve, edit, or reject"). Per the operator's directive, this is resolved as: **editing is purely client-side state** (`ReviewQueueItem`'s local `draftTitle`/`draftContent`, only committed when the Reviewer clicks Edit); **Approve is what commits it** — "Edit then Approve" calls the same `approveReviewQueueEntry(id, edited)` function as a plain Approve, just with an optional `edited` payload that overwrites the stored proposed entry as part of that single call. No separate edit/PATCH endpoint is modeled anywhere in `mockOpsData.ts` or the component tree. This mirrors the real `POST /review-queue/{id}/approve` contract exactly — `@integration.eng` can implement the real approve call to optionally accept an edited-content body without needing a second endpoint.

### 10.6 Reviewer-role-framing assumption

PRD SS2/FR-014 restricts review-queue actions to "the Reviewer persona," but PRD SS3 confirms **no real authentication exists in MVP** (Out of Scope). Per the operator's explicit instruction, this was **not** built as a login gate or any enforced access control. Instead, `ReviewQueue.tsx` renders a visible note above the queue ("The actions below are restricted to the **Reviewer** role. The MVP has no real authentication...; this is a labeled role framing, not an enforced access gate.") plus a `<fieldset><legend>Reviewer actions</legend>` wrapping each item's three buttons — a semantic/textual framing only. Recorded here as an **Assumption**, not silently built or silently skipped: any real Reviewer-role enforcement (auth, session, permissions) is future work, out of this action's scope and out of MVP scope per the PRD.

### 10.7 The mock boundary left for `@integration.eng`

All mock logic lives in **`frontend/src/lib/mockOpsData.ts`**, exporting four functions that mirror the real contract in `sad.md` SS4:

```ts
export function getInteractions(): Promise<InteractionLogEntry[]>
// mirrors GET /interactions

export function getReviewQueue(): Promise<ReviewQueueEntry[]>
// mirrors GET /review-queue

export function approveReviewQueueEntry(
  id: string,
  edited?: ReviewQueueDecisionInput,   // { title: string; content: string }
): Promise<ReviewQueueEntry>
// mirrors POST /review-queue/{id}/approve

export function rejectReviewQueueEntry(id: string): Promise<ReviewQueueEntry>
// mirrors POST /review-queue/{id}/reject
```

No component imports `fetch`/`axios` or references a URL/env var directly — `InteractionLog.tsx` is the only caller of `getInteractions`; `ReviewQueue.tsx` is the only caller of the three review-queue functions. `@integration.eng`'s `*integrate-api` should be able to replace each function body with a real call against `VITE_API_BASE_URL` (already scaffolded in `frontend/.env.example`) **without changing any function's name, signature, or return type**, and therefore without touching any `/ops` component. The mock maintains an in-module mutable array (`reviewQueue`) to simulate server-side state across approve/reject calls within one page session — this is explicitly a mock-only simulation of persistence, not real storage; state resets on page reload, same posture as `/chat` and `/inbox`.

Seed data: 6 interaction-log records (mix of chat/email, escalated/resolved, PII-redacted/not) and 3 review-queue candidate entries (one of which — `rq-003` — references a `sourceInteractionId` not present in the seeded interaction list, deliberately, to model a review-queue item generated from an escalation that isn't itself shown in the currently-displayed interaction log page/window — a realistic pagination-adjacent scenario, not a bug).

### 10.8 Accessibility approach — tokens/patterns reused vs. newly introduced

**Reused, no new computation needed:**
- `#b45f18` / `#fff4e5` / `#6b3d00` — same escalation/warning tokens as `/chat`'s `EscalationNotice` and `/inbox`'s `EmailEscalationNotice`, applied here to the Reject button border/text and the "Escalated" table indicator.
- `#6b7280` form-field borders — same token as `/chat`'s and `/inbox`'s inputs, reused for the review-item edit fields (`~4.6:1` on light backgrounds, previously verified).
- `#2563eb` / `#ffffff` — same primary-button pairing as `/chat`'s Send and `/inbox`'s Send Email, reused for the Approve button (`~5.16:1` white-on-blue, previously verified).
- `#d0d0d0` decorative panel/card borders — same token and same "decorative, not a required-contrast UI component" reading already applied (without new computation) to `/chat`'s `.chat-window`/`.chat-input` and `/inbox`'s `.inbox-window`/`.email-item` borders (see SS9.6's explicit flag on this reading) — applied here to `.ops-table-wrapper`, `.review-item`.
- Global `:focus-visible` ring, `prefers-reduced-motion` reset, skip-link, `<main id="main-content">` — all inherited from `App.tsx`/`index.css`, nothing route-specific needed.
- `role="status" aria-live="polite"` for the approve/reject confirmation message — matches the task's guidance that this isn't urgent/escalation-level (contrast with `/chat`'s/`/inbox`'s `role="alert"` on the escalation notice itself, which *is* urgent).

**Newly computed pairing (reused hue, new background context):**
- `#6b3d00` text on a plain `#ffffff` table-cell background (the "Escalated" status indicator, `.ops-indicator--escalated`) — this exact color was previously only verified as text on `#fff4e5` (an off-white/cream background) in the SS8 remediation table. Computed via the WCAG relative-luminance formula for this new white-background pairing: **~9.16:1**, comfortably passing SC 1.4.3 (>=4.5:1) — expected, since white is a lighter background than `#fff4e5`, which only increases contrast for a dark-brown foreground. No new hue was introduced; only the background context changed, so this is flagged as "newly computed" rather than "newly introduced."

**New element type — semantic-HTML checklist applied:**
- `InteractionLogTable.tsx` is the first real `<table>` in this app (SC 1.3.1 Info and Relationships). Verified: `<caption>` present (not just a visual heading above the table) naming the table's purpose; `<thead>`/`<tbody>` split; every column header is `<th scope="col">`, not a styled `<td>`. No merged/spanning cells, so no `headers`/`id` attribute wiring was needed beyond `scope`.
- `ReviewQueueItem.tsx` action buttons are real `<button type="button">` elements (never clickable `<div>`s), each with a disambiguating `aria-label` (e.g. `"Approve candidate KB entry: Repeated missed housekeeping — resolution steps"`) so a screen-reader user navigating by button list can tell same-labeled buttons on different cards apart (SC 2.4.6/4.1.2) — this was the explicit accessibility risk called out for this route, since "Approve"/"Edit"/"Reject" repeats identically across every pending card.
- Edit-mode fields use real associated `<label htmlFor>` pairs with per-item unique `id`s (`rq-title-${entry.id}`, `rq-content-${entry.id}`) — SC 1.3.1/3.3.2/4.1.2, same pattern as `/inbox`'s compose form.
- The three Reviewer-action buttons per card are grouped in a `<fieldset><legend>Reviewer actions</legend></fieldset>` — the legend is visually hidden (`.review-item__actions legend`, same clip-based sr-only technique as `index.css`'s `.sr-only`) since each button's own `aria-label` already carries the per-item context, but the semantic grouping remains in the accessibility tree (SC 1.3.1). The `<fieldset disabled>` attribute is used (not just individually disabling each button) while a request for that card is in flight, which also correctly removes all three controls from tab order together.

**Verification**:
- **Automated**: `npx @axe-core/cli http://localhost:5173/ops` (axe-core 4.13.0, chrome-headless) — **0 violations**.
- **Keyboard-only Tab path**: skip link → "Chat"/"Inbox"/"Ops" nav links → (interaction log table has no interactive controls, so it's not a Tab stop beyond any native scroll container) → per pending review-queue card: Edit → Approve → Reject (and, if Edit was pressed, the title/content fields interpose before Approve/Reject). No modals/dropdowns exist in this component tree, so there is no keyboard trap to test. All stops show the shared `:focus-visible` ring.
- **Accessible names**: skip link — "Skip to main content"; nav links — "Chat"/"Inbox"/"Ops" (current route via `NavLink`'s automatic `aria-current="page"`); table — announced via its `<caption>` text; per review-queue card — "Edit candidate KB entry: <title>" / "Approve candidate KB entry: <title>" / "Reject candidate KB entry: <title>" (or "Cancel edit of..." / "Approve edited candidate KB entry: <title>" while editing); status confirmation — announced politely via `role="status"` after a decision.
- Not yet run (same gap as `/chat`/`/inbox`): NVDA/JAWS/VoiceOver manual pass — no Windows/macOS AT available in this execution environment. The same nested-live-region-adjacent caveat doesn't directly apply here (no `role="alert"` is nested inside a `role="log"` on this route — the review-queue status uses a single top-level `role="status"`, not nested inside another live region), but this specific pattern (a `role="status"` region physically separate from the list whose items it describes) has not been manually verified either.

### 10.9 Validation performed

- `npm run build` (`tsc -b && vite build`) — succeeded, no TypeScript errors (8.17 kB CSS, 253.54 kB JS for the combined `/chat` + `/inbox` + `/ops` bundle), `dist/` produced then removed (already gitignored).
- Reused the operator's already-running dev server on `http://localhost:5173` (verified via `curl` before doing anything — no new dev server was started, none needed stopping).
- `npx @axe-core/cli http://localhost:5173/ops` — 0 violations (SS10.8).
- No unit/component tests were added — same pre-existing gap as `/chat`/`/inbox` (no frontend test runner configured yet).

## Sources (SS10 additions)

- `project-context/1.define/prd.md` FR-007, FR-008, FR-014, NFR-003, NFR-008, SS2 (Reviewer persona), SS6 ("Ops-facing" paragraph)
- `project-context/1.define/sad.md` SS2 (`interaction_logger`, "KB update approval is intentionally not an agent decision"), SS3 (line ~138 route description, line ~144 interface requirements — "side by side"), SS4 (`GET /interactions`, `GET /review-queue`, `POST /review-queue/{id}/approve`/`.../reject`, line ~154)
- `project-context/2.build/setup.md` (existing scaffold)
- `project-context/2.build/frontend.md` SS1–SS9 (the `/chat` and `/inbox` builds — pattern source for this action, in particular SS8's contrast computations and SS9's mock-boundary/module-independence convention)
- Repo state at time of this action: `frontend/src/routes/Ops.tsx` existed as a placeholder (read before edit); no `types/ops.ts`, `lib/mockOpsData.ts`, or ops-prefixed components existed before this action.

## Assumptions (SS10 additions)

- **Reviewer-role framing is a labeled UI note, not an access gate** — see SS10.6. Any real authentication/authorization for the Reviewer role is out of MVP scope (PRD confirms no auth exists) and out of this action's scope.
- **Edit-endpoint ambiguity resolved as client-side-edit-then-commit-via-approve** — see SS10.5. No new endpoint was invented; `approveReviewQueueEntry`'s optional `edited` parameter is the only mechanism, matching what a real `POST /review-queue/{id}/approve` call could plausibly accept as an optional request-body field.
- No persistence beyond the page session — review-queue and interaction-log state live only in `mockOpsData.ts`'s in-module array and component state; both reset on page reload. Same posture as `/chat`'s and `/inbox`'s Assumptions.
- `rq-003`'s `sourceInteractionId` deliberately doesn't resolve to a currently-seeded interaction-log row (see SS10.7) — modeling a realistic scenario (the log is presumably paginated/time-windowed in a real system) rather than an oversight; no UI currently attempts to cross-link/dereference this field (no click-through from review-queue item to its source interaction row was built — not required by SAD/PRD for MVP).
- "Recently decided" (last 5 approved/rejected items, shown below the pending list) was added as UI polish beyond the PRD/SAD's literal requirement, to make the Approve/Reject outcome visibly persistent on-screen in addition to the transient `role="status"` announcement — judged to support NFR-001's non-technical-audience usability bar without conflicting with anything in scope.

## Open Questions (SS10 additions)

- Same frontend-test-runner gap as `/chat`/`/inbox` (no Vitest/RTL configured) — `/ops`'s components have no unit/component tests, consistent with the existing project-wide gap tracked in SS7's Open Questions.
- Same NVDA/JAWS/VoiceOver manual-pass gap as `/chat`/`/inbox` — not available in this execution environment (SS10.8).
- Whether `#d0d0d0` decorative card/container borders should be formally exempted from SC 1.4.11 or upgraded to a 3:1-verified token remains an unresolved project-wide policy question (first flagged in SS9's Open Questions) — this action extends the same unresolved reading to `.ops-table-wrapper`/`.review-item` rather than re-litigating it per route.
- Whether the interaction log needs pagination/filtering (by channel, outcome, date range) once real data volume exists is undecided — PRD/SAD don't specify this for MVP, and the 6-row mock dataset doesn't surface the need; flagged for `@backend.eng`/`@integration.eng` if `GET /interactions` is expected to return large result sets.
- Whether a rejected/approved review-queue item should ever be reversible (e.g., an "undo" within some window) is undecided — PRD FR-014/AC-011 describe the decision as the KB-write gate, not a specific reversibility requirement; no undo was built.

## Audit (SS10 entry)

- **Timestamp**: 2026-08-13
- **Persona**: `frontend-eng`
- **Action**: `develop-fe /ops`
- **Resolved runtime**: `crewai` (`aamad.config.yml runtime.target`, no `AAMAD_TARGET_RUNTIME` override observed) — recorded per `aamad-core.md`; not directly load-bearing for this frontend-only, backend-agnostic UI action.
- **Inputs used**: `.claude/agents/frontend-eng.md`, `project-context/1.define/prd.md` (FR-007/008/014, NFR-003/008, SS2, SS6), `project-context/1.define/sad.md` SS2/SS3/SS4, `project-context/2.build/setup.md`, `project-context/2.build/frontend.md` SS1–SS9 (pattern source), `aamad.config.yml`
- **Tools/versions used**: existing scaffold (Vite v8.2.1, React 19.2.8, TypeScript ~6.0.2, react-router-dom ^7.18.2) — no new dependencies added. `npm run build` for TypeScript/build validation; the operator's already-running dev server on `http://localhost:5173` (verified via `curl` before use, no new server started) + `npx @axe-core/cli` 4.13.0 (chrome-headless) for the accessibility check (SS10.8/SS10.9).
- **Prohibited actions confirmed avoided**: no `fetch`/`axios` call to a real backend endpoint; no changes to `/chat`, `/inbox`, `App.tsx`, `index.css`, or `backend/`; no new UI component library or Tailwind introduced; no real authentication/login UI built (Reviewer-role framing only, SS10.6).
- **Ambiguity resolved, not silently assumed**: SAD's endpoint list omits a dedicated edit endpoint while PRD requires edit capability — resolved as client-side edit + commit-via-approve (SS10.5), flagged rather than silently built either way.
