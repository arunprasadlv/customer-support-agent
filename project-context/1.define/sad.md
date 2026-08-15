# System Architecture Document (SAD) — customer-support-agent

## Input Requirements

**PRD Document**: `project-context/1.define/prd.md`
**MRD**: N/A — skipped (internal/portfolio project; see PRD Assumptions)
**User Stories**: Not yet created (`project-context/1.define/user-stories/` is empty)
**MVP Scope**: Core value proposition only — hotel-domain support crew across chat + simulated email, with PII redaction and a human-curated KB feedback loop
**Selected Runtime**: crewai (from `aamad.config.yml` → `runtime.target`, confirmed by `AAMAD_TARGET_RUNTIME=crewai`)

## System Architecture Specification

### 1. MVP Architecture Philosophy & Principles

**MVP Design Principles**

- Deterministic behavior over agent autonomy wherever a wrong call has user-visible consequences (escalation, KB writes) — see ADR-001/ADR-002.
- Minimal viable agent set: the reasoning-heavy sub-problem gets a small collaborative Crew (4 agents); everything else is either a dedicated single-purpose agent or plain deterministic code.
- Observable by default: every inquiry produces one interaction-log record (classification, sentiment, PII actions, outcome).
- No path exists to the live knowledge base except through explicit human approval (NFR-008) — this is enforced structurally, not by convention.

**Core vs Future Features**

- **MVP**: chat + simulated email intake, hotel-domain classification/retrieval/sentiment/response, simulated escalation, PII redaction, human-curated KB feedback loop, JSON domain configuration.
- **Future**: real email/helpdesk integration, live KB, other verticals, voice/social channels, enterprise scale, formal compliance certification. (Full list: PRD §4 P2.)
- All deferrals inherited directly from `prd.md` — no new deferrals introduced here.

**Technical Architecture Decisions**

#### ADR-001: Orchestration pattern — Flow (top-level) with an embedded Crew (reasoning sub-problem)

- **Context**: The PRD describes both a linear pipeline with hard conditional branches (escalation gate, channel routing, KB-approval gate) and a genuinely collaborative reasoning task (classify → retrieve → sentiment → compose). CrewAI offers two orchestration primitives for this: **Crew** (autonomous role-based delegation) and **Flow** (explicit, deterministic control flow with event-driven branching and state).
- **Decision**: Use **Flow as the top-level orchestrator** for the whole inquiry lifecycle (intake, PII redaction, escalation branch, response delivery, logging). Use **Crew** only for the classify/retrieve/sentiment/compose sub-problem, invoked as a single step inside the Flow.
- **Alternatives considered** (scored against 8 project-derived criteria, weighted 2–5 by how directly they trace to a Must-priority FR/NFR):

  | Criterion (source) | Weight | Crew-only | Flow-only | Flow + embedded Crew |
  |---|:-:|:-:|:-:|:-:|
  | Deterministic branching — escalation gate (FR-006), channel routing (FR-009/010) | 5 | 2 | 5 | 5 |
  | Human-approval integrity — KB only changes via Reviewer gate (FR-014, NFR-008) | 5 | 2 | 4 | 4 |
  | Config-driven domain swap without core rewrite (FR-012, NFR-007) | 4 | 3 | 4 | 5 |
  | Collaborative reasoning across specialized roles | 3 | 5 | 2 | 5 |
  | Traceability/explainability (NFR-003, NFR-006) | 4 | 3 | 4 | 5 |
  | Dev speed vs. 5-week timeline | 4 | 4 | 3 | 3 |
  | Extensibility — new roles without rewrite (NFR-005) | 3 | 4 | 3 | 4 |
  | Runtime maturity / lower risk | 2 | 5 | 3 | 3 |
  | **Weighted total (of 150)** | | **97 (65%)** | **110 (73%)** | **130 (87%)** |

- **Rationale**: The parts of this system where a wrong autonomous call is costly (escalation, KB writes) are exactly the parts that are logically `if/else`, not judgment calls — Flow's native `@router`/`@listen` model makes that determinism provable rather than emergent from agent delegation. Crew's strength (shared context, role delegation) is real but only needed for the reasoning block, where it scores highest.
- **Consequences**: Two orchestration concepts to learn instead of one; slightly more boilerplate than a pure-Crew build. In exchange, the escalation and KB-approval paths are structurally guaranteed rather than dependent on an LLM manager agent behaving consistently.

#### ADR-002: Escalation decision and interaction logging are deterministic Flow steps, not LLM agents

- **Context**: `prd.md`'s Core Agent Definitions table names `escalation_manager` and `interaction_logger` as agents (that table is explicitly marked "indicative" — resolving it into a concrete runtime shape is this document's job). The SAD template caps MVP agent count at 3–4.
- **Decision**: `escalation_manager` and `interaction_logger` are **not** CrewAI agents. The escalation decision is a Flow `@router` reading the classifier's confidence score and the sentiment agent's score (both already computed by the reasoning Crew) — no separate LLM call. Interaction logging is a plain Flow step that persists a record; it performs no reasoning.
- **Rationale**: Neither task requires language understanding beyond what the reasoning Crew already produced — routing on a threshold and writing a log record are procedural. Collapsing them keeps the true agent count at the template's guideline (4-agent reasoning Crew) while still fully satisfying FR-006/FR-007/FR-008 as *behaviors* — the PRD does not require these to be LLM-backed, only that the behaviors happen.
- **Consequences**: Faster and cheaper (no extra LLM calls on the hot path); escalation thresholds become an explicit, testable, tunable value rather than opaque agent judgment — directly supports AC-003 ("never fabricate, always flag clearly"). Trade-off: less flexible than an LLM judging escalation-worthiness in genuinely ambiguous cases.
- **Status: Confirmed** (stakeholder-affirmed, 2026-08-05) — `escalation_manager`/`interaction_logger` stay deterministic Flow logic. Not revisited based on future QA results; if threshold tuning proves insufficient, the fix is adjusting the threshold values, not converting either into an LLM agent.

