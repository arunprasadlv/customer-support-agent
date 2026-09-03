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

## 11. `/ops` — Escalated — Needs Resolution (`*develop-fe`, live-wired)

Follow-up action, scoped to closing a real end-to-end gap: `@integration.eng`'s `*integrate-api` (SS10's mock boundary → real calls) left `getInteractions`/`getReviewQueue`/`approveReviewQueueEntry`/`rejectReviewQueueEntry` in `lib/mockOpsData.ts` fully wired to the real FastAPI backend, but nothing in the UI ever called `POST /escalations/{id}/resolve` — the only way to populate the KB Review Queue was a manual `curl`. This action adds the missing UI path: a human sees an escalated interaction, writes a resolution, submits it, and it appears in the (already-built, unchanged) KB Review Queue. Built directly against the real backend from the start — no mock-then-swap cycle, matching the pattern the other four `mockOpsData.ts` functions already established.

### 11.1 What was already in place (not redone)

Verified via a direct read of the repo before making changes: `getInteractions`, `getReviewQueue`, `approveReviewQueueEntry`, `rejectReviewQueueEntry` (`lib/mockOpsData.ts`) and `apiClient.ts`'s `apiFetch` helper already existed and already called the real backend (`@integration.eng`'s work, `project-context/2.build/integration.md`) — read, not modified in behavior. `InteractionLogTable.tsx` and `ReviewQueueItem.tsx` were read for pattern-matching only and are untouched. `/chat`, `/inbox`, and all backend files (`backend/`) are untouched.

### 11.2 Component structure

```
frontend/src/
├── lib/mockOpsData.ts                 # + resolveEscalation(interactionId, resolutionText) — new,
│                                       #   calls real POST /escalations/{id}/resolve directly
├── components/
│   ├── EscalationResolutionQueue.tsx  # NEW — owns needs-resolution fetch/compute, resolution
│   │                                  #   drafts, submit-in-flight state, per-item confirmation
│   ├── InteractionLog.tsx             # + optional `refreshToken` prop (refetch trigger)
│   └── ReviewQueue.tsx                # + optional `refreshToken` prop (refetch trigger)
├── styles/ops.css                    # + .escalation-queue*/.escalation-item* rules
└── routes/Ops.tsx                    # + <EscalationResolutionQueue> section, `refreshToken`
                                       #   state lifted here, stale header comment corrected
```

No new type file was needed — `EscalationResolutionQueue.tsx` reuses the existing `InteractionLogEntry` type from `types/ops.ts` (it only ever renders/submits against entries already shaped that way); no new backend query or type was introduced (per the operator's instruction to compute "needs resolution" client-side from data already fetched elsewhere).

### 11.3 The needs-resolution rule — judgment call recorded

Per the operator's explicit specification (not left to independent judgment, but recorded here per this section's `*develop-fe` convention of writing up every non-trivial rule): an interaction is "Escalated — Needs Resolution" iff `outcome === "escalated"` AND no review-queue entry exists with `sourceInteractionId` equal to that interaction's `id`, regardless of that entry's `status` — pending, approved, *and* rejected all count as "already handled." This was deliberately not narrowed to "no *pending* entry," because narrowing it that way would resurrect a rejected item back into the needs-resolution list, silently inviting a second resolution submission for an interaction a Reviewer already made a decision about. Computed entirely client-side in `EscalationResolutionQueue.tsx` by cross-referencing `getInteractions()` and `getReviewQueue()` (a `Set` of `reviewQueue.map(e => e.sourceInteractionId)`, filtered against `outcome === "escalated"` interactions) — no new backend query, matching the task's explicit instruction.