#### ADR-003: PII Guard is a standalone dedicated agent, run before the reasoning Crew

- **Context**: Stakeholder explicitly required a dedicated PII agent (not a shared utility, decided 2026-08-05). FR-011 requires redaction on "any content passed to the knowledge-retrieval **or LLM** components" — which includes the classifier, not just retrieval/logging.
- **Decision**: `pii_guard` runs as its own Flow step immediately after intake normalization, **before** the reasoning Crew is invoked at all. It is not a member of the reasoning Crew — it's a security gate that must run unconditionally and first, independent of classification outcome.
- **Rationale**: If PII redaction ran inside or after the reasoning Crew, raw PII would already have reached the classifier/retriever, violating FR-011's "any LLM component" wording. Running it first and standalone also makes it trivially auditable (NFR-006) as a single well-defined step.
- **Consequences**: This is the 5th LLM-backed agent, one beyond the template's 3–4 guideline. Documented and justified here rather than silently exceeded — the reasoning Crew itself still holds to 4 agents (ADR-002 keeps the other two "agents" out of the LLM count entirely).

**Net agent architecture**: 5 CrewAI agents total — a 4-agent reasoning Crew (`query_classifier`, `knowledge_retriever`, `sentiment_analyzer`, `response_composer`) plus 1 standalone agent (`pii_guard`), orchestrated by one Flow. `escalation_manager` and `interaction_logger` from the PRD's indicative table are realized as deterministic Flow logic, not agents.

**Frontend**: React (Vite) single-page app — a chat widget, a simulated email "inbox" view, and an internal ops view (interaction log + KB review queue with Reviewer approve/edit/reject). Justification: PRD doesn't mandate a framework; React is the lowest-friction default for a 5-week single-developer build with three UI surfaces sharing one component library and one API client. Recorded as a SAD-level default, not a PRD requirement — see Assumptions.

**Backend**: Python + FastAPI. Justification: matches CrewAI's Python runtime (no cross-language boundary), fast to scaffold a chat/email/review-queue API surface within the timeline, async-friendly for streaming responses later if needed.

**Streaming**: Non-streaming for MVP — NFR-002's "a few seconds" target doesn't require token-level streaming; request/response is simpler to build and test within 5 weeks. Flagged as a Future Work candidate if response composition proves slow in practice — but explicitly **not** an acceptable fallback for an unmeasured/failing latency spike; see §7 Latency Spike & Fallback Plan.

### 2. Multi-Agent System Specification

**Agent Architecture Requirements**

| Agent | Membership | Role | Goal | Tools | Model | Memory |
|---|---|---|---|---|---|---|
| `query_classifier` | Reasoning Crew | Support Query Classifier | Classify inquiry into a domain-configured intent (FR-002) | domain taxonomy lookup (from JSON domain config) | `claude-haiku-4-5` | None — stateless per inquiry |
| `knowledge_retriever` | Reasoning Crew | KB Retrieval Specialist | Retrieve grounding content for the classified intent (FR-003) | KB search (scoped to active domain config) | `claude-haiku-4-5` | None |
| `sentiment_analyzer` | Reasoning Crew | Guest Sentiment Analyst | Score sentiment/frustration (FR-004) | sentiment scorer | `claude-sonnet-5` | None |
| `response_composer` | Reasoning Crew | Response Composer | Compose tone-adjusted response from classification + retrieval + sentiment (FR-005); must not fabricate when KB has no match (AC-003) | — (LLM only) | `claude-sonnet-5` | None |
| `pii_guard` | Standalone | PII Redaction Guard | Detect/redact PII before any other component sees the raw text (FR-011) | PII detector | `claude-haiku-4-5` | None |

Memory is deliberately **none/short-lived** for all agents (reproducibility per `aamad-core.md`; no cross-inquiry state needed for MVP). Least-privilege tool access: each agent gets only the tool(s) its row lists — `knowledge_retriever` cannot write to the KB (write access is Reviewer-only, ADR below), and no agent has network/file access beyond its named tool.

#### ADR-004: Per-agent model tier — Haiku 4.5 vs. Sonnet 5, split by task stakes

- **Context**: CrewAI supports a distinct `llm` per agent; nothing requires all 5 agents to share one model. The 5 agents split cleanly by whether errors are cheap (classification, retrieval, PII pattern-matching) or feed a high-stakes downstream decision (sentiment → escalation gate; composition → guest-facing voice, AC-003).
- **Decision**: `query_classifier`, `knowledge_retriever`, and `pii_guard` run on **`claude-haiku-4-5`** (fastest/cheapest tier — $1/$5 per MTok). `sentiment_analyzer` and `response_composer` run on **`claude-sonnet-5`** (near-Opus quality on instruction-following/groundedness — $3/$15 per MTok, introductory $2/$10 through 2026-08-31).
- **Rationale**: `pii_guard` and `query_classifier` run unconditionally on every single inquiry (FR-011, FR-002) — cost and latency compound most there, and both tasks (pattern-based PII detection, classification against a small fixed taxonomy) are well within Haiku's capability. `sentiment_analyzer`'s score directly gates the escalation decision (FR-006/AC-002) — a lighter model under-calling frustration in a polite-but-furious message would silently degrade a Must-priority behavior, so the extra cost buys correctness on the one score that matters most. `response_composer` is the system's guest-facing voice and carries the AC-003 "never fabricate" bar — the highest quality requirement in the system.
- **Consequences**: 3 of 5 model calls per inquiry run on the cheap/fast tier, which directly serves NFR-002 (a few seconds end-to-end across 5 sequential calls). No agent currently uses Opus 5 — the flagship tier has no slot in this architecture, since ADR-002 already moved the one place genuinely hard agentic judgment could have lived (escalation) out to deterministic code. Opus 5 remains the documented upgrade path if a future role needs real multi-step reasoning (e.g., cross-domain synthesis once a second vertical exists).

#### ADR-005: `knowledge_retriever` uses keyword/section-scored retrieval against `domain_config.json` — no vector store

- **Context**: `domain_config.schema.json` (scaffolded by `@project-mgr`) left `taxonomy` and `knowledge_base` item shapes as `"TODO(@backend.eng): shape undefined at scaffold time"`. Without a pinned algorithm, `knowledge_retriever`'s `kb_search` tool is unspecified — risking an ad hoc second retrieval stack (e.g., embeddings/a vector-DB SaaS) that would contradict §4 Data Architecture's existing "no vector DB / external database for MVP" decision.
- **Decision**: `kb_search` is a pure, local, deterministic function — no embeddings, no external call:
  1. **Filter** `domain_config.json`'s `knowledge_base` array to entries where `entry.intent == intent` (the `ClassificationResult.intent` from `classify_task`) — this is what keeps retrieval domain-agnostic (driven by config content, not hardcoded category branches), satisfying FR-012/AC-009.
  2. **Score** each surviving entry by keyword overlap: `relevance_score = |keywords(query) ∩ entry.keywords| / |entry.keywords|`.
  3. **Floor**: drop entries scoring below **`0.20`**.
  4. Return the top **3** surviving entries as `retrieved_snippets`; `match_found = true` iff at least one entry cleared the floor.