One related judgment call *was* left open by the backend and is called out, not silently worked around: `POST /escalations/{id}/resolve` has no server-side check that `{id}`'s interaction actually has `outcome === "escalated"` (see `main.py`'s `resolve_escalation` docstring/backend.md) — a resolution could technically be submitted against a `"responded"` interaction if called directly. This UI never exposes that path (only escalated-and-unresolved interactions are ever offered a Submit button), so the gap is inert from this component's surface, but it remains a backend-side gap, out of this action's scope to fix (per the operator's instruction).

### 11.4 The refresh problem — resolution recorded

`InteractionLog.tsx` and `ReviewQueue.tsx` each fetch once on mount via `useEffect(() => {...}, [])`, with no built-in way to learn a sibling section changed server state. Resolved with a `refreshToken` counter lifted to `Ops.tsx`: `EscalationResolutionQueue` accepts an `onResolved` callback, called once after a successful `resolveEscalation`, which bumps `refreshToken` in `Ops.tsx`; `refreshToken` is passed as a new **optional** prop to all three sections (`InteractionLog`, `EscalationResolutionQueue`, `ReviewQueue`) and added to each one's existing fetch `useEffect`'s dependency array. This is additive only — `InteractionLog`/`ReviewQueue`'s existing fetch/loading/error logic, JSX, and all other props/behavior are unchanged; the prop is optional specifically so neither component's default (no-prop) behavior changes for any other caller. `EscalationResolutionQueue` also depends on its own `refreshToken` prop (so it, too, refetches if some other future action bumps the counter), even though nothing currently mutates review-queue/interaction state from outside this component besides its own submit action.

One consequence, called out rather than silently accepted: `InteractionLog`/`ReviewQueue`'s `isLoading` state is only ever set back to `true` on the very first mount (existing behavior, unchanged) — a `refreshToken`-triggered refetch updates the underlying data in place without re-showing a "Loading…" message. This was judged acceptable (the refetch is near-instant against a local dev backend, and re-flashing a loading state on every sibling action would be more visually disruptive than a silent data swap) but is flagged here as a deliberate trade-off, not an oversight.

### 11.5 How to demo the flow

1. Trigger an escalation via `/chat` (e.g. "this is unacceptable, I want to speak to a manager") or `/inbox` email compose, or use an already-escalated interaction.
2. Navigate to `/ops` — the interaction appears under **Escalated — Needs Resolution**, showing its original query text.
3. Type resolution text into the labeled textarea and click **Submit Resolution** (`aria-label="Submit resolution for: <query excerpt>"`, disambiguating this button from every other item's identically-worded button). The `<fieldset>` disables during the in-flight request.
4. On success: a `role="status" aria-live="polite"` confirmation appears ("Resolution submitted for "<excerpt>" — now awaiting Reviewer decision in the KB Review Queue."), the item disappears from the needs-resolution list, and — because `onResolved` bumped `refreshToken` — the **KB Review Queue** section below refetches and shows the new candidate as a pending item, with no page reload.
5. Approving that candidate in the (unchanged) KB Review Queue writes it to the live KB, exactly as before.

Verified as a real round trip against the live backend (SS11.7) — not just read through.

### 11.6 Accessibility approach

Same WCAG 2.2 AA bar and same reused tokens as SS10.8 — no new colors introduced:
- `#2563eb`/`#ffffff` primary-button pairing, reused for Submit Resolution.
- `#6b7280` field border, reused for the resolution `<textarea>`.
- `#d0d0d0` decorative card border, reused for `.escalation-item` (same "decorative, not a required-contrast UI component" reading as `.review-item`/`.ops-table-wrapper`, SS10.8/SS9.6).
- `#6b3d00` reused for the per-item submit-error text (`role="alert"`) — same token already verified at ~9.16:1 on white (SS10.8).
- Real `<label htmlFor>` on the resolution textarea (unique per-item id, `escalation-resolution-${entry.id}`), not placeholder-only — same convention as `EmailComposeForm.tsx`/`ReviewQueueItem.tsx`'s edit fields.
- `aria-label` on the Submit button disambiguates repeated "Submit Resolution" text across multiple items — same pattern as `ReviewQueueItem.tsx`'s Approve/Edit/Reject `aria-label`s.
- `<fieldset disabled>` while the submit request is in flight — same pattern as `ReviewQueueItem.tsx`.
- `role="status" aria-live="polite"` for the success confirmation (matches `ReviewQueue.tsx`'s pattern); a separate per-item `role="alert"` for submit failures (matches the urgency framing already used for `loadError` paragraphs in `InteractionLog.tsx`/`ReviewQueue.tsx`).
- Global `:focus-visible` ring, skip-link, `prefers-reduced-motion` reset — inherited from the existing shell, nothing new needed.

**Verification**: `npx @axe-core/cli http://localhost:5173/ops` (axe-core 4.13.0, chrome-headless) — **0 violations**, run against the live page with real escalated/resolved data present (not an empty-state-only check). Manual NVDA/JAWS/VoiceOver pass not performed — same pre-existing gap as SS8/SS9/SS10 (no Windows/macOS AT available in this execution environment).

### 11.7 Verification performed (real round trip, no new mock layer)

Both backend (`:8000`) and frontend (`:5173`) were already running; confirmed via `curl http://localhost:8000/health` (`{"status":"ok"}`) and `curl http://localhost:5173/` (`200`) before starting anything.

1. `POST /chat` with `"this is unacceptable, I want to speak to a manager right now"` → `{"escalated": true}`.
2. `GET /interactions`, sorted by `created_at` → confirmed the new row (`e2c71434-cc2a-4f70-a317-d82c01440451`) has `outcome: "escalated"`.
3. `GET /review-queue` → confirmed no entry with `original_inquiry_id` equal to that id yet (needs-resolution condition holds).
4. `POST /escalations/e2c71434-cc2a-4f70-a317-d82c01440451/resolve` with `{"resolution_text": "..."}` (the exact body shape `resolveEscalation` sends) → `{"status": "queued", "review_queue_id": "f752e5dd-..."}`, matching `resolveEscalation`'s expected response shape exactly.
5. `GET /review-queue` → confirmed the new entry exists with `status: "pending"` and `original_inquiry_id` pointing back at the resolved interaction.
6. `POST /review-queue/f752e5dd-.../approve` → `200`, returned a `kb_entry_id`, confirming the live KB write path (unchanged, `@integration.eng`'s existing work) still fires correctly for an entry that originated through this new path.
7. `GET /review-queue` again → confirmed `status: "approved"` and that the interaction still correctly counts as "already handled" (would not reappear in needs-resolution).
8. `npx @axe-core/cli http://localhost:5173/ops` against the live page (with the above data present) — 0 violations.
9. `npm run build` (`tsc -b && vite build`) — succeeded, no TypeScript errors (10.18 kB CSS, 253.84 kB JS for the combined `/chat` + `/inbox` + `/ops` bundle).

Steps 1–7 exercise the exact HTTP contract `resolveEscalation`/`getInteractions`/`getReviewQueue`/`approveReviewQueueEntry` use (same paths, methods, and body/response shapes read directly from `mockOpsData.ts`), confirming the UI code's real backend calls behave as coded, in addition to the axe-core pass confirming the component tree itself renders and is accessible against the live page.

## Sources (§11 additions)

- `project-context/1.define/prd.md` FR-008 (escalation → KB candidate), FR-014/NFR-008 (Reviewer approve/edit/reject, KB-write gate)
- `project-context/1.define/sad.md` §4 (`POST /escalations/{id}/resolve` contract)
- `backend/src/app/main.py` — read directly for the `POST /escalations/{id}/resolve` request/response schema and the `original_inquiry_not_found`/`chat_processing_failed` error envelope, per this action's explicit instruction not to guess the contract
- `project-context/2.build/frontend.md` §9/§10 (pattern source: mock-boundary write-up style, accessibility token reuse, `<fieldset disabled>`/`role="status"` conventions)
- `project-context/2.build/integration.md` (existing real-backend wiring for `getInteractions`/`getReviewQueue`/`approveReviewQueueEntry`/`rejectReviewQueueEntry`/`apiFetch`, read but not modified)
- Repo state at time of this action: `lib/mockOpsData.ts` already had four real-backend functions and no `resolveEscalation`; no `EscalationResolutionQueue.tsx` existed before this action.

## Assumptions (§11 additions)

- "Needs resolution" is computed client-side per SS11.3's rule, exactly as specified by the operator — not an independently invented heuristic.
- The backend's lack of an `outcome === "escalated"` guard on `POST /escalations/{id}/resolve` (SS11.3) is a known, separately-flagged backend gap; this UI's own design (only ever offering escalated-and-unresolved interactions a Submit control) makes the gap unreachable from this surface, but the gap itself was not fixed here (out of this action's frontend-only scope).
- `refreshToken`-triggered refetches intentionally do not re-show a "Loading…" state in `InteractionLog`/`ReviewQueue` (SS11.4) — judged an acceptable trade-off for a near-instant local-dev refetch, not revisited if the operator wants a visible refresh indicator later.
- No optimistic UI update on submit — `EscalationResolutionQueue` removes an item from its local list only after `resolveEscalation` resolves successfully, consistent with this MVP's "server-truth over client-assumed state" posture already established in `mockOpsData.ts`'s approve/reject functions (SS10.7).

## Open Questions (§11 additions)

- Same frontend-test-runner gap as §7/§9/§10 (no Vitest/RTL configured) — `EscalationResolutionQueue.tsx` has no unit/component tests.
- Same NVDA/JAWS/VoiceOver manual-pass gap as §8/§9/§10 — not available in this execution environment.
- Whether the backend should reject `POST /escalations/{id}/resolve` for a non-escalated interaction (SS11.3) is flagged again here from the frontend side; no frontend workaround was needed, but the gap remains open at the backend layer.
- Whether "Escalated — Needs Resolution" should show any indication of *how long* an interaction has been waiting (e.g. relative timestamp, oldest-first sort) is undecided — PRD/SAD don't specify this, and the current list order simply follows `getInteractions()`'s return order; flagged for future polish if the queue grows large.

## Audit (§11 entry)

- **Timestamp**: 2026-08-24
- **Persona**: `frontend-eng`
- **Action**: `develop-fe` (Escalated — Needs Resolution, `/ops`)
- **Resolved runtime**: `crewai` (`aamad.config.yml runtime.target`, no `AAMAD_TARGET_RUNTIME` override observed) — recorded per `aamad-core.md`; not directly load-bearing for this frontend-only UI action, which calls one already-tested backend REST endpoint.
- **Inputs used**: `project-context/1.define/prd.md` (FR-008, FR-014, NFR-008), `project-context/1.define/sad.md` §4, `backend/src/app/main.py` (`POST /escalations/{id}/resolve` contract, read directly, not guessed), `frontend/src/lib/mockOpsData.ts`/`apiClient.ts` (existing real-backend pattern), `frontend/src/components/InteractionLog.tsx`/`ReviewQueue.tsx`/`ReviewQueueItem.tsx`/`EmailComposeForm.tsx` (pattern source), `project-context/2.build/frontend.md` §8–§10 (accessibility/documentation conventions), `aamad.config.yml`
- **Tools/versions used**: existing scaffold (Vite v8.2.1, React 19.2.8, TypeScript ~6.0.2) — no new dependencies added. `npm run build` for TypeScript/build validation; the operator's already-running backend (`:8000`) and frontend dev server (`:5173`), verified via `curl` before use, no new servers started; `curl` for the real end-to-end backend round trip (SS11.7); `npx @axe-core/cli` 4.13.0 (chrome-headless) for the accessibility check (SS11.6).
- **Prohibited actions confirmed avoided**: no new mock layer built for `resolveEscalation` (calls the real backend directly, per explicit instruction); no changes to `/chat`, `/inbox`, `InteractionLogTable.tsx`, `ReviewQueueItem.tsx`, or any `backend/` file; no new UI component library or Tailwind introduced; `InteractionLog.tsx`/`ReviewQueue.tsx` changes are additive-only (one optional prop + one dependency-array entry each), not a rewrite of their existing fetch/error-handling logic.
- **Ambiguity resolved, not silently assumed**: the needs-resolution rule (SS11.3) and the refresh mechanism (SS11.4) were both explicitly specified by the operator and implemented as specified, not independently reinterpreted; the backend's missing `outcome` guard on resolve (SS11.3) was surfaced as an Open Question rather than fixed (backend changes out of this action's scope).

## 12. `/chat` quick-reply chips — taxonomy -> common questions (`*develop-fe`, live-wired)

Follow-up action closing a real UX gap named directly by the operator: guests previously landed on `/chat` with only the static welcome message and a blank text box, with no hint of what the assistant can help with. `GET /taxonomy` (already built, live, and verified working on the real backend — `backend/src/app/main.py`'s `CommonQuery`/`TaxonomyEntry` models and `get_taxonomy` handler, read directly rather than guessed) already exposes exactly the data needed: 4 domain categories, 3 example questions each. This action wires that endpoint into a two-step quick-reply chip UX inside the existing `ChatWindow`, additive to (never replacing) free-text input.

### 12.1 Component structure

```
frontend/src/
├── types/
│   ├── chat.ts          # + "options" ChatMessageKind, QuickReplyOption (label + baked-in onSelect),
│   │                     #   ChatMessage.options?/optionsGroupLabel? (both optional, only set for "options")
│   └── taxonomy.ts       # NEW — CommonQuery/TaxonomyEntry, mirrors main.py's Pydantic models exactly
├── lib/
│   └── taxonomyClient.ts # NEW — getTaxonomy(): Promise<TaxonomyEntry[]>, calls real GET /taxonomy via
│                          #   apiClient.ts's apiFetch (same helper /chat's sendInquiry and /ops's
│                          #   mockOpsData.ts already use for the real backend)
├── components/
│   ├── QuickReplyOptions.tsx  # NEW — renders one "options" ChatMessage: chat-row/BotAvatar shell +
│   │                          #   intro text + a role="group" pill-button list
│   └── ChatWindow.tsx         # + taxonomy fetch-on-mount effect, handleCategorySelect, render branch
└── styles/chat.css            # + .quick-reply-group/.quick-reply-chip/.chat-bubble--options rules
```

No changes to `MessageBubble.tsx`, `EscalationNotice.tsx`, `ChatInput.tsx`, `mockInquiryClient.ts`, `apiClient.ts`, `/inbox`, `/ops`, or any `backend/` file.

### 12.2 The two-step UX decision

Per the operator's confirmed flow, implemented exactly as specified rather than independently redesigned:

1. **On mount**, `ChatWindow` fetches `GET /taxonomy` once, in a `useEffect` alongside the existing static `WELCOME_MESSAGE`. On success, it appends one new assistant `"options"` message showing the 4 category labels as chips ("Reservations & Booking", "Check-in/Check-out & Billing", "Room Service & Amenities", "General Complaints").
2. **Clicking a category chip** is pure local UI navigation — no backend call, no guest-transcript entry. It appends a second assistant `"options"` message showing that category's 3 `common_queries` as chips (the `query` text as each chip's label).
3. **Clicking a common-question chip** sends it exactly as if the guest had typed and submitted it: it is routed through `ChatWindow`'s existing `handleSend(text)` — same guest-bubble append, same `isLoading`/`LoadingIndicator` state, same `sendInquiry` call, same escalation-vs-normal-reply rendering. No parallel send path was built.
4. **Chip messages are append-only and never removed or collapsed** after use — consistent with the existing `messages` array being append-only everywhere else in this component (welcome message, guest/assistant turns). A guest can scroll back and click category or common-question chips again at any time; no "used" flag or dedup logic was added, per the operator's explicit instruction to keep this simple.
5. **`ChatInput`/free text is untouched** — chips are additive. A guest can ignore every chip and type anything, exactly as before this action.

**Implementation shape**: a single new `ChatMessageKind = "options"` (not two separate kinds for "category" vs. "query") carrying `options: QuickReplyOption[]`, where each `QuickReplyOption` is `{ id, label, onSelect: () => void }`. The `onSelect` closure is baked in by whichever `ChatWindow` function *builds* the message (the taxonomy-fetch effect for category chips, `handleCategorySelect` for common-question chips) — so `QuickReplyOptions.tsx` itself is a pure, semantics-free renderer that never branches on "is this a category chip or a question chip." This was chosen over two distinct `ChatMessageKind`s (e.g. `"category-options"`/`"query-options"`) because the only actual difference between the two steps is *what a click does*, not how the chip set is rendered or grouped — encoding that difference as data (a closure) on the option itself, rather than as a second message-kind branch in the render loop, kept `ChatWindow`'s render loop at three cases (`"escalation"`/`"options"`/default `"text"`) instead of four, and kept `QuickReplyOptions.tsx` fully reusable for both steps with zero conditional logic inside it.

### 12.3 Visual style — pill/chip buttons, contrast computed (not assumed)

Per the operator-supplied reference: rounded-full ("pill"/stadium) shape, white background, thin ~1px border, blue text, `~0.5rem 1rem` padding, chips wrap in a flex row with `~0.6rem` gap, left-aligned, no drop shadow.

```css
.quick-reply-chip {
  background: #ffffff;
  border: 1px solid #6b7280;
  border-radius: 9999px;
  padding: 0.5rem 1rem;
  color: #2563eb;
  font-size: 0.9rem;
  font-weight: 600;
  line-height: 1.2;
  cursor: pointer;
}
.quick-reply-chip:hover {
  background: #eff6ff;
}
```

**Colors reused, not invented** (per instruction): `#2563eb` (this app's established primary blue — Send button, guest bubble background) for chip text; `#6b7280` (the existing form-field-border token, `.chat-input input`'s border, already verified at ~4.6:1 against `#fafafa` in §8) for the chip border.

**Contrast computed via the WCAG relative-luminance formula (§8's method), not assumed**:

| Pairing | Ratio | Requirement | Result |
|---|---|---|---|
| `#2563eb` text on `#ffffff` chip background | 5.17:1 | SC 1.4.3, ≥4.5:1 (normal text) | Pass |
| `#2563eb` text on `#eff6ff` hover background | 4.75:1 | SC 1.4.3, ≥4.5:1 | Pass |
| `#6b7280` border on `#ffffff` chip background | 4.83:1 | SC 1.4.11 Non-text Contrast, ≥3:1 | Pass |
| (for reference) `#d0d0d0` border on `#ffffff` | 1.54:1 | SC 1.4.11, ≥3:1 | **Fail — not used here** |

The last row is why `#d0d0d0` was rejected for this control despite being an existing "border" token in this app: §9.6 reasoned `#d0d0d0` panel/card borders (`.chat-window`, `.chat-input`, `.review-item`, etc.) as *decorative*, not subject to SC 1.4.11, because they bound non-interactive containers. A quick-reply chip is a real `<button>` — an interactive UI component whose boundary SC 1.4.11 explicitly covers — so that decorative exemption does not apply here and was not extended to it; `#6b7280` was used instead specifically because it passes the 3:1 UI-component minimum where `#d0d0d0` does not (1.54:1, computed above, confirms it would have failed).

### 12.4 Accessibility approach (WCAG 2.2 AA bar, §8's established target)

- Each chip is a real `<button type="button">` (`QuickReplyOptions.tsx`), not a styled `<div>`/`<a>` — SC 4.1.2, 2.1.1.
- Each chip set is wrapped in `<div role="group" aria-label="...">` — `"Choose a topic"` for the category set, `"Choose a question"` for a common-question set (`ChatMessage.optionsGroupLabel`, set by whichever `ChatWindow` function builds the message) — so a screen-reader user gets an accessible name for what the button list represents, not just a bare list of buttons.
- Chip messages append into the existing `.chat-messages` `role="log" aria-live="polite"` region exactly like every other message — same nested-live-region characteristic already flagged in this file's Open Questions (§ Open Questions, "no separate `aria-live` on `LoadingIndicator`" discussion); not a new problem introduced by this action, just consistent with how the rest of the transcript already announces.
- Reuses the global `:focus-visible` ring (`index.css`) and `prefers-reduced-motion` handling (`.chat-row`'s `message-in` animation, already neutralized under reduced motion) — nothing new needed for either.
- `QuickReplyOptions.tsx` reuses the exact `chat-row`/`BotAvatar`/`chat-bubble--assistant`/`chat-bubble__meta` shell `MessageBubble.tsx` uses, so it reads as "the assistant sent you some options" with the same visual/semantic pattern as every other assistant turn, differing only in body content (a button group instead of a lone `<p>`).

**Verification performed**: `npx @axe-core/cli http://localhost:5173/chat` (axe-core 4.13.0, chrome-headless) against the initial page load (category chips visible, the default state after the taxonomy fetch resolves) — **0 violations**. Because axe-core CLI has no built-in click/interaction support, a second pass was scripted directly against the same installed axe-core 4.13.0 engine via `selenium-webdriver`/`chromedriver` (both already present as `@axe-core/cli`'s own dependencies, reused rather than adding a new tool): navigate to `/chat`, click a category chip, wait for the resulting common-question chip set to render (and for the `.chat-row` fade-in animation to finish, to avoid a false-positive contrast read mid-transition), then run `axe.run(document)` with both chip sets simultaneously visible in the DOM — **0 violations**. (First run of that second pass, before the animation-settle wait was added, surfaced a transient `color-contrast` finding on the just-appeared chips — traced to auditing mid-fade opacity, not a real static-CSS issue; confirmed by re-running after the 250ms `message-in` animation had time to finish, which passed clean. Recorded here rather than silently discarded, since it could otherwise look like an unexplained pass/fail flip.) Manual NVDA/JAWS/VoiceOver pass not performed — same pre-existing gap as §8/§9/§10/§11 (no Windows/macOS AT available in this execution environment).

## 13. `/ops` interaction trace panel (`*develop-fe`, live-wired)

Operator-requested follow-up: a dashboard to view the full end-to-end trace for any given interaction — every LLM call and tool call, in order, with success/failure — consuming `@backend.eng`'s already-live `GET /interactions/{id}/trace` (main.py, added same run per its own docstring: "backend half of a trace dashboard"). This is `/ops`-only (the hotel support/ops staff surface); `/chat` and `/inbox` were not touched.

### 13.1 Component structure

```
frontend/src/
├── types/ops.ts                       # + TraceEventType, TraceEventOutcome, TraceEvent
├── lib/mockOpsData.ts                 # + TraceEventDto/InteractionTraceDto, toTraceEvent(), getInteractionTrace(id)
├── components/
│   ├── InteractionLogTable.tsx        # MODIFIED — new "Trace" column, per-row "View Trace"/"Hide Trace"
│   │                                  #   toggle (Set<string> expandedIds, not a single id — more than one
│   │                                  #   row's trace can be open at once), a second <tr> (Fragment-wrapped,
│   │                                  #   colSpan across all columns) rendered only while that row is expanded
│   └── InteractionTracePanel.tsx      # NEW — mounted only while its row is expanded; owns its own
│                                       #   loading/error/empty-trace state and the GET call itself
└── styles/ops.css                     # + .ops-table__trace-toggle/.ops-table__trace-row, .trace-panel__*
```

### 13.2 Why an expand-in-place row, not a modal

`aamad.config.yml`'s `ui.prefer_modals: false` rules out a dialog; a second `<tr>` (rendered from the same component as a `Fragment` wrapping both rows, so React's `key` and the table's DOM structure stay a single valid `<tbody>`) keeps the trace visually anchored to its row, matches `InteractionLogTable`'s existing "real semantic `<table>`" posture, and needs no new dependency — the toggle is plain `useState`, same as every other piece of local UI state on this page (`ReviewQueueItem`'s `isEditing`, `EscalationResolutionQueue`'s per-item resolution drafts).

### 13.3 Lazy fetch — only expanded rows call the backend

`InteractionTracePanel` is conditionally rendered (`{isExpanded && (...)}` in `InteractionLogTable`), so its `useEffect`-driven fetch only fires once a row is actually expanded — collapsing a row unmounts the panel, re-expanding remounts (and refetches) it. No row's trace is fetched up front; a log with 40 rows makes zero `/trace` calls until a user clicks "View Trace" on one of them (verified directly — see §13.6).

### 13.4 Rendering contract — human-readable, three explicit states, no color-alone signaling

- **Event-type labels**: the raw backend `event` values (`task_started`, `llm_call_completed`, `tool_call_error`, etc.) are never shown verbatim — `EVENT_TYPE_LABELS` in `InteractionTracePanel.tsx` maps each to a short human label ("Task started", "LLM call", "Tool call"), appended with a truncated (first-line, 80-char-capped) `task_name` for context. `task_name` on the wire is CrewAI's full task instruction text (often prompt-length, multi-line — confirmed directly against the live backend, see §13.6), not a short label, so truncating only the *display* string (never the underlying `TraceEvent.taskName` field) was necessary to keep one event row scannable.
- **Outcome**: three states per event, not two — `success` (✓ "Success" + `detail` text if present), `failure` (⚠ "Failure" + `error` text, styled with the same amber `.ops-indicator--escalated`-family tokens already used for the Interaction Log's own "Escalated" outcome — a failed trace step is a real functional warning, not decoration), and `null` ("… In progress" — e.g. a `task_started` event has no outcome yet per the backend's own schema comment, `# null only for task_started`). Icon + text label on every state; no reliance on color alone (`.ops-indicator` convention, unchanged from the existing Interaction Log columns).
- **Three panel-level states**: loading (`"Loading trace…"`), a real fetch error (`role="alert"`, distinct copy: `"Could not load the trace: ..."`, thrown `ApiError`/network failure surfaced the same way `InteractionLog.tsx` already handles its own fetch error), and a valid empty trace (`"No trace recorded for this interaction."`, plain status text, not an error) — the last one is the 200-with-`events: []` case the backend contract calls out explicitly (an interaction that failed before the reasoning Crew ever ran, or predates trace-event correlation). `getInteractionTrace` lets a 404 (`interaction_not_found`) surface as a thrown error unchanged, same as every other `mockOpsData.ts` call — the panel's error path handles it, nothing swallows it earlier.
- **Semantic structure**: the trace is an `<ol>` (order is meaningful — chronological, already sorted server-side, no client re-sort), one `<li>` per event; the toggle is a real `<button type="button">` with `aria-expanded` and `aria-controls` pointing at the detail row's `id`, plus an `.sr-only`-suffixed accessible name naming which interaction it targets (mirrors `ReviewQueueItem`'s per-item `aria-label` disambiguation convention, since every row's button would otherwise read identically as "View Trace" to a screen-reader user navigating by role).

### 13.5 Judgment calls recorded

- `expandedIds` as a `Set<string>` rather than a single `expandedId: string | null` — the task description said "the one(s) currently expanded" (plural allowed); a `Set` costs nothing extra in complexity and avoids an arbitrary one-row-at-a-time restriction the backend contract/PRD never asked for.
- Re-fetch on every expand (no cache across collapse/re-expand cycles) — chosen for simplicity and consistency with this page's existing "server-truth over client cache" posture (`approveReviewQueueEntry`/`rejectReviewQueueEntry` already re-fetch rather than assume), not because caching was ruled out; flagged under Open Questions below as a possible future optimization if trace panels are opened/closed frequently against a slow backend.
- `task_name` truncation is presentation-only (`shortTaskName()` in `InteractionTracePanel.tsx`) — the `TraceEvent.taskName` field itself is never truncated, so nothing is lost for a future feature (e.g. a "full task text" expansion) that might want the untruncated value.

### 13.6 Verification performed (real round trip, no mock layer)

Both backend (`:8000`, `uvicorn app.main:app --app-dir src`) and frontend (`:5173`, `npm run dev`) started fresh for this verification (neither was already running) and confirmed via `curl http://localhost:8000/health` (`{"status":"ok"}`) and `curl -o /dev/null -w "%{http_code}" http://localhost:5173/` (`200`) before proceeding.

1. `npm run lint` (`oxlint`) — clean, no findings.
2. `npm run build` (`tsc -b && vite build`) — succeeded, no TypeScript errors (11.91 kB CSS, 260.07 kB JS for the combined `/chat` + `/inbox` + `/ops` bundle).
3. `curl http://localhost:8000/interactions` confirmed real seed rows exist (40 total); `curl http://localhost:8000/interactions/{id}/trace` against one of them returned `{"interaction_id": "...", "events": []}` — this repo's existing seed data predates the trace-correlation feature, so every pre-existing row has an empty trace. To verify the populated-trace render against real data (not fabricated), sent one live `POST /chat` request (`"What time is check-in?"`) through the real `InquiryFlow`/reasoning Crew, then fetched that new interaction's `/trace` — the real backend returned 19 chronologically-ordered events (`task_started` → `llm_call_completed` → `tool_call_finished` → `task_completed`, repeated across the PII-guard, classification, KB-retrieval, sentiment, and response-composition tasks), confirming the contract exactly as documented (task_name = full task instruction text, agent_role null on task-level events, present on LLM/tool-level events).
4. Drove `/ops` in a real (headless Chromium, Playwright 1.62) browser session against the two running dev servers: loaded `/ops`, clicked "View Trace" on the row for the live `"What time is check-in?"` interaction — `aria-expanded` flipped to `"true"`, 19 `.trace-panel__event` items rendered in order, 0 styled as failures (correctly — all 19 were real successes), 0 browser console errors. Screenshot confirmed timestamp/agent/human-readable step label/outcome/detail rendering matches §13.4's contract exactly (e.g. "LLM call — Call the `pii_detector` tool exactly once on the following raw inqu…" with a ✓ Success indicator and the raw tool-call JSON as `detail`).
5. Clicked "View Trace" on a second (pre-existing, empty-trace) row in the same session — rendered `"No trace recorded for this interaction."`, confirmed distinct from both the loading and error states, not mistaken for a failure.
6. Verified the failure-styled path (no real failed interaction exists in this seed data, and deliberately not fabricating a backend failure just to screenshot one): intercepted the `GET /interactions/*/trace` network call in the same Playwright session with a synthetic single-event `outcome: "failure"` response and confirmed `.trace-panel__event--failure` styling (amber background/border) plus the ⚠ "Failure" icon+text and the `error` string rendering — confirms the CSS/conditional-render path this repo's own data cannot currently exercise, without touching any real backend/app code to force a failure.
7. Both dev servers (the ones started fresh for this verification, PIDs confirmed via `Get-NetTCPConnection` on ports 8000/5173) were stopped afterward, returning the environment to its pre-verification state.

### Sources (§13 additions)

- `backend/src/app/main.py` — `TraceEvent`/`InteractionTraceResponse` Pydantic models and `GET /interactions/{id}/trace` handler, read directly for the exact response shape (not guessed)
- `backend/src/app/persistence/trace_log.py` — read directly to confirm event semantics (which fields are null for which event types, e.g. `outcome: null only for task_started`, and that `task_name` carries full task instruction text, not a short label) before designing the human-readable label mapping
- `frontend/src/components/InteractionLogTable.tsx`/`InteractionLog.tsx`/`ReviewQueueItem.tsx` (pattern source for the table/row/toggle/fetch-state conventions, read before extending)
- `frontend/src/lib/mockOpsData.ts`/`apiClient.ts` (existing Dto/mapper/`apiFetch` convention, followed exactly for `getInteractionTrace`)
- `aamad.config.yml` (`ui.prefer_modals: false`, load-bearing for the expand-in-place vs. modal decision)
- Live round trip against the real backend (`GET /interactions`, `GET /interactions/{id}/trace`, `POST /chat`) and a real Playwright browser session against the real frontend dev server, per §13.6
- Repo state at time of this action: `frontend/src/components/InteractionTracePanel.tsx` did not exist before this action

### Assumptions (§13 additions)

- "The one(s) currently expanded" was read as permitting more than one row's trace open at once (a `Set`, not a single `expandedId`) — PRD/SAD don't specify a one-at-a-time constraint, and this table has no other single-selection precedent to match.
- Re-fetching a row's trace on every expand (rather than caching across collapse/expand cycles within one page load) was judged acceptable for this MVP's scale (per setup.md's existing "tiny log volume" framing, reused from `trace_log.py`'s own reasoning) — not a hard requirement from PRD/SAD either way.
- No client-side re-sort of `events` — the backend contract already guarantees chronological order server-side; trusting that rather than adding a redundant client-side sort.

### Open Questions (§13 additions)

- Same frontend-test-runner gap as §7/§9/§10/§11/§12 (no Vitest/RTL configured) — `InteractionTracePanel.tsx`/`InteractionLogTable.tsx`'s new expand/fetch logic has no unit/component tests.
- Same NVDA/JAWS/VoiceOver manual-pass gap as §8/§9/§10/§11/§12 — not available in this execution environment.
- Whether trace fetches should be cached across collapse/re-expand within one page load (avoiding a re-fetch if a user toggles the same row open/closed repeatedly) is undecided — flagged as a possible future optimization, not a gap in what was asked for, since the operator's task did not specify caching behavior either way.

### Audit (§13 entry)

- **Timestamp**: 2026-09-01
- **Persona**: `frontend-eng`
- **Action**: `develop-fe` (interaction trace dashboard, `/ops`)
- **Resolved runtime**: `crewai` (`aamad.config.yml runtime.target: crewai`, consistent with every prior section of this file) — recorded per `aamad-core.md`; not directly load-bearing for this frontend-only UI action, which calls one already-tested, already-live backend REST endpoint (`GET /interactions/{id}/trace`).
- **Inputs used**: `backend/src/app/main.py` (`TraceEvent`/`InteractionTraceResponse` models and handler, read directly), `backend/src/app/persistence/trace_log.py` (event-semantics reference), `frontend/src/routes/Ops.tsx`, `frontend/src/components/InteractionLog.tsx`/`InteractionLogTable.tsx`/`ReviewQueueItem.tsx` (pattern source), `frontend/src/lib/mockOpsData.ts`/`apiClient.ts` (existing convention, extended not replaced), `frontend/src/types/ops.ts` (extended), `frontend/src/styles/ops.css` (extended, same token set), `aamad.config.yml` (`ui.prefer_modals: false`), the operator's task description (backend contract, accessibility bar, verification requirements).
- **Tools/versions used**: existing scaffold (Vite v8.2.1, React 19.2.8, TypeScript ~6.0.2) — no new npm dependencies added to `package.json`. `npm run lint` (oxlint) and `npm run build` for static validation; a fresh `uvicorn app.main:app` (backend, `:8000`) and `npm run dev` (frontend, `:5173`) session, both stopped after verification; `curl` for direct contract confirmation (`GET /health`, `GET /interactions`, `GET /interactions/{id}/trace`, `POST /chat`); Playwright 1.62 (chromium, headless, already cached locally — no new install) driven via a scratch Node script for the real click-through render/screenshot verification and the synthetic-failure-response network-intercept check, run from the scratchpad directory, not committed to the repo.
- **Prohibited actions confirmed avoided**: no changes to `/chat`, `/inbox`, `mockInquiryClient.ts`, `mockEmailClient.ts`, `EscalationResolutionQueue.tsx`, `ReviewQueue.tsx`, or any `backend/` file; no new routing library or state-management dependency introduced (plain `useState`/`useEffect`, consistent with every prior section of this file); no modal dialog built (`aamad.config.yml ui.prefer_modals: false` honored via the expand-in-place `<tr>` pattern); no new CSS file or CSS-in-JS introduced (extended the existing `ops.css`).

### 12.5 Verification performed (real round trip, no mock layer)

Both backend (`:8000`) and frontend (`:5173`) were already running; confirmed via `curl http://localhost:8000/health` (`{"status":"ok"}`) and `curl http://localhost:5173/` (`200`) before starting anything. `curl http://localhost:8000/taxonomy` confirmed the live 4-category/3-question response shape ahead of writing `types/taxonomy.ts`, per the instruction to read the exact contract rather than guess it.

1. Loaded `/chat` in a real (headless Chrome) browser session — the welcome message rendered, followed by a new assistant message with 4 pill chips: "Reservations & Booking", "Check-in/Check-out & Billing", "Room Service & Amenities", "General Complaints".
2. Clicked "Reservations & Booking" — a new assistant message appeared with 3 pill chips: "What is your cancellation policy?", "Can I change the dates on my reservation?", "Do you have any rooms available this weekend?". The category chip message remained visible above it (not removed/collapsed).
3. Clicked "Do you have any rooms available this weekend?" — it appeared as a guest message bubble, the loading indicator appeared, and a real assistant reply was returned from the live backend (a genuine `InquiryFlow` response declining to check live availability and redirecting to the booking widget/front desk — not a canned string), rendered as a normal (non-escalation) bubble. Confirms the chip click drove the exact same `handleSend`/`sendInquiry`/`POST /chat` path a manually typed message would.
4. `npm run build` (`tsc -b && vite build`) — succeeded, no TypeScript errors (10.53 kB CSS, 255.37 kB JS for the combined `/chat` + `/inbox` + `/ops` bundle).

### Sources (§12 additions)

- `backend/src/app/main.py` — `CommonQuery`/`TaxonomyEntry` Pydantic models and `GET /taxonomy` handler, read directly for the exact response shape (not guessed), plus a live `curl http://localhost:8000/taxonomy` round trip confirming it
- `frontend/src/lib/apiClient.ts` (existing `apiFetch` helper, reused unmodified)
- `frontend/src/components/ChatWindow.tsx`/`MessageBubble.tsx`/`EscalationNotice.tsx`/`BotAvatar.tsx` (pattern source, read before extending)
- `project-context/2.build/frontend.md` §8 (contrast-computation method and established tokens), §9.6 (the `#d0d0d0` decorative-border exemption explicitly not extended here)
- Operator's UX-flow and visual-style specification (two-step category → common-question chip flow; reference-screenshot pill description), given directly in this action's task
- Repo state at time of this action: `frontend/src/lib/taxonomyClient.ts`, `frontend/src/types/taxonomy.ts`, `frontend/src/components/QuickReplyOptions.tsx` did not exist before this action

### Assumptions (§12 additions)

- The category-chips intro text ("Here are some things I can help with — pick a topic, or just type your question below.") and the per-category intro text (`Common questions about "<label>":`) are new, small pieces of UI copy not dictated verbatim by PRD/SAD/the operator's task — judged in-scope UI polish (same category as the existing static `WELCOME_MESSAGE`), not a fabricated backend response, since neither calls `sendInquiry` or represents an answer to a guest question.
- If `GET /taxonomy` resolves to an empty array (not currently possible against the live backend's seed config, but not contractually forbidden by the response type), no chip message is appended at all, silently — treated the same as a fetch failure from the guest's perspective (chat remains usable via free text with no visible error), since an empty chip set would be equivalent to no chips.
- Taxonomy is fetched exactly once per `ChatWindow` mount (no re-fetch/refresh trigger) — matches this app's existing "single guest session per browser tab, no persistence" posture (§ Assumptions) and the fact that the taxonomy is a static, `lru_cache`d, seed-authored config on the backend (per `main.py`'s `get_taxonomy` docstring), not data expected to change within a session.

### Open Questions (§12 additions)

- Same frontend-test-runner gap as §7/§9/§10/§11 (no Vitest/RTL configured) — `QuickReplyOptions.tsx`/`ChatWindow.tsx`'s new taxonomy logic has no unit/component tests.
- Same NVDA/JAWS/VoiceOver manual-pass gap as §8/§9/§10/§11 — not available in this execution environment.
- Whether re-clicking an already-used common-question chip a second time (§12.2 point 4 — no "used" state) should visually indicate it was already asked (e.g. a subtle "asked" badge) is undecided; PRD/SAD don't specify this and the operator explicitly asked for the simpler append-only behavior for this MVP pass — flagged here only as a possible future polish item, not a gap in what was asked for.

### Audit (§12 entry)

- **Timestamp**: 2026-08-27
- **Persona**: `frontend-eng`
- **Action**: `develop-fe` (quick-reply taxonomy chips, `/chat`)
- **Resolved runtime**: `crewai` (`aamad.config.yml runtime.target: crewai`, `AAMAD_TARGET_RUNTIME=crewai` observed in the environment, consistent with the config) — recorded per `aamad-core.md`; not directly load-bearing for this frontend-only UI action, which calls one already-tested, already-live backend REST endpoint (`GET /taxonomy`).
- **Inputs used**: `backend/src/app/main.py` (`CommonQuery`/`TaxonomyEntry`/`get_taxonomy`, read directly), `frontend/src/lib/apiClient.ts` (reused unmodified), `frontend/src/components/ChatWindow.tsx`/`MessageBubble.tsx`/`EscalationNotice.tsx`/`BotAvatar.tsx`/`ChatInput.tsx` (pattern source), `frontend/src/styles/chat.css`/`index.css` (existing token/animation/focus conventions), `project-context/2.build/frontend.md` §8–§11 (accessibility/documentation/contrast-computation conventions), `aamad.config.yml`, the operator's task description (UX flow, visual-style reference, accessibility bar, verification requirements).
- **Tools/versions used**: existing scaffold (Vite v8.2.1, React 19.2.8, TypeScript ~6.0.2) — no new npm dependencies added to `package.json`. `npm run build` for TypeScript/build validation; the operator's already-running backend (`:8000`) and frontend dev server (`:5173`), verified via `curl` before use, no new servers started; `curl` for the real `GET /taxonomy`/`POST /chat` contract confirmation and round trip; `npx @axe-core/cli` 4.13.0 (chrome-headless) for the static accessibility check; `selenium-webdriver`/`chromedriver` (both already-installed transitive dependencies of `@axe-core/cli`, invoked directly via a scratch Node script — no new dependency installed) plus the same `axe-core` 4.13.0 engine `@axe-core/cli` uses, to drive the click-through category→common-question interaction and audit both chip states plus the real send round trip in one session.
- **Prohibited actions confirmed avoided**: no changes to `/inbox`, `/ops`, `MessageBubble.tsx`, `EscalationNotice.tsx`, `ChatInput.tsx`, `mockInquiryClient.ts`, `apiClient.ts`, or any `backend/` file; no new UI component library or Tailwind introduced (plain CSS, consistent with `aamad.config.yml ui.visual_style: minimal` and every prior section of this file); no parallel send path built — common-question chips route through the existing `handleSend`.
- **Ambiguity resolved, not silently assumed**: the single-`"options"`-kind-with-baked-in-`onSelect` shape (§12.2) was chosen over two distinct message kinds as a judgment call explicitly invited by the task ("whatever's cleanest... don't force one message kind to awkwardly serve two different click behaviors"), and the reasoning is recorded in §12.2 rather than left implicit; the `#6b7280`-vs-`#d0d0d0` border choice (§12.3) was computed, not assumed, specifically because the task called out that the existing `#d0d0d0` decorative-border exemption (§9.6) should not be silently extended to an interactive control.

## 14. `/ops` interaction trace panel — per-step latency (`*develop-fe`, follow-up)

Operator-requested follow-up to §13: the backend now attaches per-step latency data (`duration_ms`/`latency_pass`/`meets_target`, sad.md §7 NFR-002's 5s target / 10s hard ceiling) to `llm_call_completed`/`llm_call_failed`/`tool_call_finished`/`tool_call_error` trace events, plus two new bare timing-marker event types, `llm_call_started`/`tool_call_started`. This section extends `InteractionTracePanel.tsx` to surface both. `/chat`, `/inbox`, `InteractionLogTable.tsx`'s row/toggle logic, `ReviewQueue.tsx`, and `EscalationResolutionQueue.tsx` were not touched; no backend file was edited.

### 14.1 Component structure

```
frontend/src/
├── types/ops.ts                       # TraceEventType + 2 new literals; TraceEvent + durationMs/latencyPass/meetsTarget
├── lib/mockOpsData.ts                 # TraceEventDto + duration_ms/latency_pass/meets_target; toTraceEvent() maps them
├── components/InteractionTracePanel.tsx  # MODIFIED — duration formatting, latency badge, slowest-step marker, start-marker handling
└── styles/ops.css                     # + .trace-panel__duration, .trace-panel__latency-badge--slow,
                                        #   .trace-panel__event--latency-fail, .trace-panel__event--slowest,
                                        #   .trace-panel__slowest-badge
```

### 14.2 Two badges, not one — Outcome vs. Latency

Latency pass/fail is a genuinely separate signal from the existing success/failure outcome badge: a step can succeed but blow the 10s ceiling, or fail fast well under it. Rather than merge the two into one indicator, the existing outcome badge text was relabeled with an explicit prefix (`"✓ Outcome: Success"` / `"⚠ Outcome: Failure"` / `"… Outcome: In progress"`, was bare `"Success"`/`"Failure"`/`"In progress"` before this action) and a new, separately-rendered latency badge sits alongside it (`"✓ Latency: Pass"` / `"⏱ Latency: Slow (over 5s target)"` / `"⚠ Latency: Fail (over 10s ceiling)"`), plus a plain-text duration (`formatDuration()`: `<1000ms` renders as `"847ms"`, `>=1000ms` as `"2.3s"` — never raw milliseconds). Both badges keep this page's existing icon+text convention; neither relies on color alone. The two are visually adjacent but structurally distinct `<span>`s, so a screen-reader user or a sighted skimmer reads them as two separate facts about the same step, not one conflated status.

### 14.3 Three latency states, one severity ladder

- `latencyPass === false` (over the 10s ceiling): reuses the *exact* amber warning treatment already established for a failed outcome — `.trace-panel__event--latency-fail` now shares `.trace-panel__event--failure`'s `#fff4e5`/`#b45f18` background/border declaration (one CSS rule, two selectors) rather than inventing a second warning palette. Can coexist with an actual outcome failure on the same row (independent booleans) without visual conflict, since both resolve to the same colors.
- `latencyPass === true, meetsTarget === false` (passes the ceiling, misses the 5s target): a deliberately *lesser* treatment — `.trace-panel__latency-badge--slow` colors just the badge text amber-toned (`#6b3d00`, reused from the same token family), no background/border box — visually distinguishable from a real fail without competing for attention with one.
- `latencyPass === true, meetsTarget === true`: a plain `✓ Latency: Pass` badge, same default styling as a passing outcome badge.

### 14.4 "Slowest step" is a different concept from "failed latency" — kept visually distinct

The single event with the highest `durationMs` in the trace (computed client-side in the render loop — `Array.forEach` tracking a running max index, `>` not `>=` so ties resolve to the first occurrence; no backend call) gets its own marker: a `#2563eb` blue border (`.trace-panel__event--slowest`, already-verified ~5.18:1 on white, reused from `.ops-table__trace-toggle`'s existing link-blue) plus an explicit `"🐢 Slowest step in this trace"` text badge. This is a *relative-ranking* signal, not a pass/fail one — the slowest step in a trace can still pass both latency checks — so it deliberately never reuses the amber fail palette; verified both ways (§14.6): a slowest step that also fails latency shows amber fill *and* the blue border ring together without visual confusion, and a slowest step that itself passes shows only the blue ring with no amber. When every event's `durationMs` is null (all-task-level or empty trace), the running max index stays `-1` and nothing is marked — no error, per the operator's explicit requirement.

### 14.5 Start markers render as a bare fact, no badge section

`llm_call_started`/`tool_call_started` (`isStartMarker()` in `InteractionTracePanel.tsx`) get a normal chronological `<li>` — timestamp, agent role, and a new human-readable label (`"LLM call started"` / `"Tool call started"`) — but the entire outcome/latency badge block is conditionally skipped for them (`{!isStart && (...)}`), since the backend sends `outcome`/`detail`/`error`/`duration_ms`/`latency_pass`/`meets_target` as `null` for these by contract (they mark a step's start, not its outcome) and rendering a badge for "null outcome" here would misrepresent a normal in-flight marker as the same kind of "in progress" state `task_started` already uses.

### 14.6 Verification performed — real round trip where possible, synthetic where the running backend could not serve it

Reused the operator's already-running dev servers (`backend :8000`, `frontend :5173`, started earlier this session) — did not start, stop, or restart either, confirmed via `curl http://localhost:8000/health` (`{"status":"ok"}`) and `curl -o /dev/null -w "%{http_code}" http://localhost:5173/` (`200`) before proceeding.

1. `npm run lint` (`oxlint`) — clean, no findings.
2. `npm run build` (`tsc -b && vite build`) — succeeded, no TypeScript errors (12.28 kB CSS, 261.61 kB JS for the combined `/chat` + `/inbox` + `/ops` bundle).
3. **A genuinely live LLM call was made** — `backend/.env` has a real `ANTHROPIC_API_KEY` — `POST /chat {"message": "What time is check-in?"}` returned a real, non-canned `InquiryFlow` reply. However, fetching that fresh interaction's `GET /interactions/{id}/trace` returned the *pre-latency* event shape: no `duration_ms`/`latency_pass`/`meets_target` keys on any event at all, and no `llm_call_started`/`tool_call_started` events among the 19 returned. Investigated rather than assumed: `git status` shows `backend/src/app/main.py` modified and `backend/src/app/persistence/trace_log.py` untracked (the per-step-latency backend work is uncommitted, on-disk-only) — and the running `uvicorn` process's creation time (18:07:57) predates both files' last-modified time (18:16–18:17). Not run with `--reload`, so the live process is serving the *old* in-memory code and cannot produce the new fields no matter what request is sent to it. Per the operator's explicit instruction not to kill/restart the shared dev servers (another session/user may be relying on them), this was **not** worked around by restarting — flagged below as an Open Question/blocker instead of silently faked.
4. Given (3), the new UI was verified against **synthetic, network-intercepted `GET /interactions/{id}/trace` responses** (Playwright 1.62.1, headless Chromium — same tool/version as §13.6, resolved via `npx`'s cache since Playwright is not a project dependency; run from the scratchpad directory, nothing committed), matching the exact documented DTO shape (`backend/src/app/main.py`'s `TraceEvent` model field set, `backend/src/app/persistence/trace_log.py`'s docstring, and the boundary values `backend/tests/unit/test_trace_log.py` asserts — 1200/5000/5001/10000/10001ms) — the same "intercept the real page, substitute a synthetic backend response" pattern §13.6 step 6 already established for exercising a state the real seed data couldn't reach. Loaded the real `/ops` page from the real dev server, clicked "View Trace" on a real row, and against the synthetic response confirmed, with 0 browser console errors throughout:
   - A fast (847ms) passing step rendered exactly two adjacent badges, `"✓ Outcome: Success"` and `"✓ Latency: Pass"`, plus `"Duration: 847ms"`.
   - A slow-but-passing (6.3s) step rendered `"⏱ Latency: Slow (over 5s target)"` with no amber row background (`trace-panel__event--latency-fail` class absent).
   - A latency-failing (12.4s) step rendered `"⚠ Latency: Fail (over 10s ceiling)"`, got both `trace-panel__event--failure` and `trace-panel__event--latency-fail` classes, and its computed `background-color` was `rgb(255, 244, 229)` (`#fff4e5`, the existing token, confirmed via `getComputedStyle`, not assumed).
   - That same 12.4s step (the trace's highest `durationMs`) also carried `trace-panel__event--slowest` and the `"🐢 Slowest step in this trace"` badge; the 847ms step did not.
   - A second synthetic trace (a 500ms step and a 9.8s step, both passing) confirmed the slowest-marker path independently of failure: the 9.8s step got `trace-panel__event--slowest` and its blue border with *no* amber background — screenshotted for visual confirmation.
   - `llm_call_started`/`tool_call_started` entries rendered with their new labels and zero `.ops-indicator` elements inside them (confirmed via a DOM count, not eyeballed).
   - Re-routing the same interception to `{events: []}` and toggling the row closed/re-opened still rendered `"No trace recorded for this interaction."` with no console errors — the "skip without erroring" empty-trace requirement holds with the new code paths in place.
5. Both dev servers were left running, untouched, per the operator's instruction (not stopped by this action).

### Sources (§14 additions)

- `backend/src/app/main.py` — `TraceEvent` Pydantic model (`duration_ms`/`latency_pass`/`meets_target` fields and their docstring), read directly, plus a live `curl`/`POST /chat` round trip against the running instance
- `backend/src/app/persistence/trace_log.py` — read directly for event/field semantics (`_latency_fields`, the 5000ms/10000ms thresholds, the two `*_started` marker handlers) — confirmed as uncommitted/untracked working-tree state via `git status`, not assumed to already be live
- `backend/tests/unit/test_trace_log.py` — boundary-value test cases (1200/5000/5001/10000/10001ms) used as the synthetic-verification fixture values, so the UI check exercises the same boundaries the backend itself is tested against
- `frontend/src/components/InteractionTracePanel.tsx`/`frontend/src/styles/ops.css` (§13's own prior work, extended not replaced)
- Live round trip against the real backend (`GET /health`, `POST /chat`, `GET /interactions/{id}/trace`) and a real Playwright browser session against the real frontend dev server, with synthetic network interception per §14.6
- Repo state at time of this action: `backend/src/app/main.py` modified (uncommitted), `backend/src/app/persistence/trace_log.py` untracked — both predate this frontend action and were read, not written, here

### Assumptions (§14 additions)

- The existing outcome badge text (`"Success"`/`"Failure"`/`"In progress"`) was relabeled to `"Outcome: Success"`/`"Outcome: Failure"`/`"Outcome: In progress"` — a visible behavior change to already-shipped §13 UI, judged necessary (not optional polish) once a second, independently-labeled "Latency: ..." badge sits next to it, per the operator's explicit example phrasing ("Outcome: Success" and "Latency: Pass" as two distinct, clearly-labeled indicators").
- A tie for "highest `durationMs`" (two events with the exact same value) resolves to whichever occurs first chronologically (strict `>` comparison) — PRD/SAD/the task don't specify tie-breaking and this trace is already chronologically ordered, so "first" is a defensible, deterministic default.
- "Slow but passing" (`meetsTarget === false`, `latencyPass === true`) severity was implemented as muted badge-text-only styling (no background/border box) rather than, e.g., a lighter-tint box — the task explicitly left the exact treatment to this persona's judgment as long as it read as less severe than an outright fail and used icon+text.

### Open Questions (§14 additions)

- **Blocker for a fully live demo of this feature, not a code gap**: the shared backend dev server process must be restarted to pick up the uncommitted `main.py`/`trace_log.py` changes before `/ops` can show real (non-synthetic) latency data — this action deliberately did not restart it per the explicit instruction not to disrupt the running instance. Whoever owns that restart should re-verify the real round trip once it's safe to bounce the server.
- Same frontend-test-runner gap as §7/§9/§10/§11/§12/§13 (no Vitest/RTL configured) — the new duration/latency-badge/slowest-step logic in `InteractionTracePanel.tsx` has no unit/component tests.
- Same NVDA/JAWS/VoiceOver manual-pass gap as §8–§13 — not available in this execution environment; the icon+text/no-color-alone convention was followed but not machine- or AT-verified beyond DOM/contrast checks.

### Audit (§14 entry)

- **Timestamp**: 2026-09-01
- **Persona**: `frontend-eng`
- **Action**: `develop-fe` (per-step latency additions to the `/ops` interaction trace panel, follow-up to §13)
- **Resolved runtime**: `crewai` (`aamad.config.yml runtime.target: crewai`, consistent with every prior section of this file) — recorded per `aamad-core.md`; not directly load-bearing for this frontend-only UI action.
- **Inputs used**: `backend/src/app/main.py` (`TraceEvent` model, read directly), `backend/src/app/persistence/trace_log.py` (event/field semantics, read directly), `backend/tests/unit/test_trace_log.py` (boundary values reused for synthetic verification), `frontend/src/types/ops.ts`/`frontend/src/lib/mockOpsData.ts`/`frontend/src/components/InteractionTracePanel.tsx`/`frontend/src/styles/ops.css` (§13's existing work, extended), the operator's task description (field contract, badge/severity/slowest-step requirements, accessibility bar, verification requirements).
- **Tools/versions used**: existing scaffold (Vite v8.2.1, React 19.2.8, TypeScript ~6.0.2) — no new npm dependencies added to `package.json`. `npm run lint` (oxlint) and `npm run build` for static validation; the operator's already-running backend (`:8000`, `uvicorn`) and frontend (`:5173`, `npm run dev`) dev servers, reused as instructed and left running; `curl` for direct contract confirmation (`GET /health`, `POST /chat`, `GET /interactions`, `GET /interactions/{id}/trace`); `git status`/`git log` to establish the uncommitted-backend-code finding; Playwright 1.62.1 (chromium, headless, resolved via `npx`'s package cache — not a project dependency, no `package.json` change) driven via scratch Node scripts (network-route interception, DOM assertions, and element screenshots) from the scratchpad directory, not committed to the repo.
- **Prohibited actions confirmed avoided**: no changes to `/chat`, `/inbox`, `InteractionLogTable.tsx`'s row/toggle logic, `ReviewQueue.tsx`, `EscalationResolutionQueue.tsx`, or any `backend/` file; no new npm dependency added; no new CSS file or CSS-in-JS (extended the existing `ops.css`); did not kill, restart, or otherwise disrupt the operator's already-running `backend`/`frontend` dev server processes, even though doing so would have enabled a fully live (non-synthetic) verification — the tradeoff and its consequence are recorded above rather than silently worked around.