- **Config shapes** (resolves the schema's TODOs):
  ```
  taxonomy[]:       { intent: str, label: str, keywords: string[] }
  knowledge_base[]: { kb_entry_id: str, intent: str, section: str, keywords: string[], content: str }
  ```
- **Required seed set**: one `taxonomy` entry per FR-013 scenario category — `reservations_booking`, `checkin_checkout_billing`, `room_service_amenities`, `general_complaints` — each with at least one `knowledge_base` entry, so Phase 1 of MVP Build Sequencing (below) has real content to retrieve against.
- **Rationale**: Keyword/section scoring is fully explainable (every `relevance_score` traces to specific overlapping words, unlike a cosine-similarity float from an embedding model), requires zero new infrastructure, and is trivially fast enough for NFR-002 at MVP's KB scale (a handful of entries per intent, four intents). The floor is what makes `match_found=false` an honest signal rather than "always return the closest thing" — directly protects AC-003's no-fabrication rule via `ComposedResponse.grounded` (see Typed Task Outputs).
- **Consequences**: Retrieval quality is bounded by keyword overlap, not semantic similarity — a guest phrasing a question with none of the KB entry's keywords will miss even on-topic content and correctly escalate rather than silently degrade. Documented as a known MVP limitation, not a bug; a vector-based upgrade is the natural Future Work path if this proves too blunt in QA.

**Task / Turn Orchestration**

Flow (`InquiryFlow`), one instance per inquiry, regardless of channel:

1. **`@start` — intake_normalize**: receive raw inquiry (chat message or simulated-email submission) → normalize to `{channel, raw_text, sender_id, timestamp}`.
2. **`@listen` — pii_redact**: `pii_guard` agent redacts/masks PII in `raw_text` → produces `clean_text` and `redaction_actions` (see Typed Task Outputs below). Runs before step 3, no exceptions (FR-011).
3. **`@listen` — run_reasoning_crew**: `reasoning_crew.kickoff(clean_text, domain_config)` — sequential process, task-context chaining passes `intent` → `retrieved_snippets` → `sentiment_score` → `draft_response` through the four agents in order, each field typed per the Pydantic contracts below.
4. **`@router` — escalation_gate**: reads `confidence`, `sentiment_score`, `grounded` from step 3's output (see Typed Task Outputs below) and evaluates, in order, three independent OR'd conditions — any one true routes to `escalate`:
   - `grounded == false` (not tunable — AC-003 mandates escalation over fabrication whenever there's no KB match)
   - `confidence <= 0.70` (classifier confidence at or below this line is not trusted)
   - `sentiment_score >= 0.75` (equivalent to `sentiment_label == "angry"` — see Typed Task Outputs)
   - **`escalate` branch** (any condition above true): flag the interaction for simulated human handoff; guest-visible message states this clearly (AC-003). The (simulated) human's resolution is recorded separately once submitted — see the decoupled `EscalationResolutionFlow` below — not blocked on here.
   - **`respond` branch** (else): deliver `draft_response`.
   - All three numbers are MVP starting values, deliberately simple (independent thresholds, no compound/weighted scoring) and expected to be tuned from `@qa-eng` acceptance results — not a final calibration.
   - **Ordering note**: as documented, this step runs after the full reasoning Crew (including `compose_response_task`) completes. If the §7 Latency Spike shows p95 missing target, fallback (2) there reorders this gate to run before `compose_response_task`, invoking the composer only on the `respond` branch — not applied by default, only on measured evidence.
5. **`@listen` — deliver_response**: send `draft_response` (or escalation notice) back via the originating channel — chat reply or simulated email reply (FR-005, FR-010, AC-006).
6. **`@listen` — log_interaction**: always runs (both branches) — persists one interaction-log record: query, classification, sentiment, PII actions taken, outcome (FR-007).

**Typed Task Outputs (Pydantic contracts)**

Every CrewAI `Task` in the reasoning Crew, plus `pii_guard`'s task, binds `output_pydantic=<Model>` (per `adapter-crewai.md`'s structured-output-contract Quality Gate) — no task returns free-form prose for a downstream step or the `@router` to parse. This is what makes `escalation_gate` (step 4) a pure function over typed fields rather than a text-sniffing heuristic:

| Task (agent) | Model | Fields |
|---|---|---|
| `redact_pii_task` (`pii_guard`) | `RedactionResult` | `clean_text: str`, `redaction_actions: list[RedactionAction]` — `RedactionAction = {entity_type: str, span_start: int, span_end: int, method: Literal["mask","remove"]}` |
| `classify_task` (`query_classifier`) | `ClassificationResult` | `intent: str`, `confidence: float` (0.0–1.0) |
| `retrieve_knowledge_task` (`knowledge_retriever`) | `KBRetrievalResult` | `retrieved_snippets: list[KBSnippet]`, `match_found: bool` — `KBSnippet = {kb_entry_id: str, content: str, relevance_score: float}`; `relevance_score` and `match_found` are computed by the keyword/section-scored algorithm in ADR-005, not a vector similarity |
| `analyze_sentiment_task` (`sentiment_analyzer`) | `SentimentResult` | `sentiment_score: float` (0.0–1.0), `sentiment_label: Literal["neutral","frustrated","angry"]` — boundaries: `neutral` < 0.40, `frustrated` 0.40–0.74, `angry` ≥ 0.75 |
| `compose_response_task` (`response_composer`) | `ComposedResponse` | `draft_response: str`, `grounded: bool` (false whenever `match_found` was false — structurally enforces AC-003's no-fabrication rule, not just a prompt instruction) |

`escalation_gate` (step 4) reads exactly three typed fields — `confidence: float`, `sentiment_score: float`, `grounded: bool` — nothing else; this closed input set, combined with the pinned thresholds in step 4 (`confidence <= 0.70`, `sentiment_score >= 0.75`, `grounded == false`), is what makes ADR-002's "pure function" claim true in code, not just in the ADR's prose.

`log_interaction_task` maps `draft_response → response_text` and carries `intent`, `confidence`, `sentiment_score`, and a summary of `redaction_actions` through unchanged into the `interaction_log` record (§4/§6) — same field names throughout, no re-mapping/renaming between the Flow, the Crew, and the persisted log.

Decoupled second flow, `EscalationResolutionFlow` — triggered independently whenever a (simulated) human operator submits a resolution for an escalated interaction (this does not keep `InquiryFlow` waiting; escalation and its eventual human resolution are asynchronous by nature):

1. Receive `{original_inquiry_id, resolution_text}`.
2. Write a candidate KB entry to the review queue, linked to the original query (FR-008, AC-010).

Third, fully separate write path — the **only** path that can modify the live KB (NFR-008):

1. Reviewer views a queued candidate entry.
2. Approve (optionally edited) → entry written to live KB, retrievable by `knowledge_retriever` from that point on (FR-014, AC-011).
3. Reject → entry discarded, KB unchanged.

**Error handling / retries / timeouts**: reasoning Crew tasks get a per-task timeout budget (`max_iter <= 12` per `adapter-crewai.md` baseline); on `pii_guard` failure, the Flow halts and logs a Diagnostic rather than passing unredacted text forward (fail-closed, not fail-open, given FR-011 is a Must). On `response_composer` producing no groundable answer, `escalation_gate` treats it as low-confidence and routes to escalate rather than returning a fabricated answer (AC-003).

**Runtime-Conditional Configuration (crewai)**

- **Process type**: `Process.sequential` for the reasoning Crew (per `adapter-crewai.md`'s preference for reproducible MVP builds — no manager-agent/hierarchical process needed for a 4-step linear chain).
- **Two separate configuration layers** (do not conflate):
  1. **Framework-level** `config/agents.yaml` + `config/tasks.yaml` — static CrewAI role/goal/backstory/task definitions, per `adapter-crewai.md`'s YAML-externalization rule. Defines the 5 agents' identities.
  2. **Domain-level** `domain_config.json`, schema-validated (stakeholder-confirmed format) — the swappable KB content, intent taxonomy, and prompt fragments (FR-012/FR-013). Loaded at runtime and templated into task descriptions/inputs; swapping this file (and only this file) is what NFR-007's domain-portability guarantee depends on.
- `max_iter <= 12`, `max_retry_limit >= 2`, `allow_delegation=false` for all 5 agents (no manager-agent pattern justified for this MVP scope).
- `kickoff_for_each` is not used — one `kickoff()` per inquiry, invoked from the Flow step.

### 3. Frontend Architecture Specification

**Technology Stack**: React + Vite, TypeScript, minimal CSS (no heavy component library — matches `ui.visual_style: minimal` in `aamad.config.yml`), no client-side state library beyond React state/context (scope doesn't need more).

**Application Structure**

- `/chat` — guest chat widget (primary interaction surface, NFR-001).
- `/inbox` — simulated email inbox view (submit an "email" inquiry, view "sent" replies).
- `/ops` — internal view: interaction log (NFR-003) + KB review queue (Reviewer approve/edit/reject, FR-014).
- One API client module; no backend logic in this epic (per `development-workflow.md` module boundaries).

**Interface Requirements**

- Chat/inbox: loading state while `InquiryFlow` runs; clear, distinct visual treatment for an escalation notice vs. a normal answer (AC-003).
- Ops view: per-interaction detail (classification, sentiment score, PII redaction indicator) supporting explainability; review-queue items show original query + proposed KB entry side by side before Reviewer decides.
- Future Work placeholders (visibly marked, non-functional for MVP): real-email settings, other-domain selector, voice input.

### 4. Backend Architecture Specification

**API Architecture** (FastAPI)

- `POST /chat` — `{message, session_id}` → `{reply, escalated: bool}`. Triggers `InquiryFlow` with `channel=chat`.
- `POST /email` — `{from, subject, body}` → `{reply_body, escalated: bool}`. Triggers `InquiryFlow` with `channel=email`.
- `POST /escalations/{id}/resolve` — `{resolution_text}` → triggers `EscalationResolutionFlow`.
- `GET /review-queue` / `POST /review-queue/{id}/approve` / `POST /review-queue/{id}/reject` — the sole KB-write path (NFR-008).
- `GET /interactions` — interaction log for the ops view.
- Validation: request schemas enforced (FastAPI/Pydantic); error envelope `{error_code, message}`; no rate limiting for MVP (no real external traffic).

**Data Architecture** (justified minimal store — PRD requires persistence, so this isn't deferred)

- Local file-based or embedded DB (e.g., SQLite) for: KB content (seeded from `domain_config.json`, then mutable only via approved review-queue writes), interaction log, review queue. No vector DB / external database for MVP (Out of Scope — Future Work).

**Runtime Integration Layer**

- FastAPI route handlers invoke `InquiryFlow.kickoff()` / `EscalationResolutionFlow.kickoff()` synchronously (non-streaming, per §1).
- Agent configuration (`config/agents.yaml`, `config/tasks.yaml`) loaded once at process start; `domain_config.json` loaded once at start and hot-swappable only by restart for MVP (no live domain-switching UI).
- Prompt Trace and per-task logs written per `adapter-crewai.md` Logging rules, redacting secrets, under `project-context/2.build/logs`.

**Authentication & Secrets**

- No user authentication for MVP (Out of Scope). LLM provider is **Anthropic** (stakeholder-confirmed); specific model TBD. API key via env var only (`.env.example` entry: `ANTHROPIC_API_KEY`) — never committed, never in Prompt Trace.

### 5. DevOps & Deployment Architecture

- **CI/CD (minimal MVP)**: lint (ruff/flake8), test (pytest), build — no deploy automation beyond config scaffolding, per `delivery-workflow.md`.
- **Hosting**: single-service local/dev target for MVP demo; `/health` endpoint required. Specific cloud target is an Open Question for `@devops-eng`.
- **IaC / multi-region / advanced monitoring**: Future Work — not scoped.
- **Observability**: baseline structured logs (interaction log, PII-action log) + `/health`; no APM for MVP.

### 6. Data Flow & Integration Architecture

Guest (chat or simulated email) → FastAPI route → `InquiryFlow` (`pii_guard` → reasoning Crew → escalation router → response/escalation) → reply delivered on originating channel, interaction logged. Escalations separately resolved via `EscalationResolutionFlow` → review queue → Reviewer approval → live KB (the only integration point that mutates persistent domain knowledge). No external API/tool integrations for MVP — everything is local/simulated per Constraints in `system-description.md` §5. Errors at any Flow step surface as a chat/email-visible "something went wrong, escalating to a human" message rather than a silent failure or a fabricated answer (AC-003 extends to the error path).

### 7. Performance & Scalability Specifications

- Response-time target: **p95 ≤ 5 seconds** end-to-end per inquiry — an engineering interpretation of NFR-002's qualitative "a few seconds," pinned so it's measurable rather than assumed. Not yet verified: the pipeline is 5 sequential LLM calls per inquiry (`pii_guard`, `query_classifier`, `knowledge_retriever`, `sentiment_analyzer`, `response_composer`), 2 of them on the Sonnet tier (ADR-004) — treated as a spike to measure, not a given.
- Concurrency: not a design driver for MVP (no real traffic) — single-process FastAPI is sufficient.
- Scaling path: deferred entirely (Out of Scope — enterprise-scale load is explicit Future Work in the PRD).
- Token/cost controls: `max_iter <= 12` per agent task; no retries beyond `max_retry_limit >= 2` to bound cost per inquiry.
- **Hard ceiling**: Flow-level `max_execution_time` set to **10s** (2× the p95 target, per `adapter-crewai.md`'s execution-budget guidance) — a stuck or abnormally slow run degrades automatically to the `escalate` branch rather than hanging indefinitely.

**Latency Spike & Fallback Plan**

- **Spike timing**: immediately after Phase 1 (`/chat` vertical slice — see MVP Build Sequencing) lands, *before* starting Phase 2, `@qa-eng`/`@backend-eng` measure p95 latency over a representative sample (20+ requests spanning all four hotel scenario categories), using the per-task Trace Log timing already required by `adapter-crewai.md` Logging. This is a required gate before Phase 2 begins, not an optional nice-to-have.
- **If p95 exceeds 5s, apply this fallback ladder incrementally** (measure again after each step; stop as soon as target is met) — ordered by invasiveness/risk, not by expected savings:
  1. **Downgrade `sentiment_analyzer` from Sonnet to Haiku** — a config-only change (`agents.yaml`), fully reversible, no architecture impact. Re-run AC-002 fixtures afterward to confirm sentiment-scoring accuracy didn't regress (ADR-004 put this on Sonnet specifically to avoid under-calling frustration — this fallback carries real quality risk, not just a cost/latency trade).
  2. **Skip `compose_response_task` on the `escalate` branch** — a pipeline reordering, not a config tweak: `escalation_gate`'s three inputs (`confidence`, `sentiment_score`, `grounded`) are all available once `sentiment_analyzer` finishes (`grounded` is just `match_found` carried over from `retrieve_knowledge_task` — see Typed Task Outputs), so `compose_response_task` does not need to run before the gate decides. Reorder the Crew to classify → retrieve → sentiment → `escalation_gate` → `compose_response_task` only on the `respond` branch. This removes one full Sonnet call on every inquiry that was going to escalate anyway, with zero quality trade-off (today that composed output is silently discarded on the escalate branch). If adopted, §2 step 4's ordering is amended accordingly — not applied by default; only on evidence from the spike.
  3. **Last resort**: revisit `response_composer`'s Sonnet tier on the `respond` branch itself — this is the one guest-facing, AC-003-critical call, so it's the most reluctant step, attempted only if (1)+(2) together still miss target.
- **Explicitly ruled out as a fix**: reintroducing streaming. Non-streaming is an already-settled decision (§1 Streaming) — streaming would hide latency from the guest without reducing actual compute time, and silently reopening a closed decision to paper over an unmeasured assumption is exactly the anti-pattern this plan exists to avoid. If streaming is ever revisited, it must be its own deliberate decision, not a Band-Aid applied under deadline pressure.

### 8. Security & Compliance Architecture

- **AuthN/AuthZ**: none for MVP (Out of Scope, documented).
- **PII handling**: `pii_guard` redacts/masks before any other component sees raw text (FR-011); redaction actions are themselves logged (NFR-006); best-practice encryption at rest for stored PII-adjacent data (NFR-004) — no named regulation certified (GDPR/CCPA/HIPAA remains an Open Question).
- **KB integrity**: enforced structurally — only the Reviewer-approval write path can mutate the live KB (NFR-008); no agent holds KB write access.
- **Input validation**: FastAPI/Pydantic schema validation on all endpoints; PII-guard treated as a security-critical fail-closed step (§2 error handling).
- **Compliance**: general best-practice only for MVP; formal certification explicitly deferred — flagged again here per `aamad-core.md`'s Security and Compliance rule, and a Security Assessment (`@security.eng`) is required before Deliver per `aamad.config.yml` (`security.require_security_assessment: true`).

### 9. Testing & Quality Assurance Specifications

- **Unit**: PII-guard redaction correctness; escalation-router threshold logic (ADR-002 makes this a pure function — directly unit-testable, a deliberate benefit of that decision); domain-config JSON schema validation.
- **Integration**: full `InquiryFlow` run per hotel scenario category (reservations & booking, check-in/check-out & billing, room service & amenities, general complaints) mapped to AC-001–AC-011.
- **Smoke/acceptance**: AC-001 through AC-011 from `system-description.md`/`prd.md` form the acceptance suite; `@qa-eng` maps test cases 1:1 to these IDs.
- **Runtime-specific checks**: reasoning-Crew task outputs schema-checked at each context-chain step (malformed output fails closed to escalation, not a guess).
- Security assessment recommended before Deliver (see §8).

### 10. MVP Launch & Feedback Strategy

- No external beta/pilot — internal/portfolio project (PRD §9). "Launch" = a working local demo covering all four in-scope hotel scenarios plus the escalation and KB-review-approval flows end-to-end.
- Success metrics tied to PRD §7: AC-001–011 pass rate, qualitative classification/escalation correctness across the four scenario categories, NFR-002 latency observed in practice.
- Iteration priorities after first working demo: (1) close any AC gaps found by `@qa-eng`, (2) revisit the self-improvement roadmap items from the stakeholder brainstorm (LLM-assisted KB drafting, gap detection — currently Future Work, not yet committed).

## MVP Build Sequencing

All three frontend surfaces (`/chat`, `/inbox`, `/ops`) are already implemented against mock clients (`mockInquiryClient.ts`, `mockEmailClient.ts`, `mockOpsData.ts`) — the `@frontend-eng` epic is complete. Remaining work is `@backend-eng`/`@integration-eng`, and per reviewer feedback it proceeds as a vertical slice through one user journey at a time, not all three at once:

| Phase | Scope | Wires up | Proves |
|---|---|---|---|
| **1** | Prerequisite: seed `domain_config.json` with the 4 FR-013 taxonomy/KB entries per ADR-005 (done — see Sources). Then backend `InquiryFlow` for `channel=chat` only: `pii_guard` → reasoning Crew (retrieval per ADR-005) → `escalation_gate` (§2 step 4, thresholds now pinned) → respond-or-escalate → `log_interaction`. No `EscalationResolutionFlow`, no Reviewer write path yet — escalated interactions are flagged and logged, nothing more. | `/chat` (replaces `mockInquiryClient.ts` with the real `POST /chat` per §4) | AC-001, AC-002, AC-003, AC-007, AC-008, AC-009 |
| **2** | Add `channel=email` to `InquiryFlow` (same pipeline, different adapter). Add `EscalationResolutionFlow` — now needed since Phase 1 produces real escalations to resolve. | `/inbox` (replaces `mockEmailClient.ts` with `POST /email`) | AC-006, AC-010 |
| **3** | Review-queue endpoints + the Reviewer approve/reject write path — the third, KB-write-only path (NFR-008). | `/ops` (replaces `mockOpsData.ts` with `GET /interactions`, `GET/POST /review-queue/...`) | AC-011 |

Phase 1 is the walking skeleton: it is the only phase that touches every architectural layer (Flow, reasoning Crew, PII gate, escalation gate, persistence) end-to-end, so it de-risks the rest of the build before `/inbox` and `/ops` — which mostly add a channel adapter and a write path onto an already-proven pipeline — are attempted.

**Gate between Phase 1 and Phase 2**: the §7 Latency Spike (measure p95, apply the fallback ladder if needed) runs immediately after Phase 1 lands and before Phase 2 starts — cheaper to fix the reasoning Crew's shape once, on the smallest working slice, than after `/inbox` doubles the traffic through the same pipeline.

## Implementation Guidance for AI Development Agents

1. `@project-mgr` — environment/dependency setup per `setup.md` (Python + FastAPI + CrewAI backend, `config/agents.yaml`, `config/tasks.yaml`, `domain_config.json` scaffolds). Frontend scaffold already exists.
2. `@frontend-eng` — **complete**: chat, inbox, and ops UI surfaces built per §3, running against mock clients pending backend wiring.
3. `@backend-eng` — `InquiryFlow`/`EscalationResolutionFlow`, the 5 agents, FastAPI routes, local data store, per §2/§4 and ADR-001/002/003 — built in the 3 phases above, Phase 1 first.
4. `@integration-eng` — wire FE ↔ BE per the API contract in §4, replacing each mock client as its phase's backend work lands (see MVP Build Sequencing table).
5. `@qa-eng` — validate against AC-001–011 (§9), phase by phase as each lands rather than only at the end.
6. `@security-eng` — assessment before Deliver (§8, required by `aamad.config.yml`).
7. `@devops-eng` — deploy config, CI, runbook, user guide (§5) — Deliver phase only.

## Architecture Validation Checklist

- [x] PRD requirements mapped to architectural components (every FR/NFR/AC referenced above traces to a §1–§9 element)
- [x] Agents designed for the domain and selected runtime (5 CrewAI agents, JSON domain config, hotel pilot — §2)
- [x] Frontend and backend contracts agree on schemas (§3/§4 endpoint table)
- [x] Secrets via env vars only (§4 Authentication & Secrets)
- [x] MVP vs Future Work boundaries explicit (§1 Core vs Future, inherited from PRD §4 P2)
- [x] Resolved `AAMAD_TARGET_RUNTIME` recorded in Audit

## Sources

- `project-context/1.define/prd.md`
- `project-context/1.define/system-description.md`
- `aamad.config.yml` (`runtime.target: crewai`, `ui.visual_style: minimal`, `security.require_security_assessment: true`)
- `.claude/rules/adapter-crewai.md` (YAML config-externalization, sequential-process default, `max_iter`/`max_retry_limit` baselines)
- Stakeholder decision (2026-08-05): Flow + embedded Crew orchestration, scored against project-derived criteria (ADR-001)
- `backend/domain_config.json`, `backend/domain_config.schema.json` — seeded/formalized 2026-08-06 per ADR-005

## Assumptions

- React/Vite frontend and FastAPI backend are SAD-level defaults, not PRD requirements — PRD was silent on both. Justified by 5-week timeline and Python/CrewAI alignment (§1, §3, §4).
- Non-streaming request/response chosen over token streaming for MVP simplicity; revisit if latency (NFR-002) becomes an issue in practice.
- SQLite/file-based local storage assumed sufficient for MVP data volume (four hotel scenario categories, no real traffic).
- `escalation_manager` and `interaction_logger`, named as agents in `prd.md`'s indicative table, are implemented as deterministic Flow logic rather than LLM agents (ADR-002) — behavior-equivalent to their FR/AC requirements, but a resolved implementation-level deviation from the PRD's literal table worth flagging back to the stakeholder if it matters for the "5 agents" framing elsewhere.
- LLM provider is Anthropic (stakeholder-confirmed, 2026-08-05). Specific models are now resolved per agent (ADR-004): `claude-haiku-4-5` for `query_classifier`/`knowledge_retriever`/`pii_guard`, `claude-sonnet-5` for `sentiment_analyzer`/`response_composer`. `.env.example` (to be created in Phase 2 setup) will define `ANTHROPIC_API_KEY`.
- `backend/domain_config.json` is seeded (2026-08-06) with the 4 FR-013 taxonomy entries and 3 `knowledge_base` entries each (12 total), per ADR-005's shapes; `backend/domain_config.schema.json` updated to formalize those shapes (was previously `"TODO(@backend.eng): shape undefined"`). Keyword lists are a reasonable MVP starting set, not exhaustively tuned — `@backend-eng`/`@qa-eng` may extend them if Phase 1 testing shows real guest phrasing missing common keywords (ADR-005 Consequences already flags this as an expected limitation, not a bug).
- NFR-002's p95 ≤ 5s target and 10s hard ceiling (§7) are engineering interpretations of PRD's qualitative "a few seconds," not stakeholder-confirmed numbers — reasonable defaults pending the Phase 1 latency spike's actual measurement, not a guarantee the unmodified 5-call pipeline will meet them.

## Open Questions

Carried forward from `prd.md` (unresolved as of this document):

- Actual budget for the project (timeline confirmed: 5 weeks).
- Which specific regulation, if any, PII handling must ultimately comply with.
- Hosting/infrastructure target for MVP — for `@devops-eng` to propose during Phase 3 planning.

New, raised by this SAD:

**Resolved this round**:

ADR-002 (`escalation_manager`/`interaction_logger` as deterministic Flow logic, not agents) is confirmed final — see ADR-002 Status. Per-agent Claude model selection is resolved via ADR-004 — Haiku 4.5 for classification/retrieval/PII, Sonnet 5 for sentiment/composition. No agent currently needs Opus 5; documented as the upgrade path if a future role needs deeper multi-step reasoning. `escalation_gate` numeric thresholds resolved (2026-08-06): `confidence <= 0.70` OR `sentiment_score >= 0.75` OR `grounded == false` → escalate (§2 step 4); `sentiment_label` boundaries pinned to match (`neutral` < 0.40, `frustrated` 0.40–0.74, `angry` ≥ 0.75). Explicitly a simple, independently-thresholded MVP starting point, not a tuned/calibrated model — expected to move based on `@qa-eng` acceptance results against AC-002/AC-003. Build sequencing resolved (2026-08-06): frontend is complete (all 3 surfaces built against mock clients); backend/integration proceeds as a 3-phase vertical slice — `/chat` first (full pipeline), then `/inbox`, then `/ops` — see "MVP Build Sequencing". `knowledge_retriever`'s retrieval algorithm resolved (2026-08-06) via ADR-005: keyword/section-scored matching against `domain_config.json`, floor `0.20`, top `3` — no vector store. `domain_config.json` seeded with all 4 FR-013 scenario categories (see Assumptions). NFR-002 treated as a measured spike, not an assumption (2026-08-06): p95 ≤ 5s target, 10s hard ceiling, mandatory measurement gate between Phase 1 and Phase 2, and a pre-agreed fallback ladder (Haiku sentiment → skip composer on escalate → last-resort composer downgrade) — streaming explicitly ruled out as a fix (§7).

## Audit

- **Timestamp**: 2026-08-05
- **Persona**: `system-arch`
- **Action**: `create-sad --mvp`
- **Resolved runtime**: `crewai` (`AAMAD_TARGET_RUNTIME` env var, consistent with `aamad.config.yml`)
- **Inputs used**: `prd.md`, `system-description.md` (MRD N/A)
- **Timestamp**: 2026-08-05
- **Persona**: `system-arch`
- **Action**: `create-sad --mvp` (follow-up: LLM provider confirmed as Anthropic per stakeholder input; specific model remains an Open Question)
- **Timestamp**: 2026-08-05
- **Persona**: `system-arch`
- **Action**: `create-sad --mvp` (follow-up: ADR-002 confirmed final by stakeholder — `escalation_manager`/`interaction_logger` remain deterministic Flow logic, not agents)
- **Timestamp**: 2026-08-05
- **Persona**: `system-arch`
- **Action**: `create-sad --mvp` (follow-up: ADR-004 added — per-agent Claude model tier resolved: `claude-haiku-4-5` for `query_classifier`/`knowledge_retriever`/`pii_guard`, `claude-sonnet-5` for `sentiment_analyzer`/`response_composer`; no current agent uses Opus 5)
- **Timestamp**: 2026-08-06
- **Persona**: `system-arch`
- **Action**: `create-sad --mvp` (follow-up, reviewer feedback item 1: added "Typed Task Outputs (Pydantic contracts)" under §2 — named `output_pydantic` fields for every reasoning-Crew task and `pii_guard`'s task, so `escalation_gate` reads only typed fields; raised numeric-threshold values as a new Open Question, deliberately left unresolved pending separate decision)
- **Timestamp**: 2026-08-06
- **Persona**: `system-arch`
- **Action**: `create-sad --mvp` (follow-up, reviewer feedback item 2: pinned `escalation_gate` numeric thresholds — `confidence <= 0.70` OR `sentiment_score >= 0.75` OR `grounded == false` → escalate; pinned `sentiment_label` boundaries to match; resolved the Open Question raised by item 1)
- **Timestamp**: 2026-08-06
- **Persona**: `system-arch`
- **Action**: `create-sad --mvp` (follow-up, reviewer feedback item 3: added "MVP Build Sequencing" section — 3-phase vertical slice (`/chat` → `/inbox` → `/ops`) for `@backend-eng`/`@integration-eng`; noted `@frontend-eng` epic already complete against mock clients; updated Implementation Guidance list accordingly)
- **Timestamp**: 2026-08-06
- **Persona**: `system-arch`
- **Action**: `create-sad --mvp` (follow-up, reviewer feedback item 4: added ADR-005 — keyword/section-scored `knowledge_retriever` retrieval against `domain_config.json`, no vector store, floor 0.20/top 3; pinned `taxonomy`/`knowledge_base` entry shapes; seeded `backend/domain_config.json` with all 4 FR-013 scenario categories (12 KB entries total) and formalized `backend/domain_config.schema.json` to match, also fixing a pre-existing gap where `$schema` wasn't declared under `properties`)
- **Timestamp**: 2026-08-06
- **Persona**: `system-arch`
- **Action**: `create-sad --mvp` (follow-up, reviewer feedback item 5: rewrote §7 Performance & Scalability — pinned NFR-002 to p95 ≤ 5s / 10s hard ceiling, added a mandatory Phase 1→2 latency-spike gate and a 3-step fallback ladder (Haiku sentiment tier → reorder `escalation_gate` before `compose_response_task` on the escalate branch → last-resort composer downgrade), explicitly ruled out streaming as a fallback; cross-referenced from §1 Streaming, §2 `escalation_gate`, and MVP Build Sequencing)
