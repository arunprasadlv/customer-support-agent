# Product Requirements Document — customer-support-agent

## Input Requirements

**Deep Research Report / MRD**: N/A — skipped. This is an internal/portfolio project demonstrating a domain-agnostic multi-agent support architecture (see `usecase.txt` "Selection Considerations"), not a funded commercial launch, so market-sizing research was not commissioned. See Assumptions.
**System Description**: `project-context/1.define/system-description.md`
**System Concept**: A CrewAI-orchestrated crew of specialized agents (classification/routing, knowledge retrieval, sentiment analysis, response generation, escalation) that resolves customer support inquiries received via chat or a simulated email inbox. Core agent logic is domain-agnostic; a swappable domain-configuration layer supplies the knowledge base, intent taxonomy, and prompts. The MVP pilot domain is **Hotel/Hospitality**.
**Selected Runtime**: crewai (from `aamad.config.yml`)

## 1. Executive Summary

### Problem Statement

- Generic single-agent chatbots and manual triage can't specialize across the distinct reasoning needed for reservation questions, billing/folio disputes, amenity requests, and complaint handling — this produces slow, inconsistent resolutions and no clear escalation path when a guest is frustrated.
- Industry benchmark figures cited in `usecase.txt` (58% resolution-time reduction, 84% first-call resolution, 92% CSAT, 45% lower operating cost, 30% automation savings, 50,000+ daily interactions at scale) describe the *market opportunity* for multi-agent CX systems generally. They are **not MVP targets** for this project — there is no live traffic to measure them against. See Assumptions.
- Target population for MVP: simulated hotel guests and hotel support/ops staff, exercised through the four in-scope scenario categories (reservations & booking, check-in/check-out & billing, room service & amenities, general complaints). Real market sizing is N/A — see Assumptions.

### Solution Overview

- A CrewAI crew — classifier/router, knowledge retrieval, sentiment analysis, response composer, escalation manager, plus a PII-redaction step and an interaction/review-queue logger — collaborates to resolve each inquiry end-to-end, across chat and a simulated email channel, under one shared pipeline.
- Differentiators: (1) the crew's core logic is domain-agnostic by construction — knowledge base, taxonomy, and prompts are supplied by an external domain configuration rather than hardcoded, so the same crew could later serve IT helpdesk or retail without rewriting agents; (2) PII-aware handling (redaction, encryption, audit logging) is built into the MVP pipeline rather than deferred.
- Expected outcome: a working, demonstrable proof of coordinated multi-agent architecture (delegation, shared context, conditional escalation, config-driven specialization) using Hotel/Hospitality as the reference vertical.

### Strategic Rationale

- Multi-agent decomposition fits this problem because classification, retrieval, sentiment scoring, and escalation policy are distinct reasoning tasks that benefit from separated responsibilities — and that same separation is what makes domain-swapping possible without rewriting core logic (FR-012).
- Business case is architectural/technical mastery, not funded-product ROI: build once, demonstrate reusability across verticals (per `usecase.txt` "Selection Considerations" — differentiation from single-agent chatbots).
- Market timing / competitive positioning: N/A — internal/portfolio project. See Assumptions.

## 2. Market Context & User Analysis

### Target Market / Users

- **Primary persona (MVP pilot)**: A hotel guest submitting a reservation, billing, amenity, or complaint inquiry via chat or email.
- **Secondary persona**: Hotel support/ops staff who receive simulated escalations and review interaction logs.
- **Reviewer persona** (stakeholder-confirmed): approves, edits, or rejects candidate KB entries generated from escalation resolutions (FR-014) — the sole gate through which the live KB can change.
- **Market segment size / growth**: N/A — not a market-entry project. See Assumptions.
- **Geographic focus**: N/A.

### User Needs Analysis

- **Pain points**: having to re-explain an issue across channels, no visibility into whether/when a human will step in, feeling unheard when frustrated, inconsistent answers.
- **User journey**: guest sends an inquiry (chat or email) → classified into a hotel intent category → grounded against the hotel domain knowledge base → sentiment scored to adjust tone/escalation likelihood → response delivered on the originating channel, or a simulated escalation is clearly flagged.
- **Adoption barriers / success factors**: not applicable in a market sense (no real users); for the MVP demo, success means the four in-scope hotel scenario categories are classified and answered correctly, and escalation triggers appropriately on unresolved or high-frustration cases.

### Competitive Landscape

- Skipped (MRD not commissioned). Directionally, `usecase.txt` frames this system's differentiation as moving beyond single-agent chatbots to a coordinated, specialized crew — treat as qualitative positioning only, not a sourced competitive analysis.

## 3. Technical Requirements & Architecture

### Runtime & Agent Specifications (CrewAI)

- **Collaboration pattern**: sequential/hierarchical CrewAI process per inquiry — classify → retrieve → score sentiment → compose response → escalation-decision gate — with a shared context object carrying the original inquiry, detected intent, retrieved KB snippets, and sentiment score across tasks.
- **Task orchestration**: one `crew.kickoff()` per inquiry (chat message or simulated email), regardless of originating channel (FR-009/FR-010 share the same pipeline as chat).
- Exact task/delegation wiring (hierarchical vs. sequential process, manager-agent use) is an implementation decision for `@system-arch` / `@backend-eng`, not fixed here.

### Core Agent Definitions

| Agent | Role | Goal | Tools (indicative) | Runtime notes |
|---|---|---|---|---|
| `query_classifier` | Support Query Classifier | Classify an inbound inquiry into a domain-configured intent/category | domain taxonomy lookup | Reads categories from domain config only — no hardcoded intents (FR-012) |
| `knowledge_retriever` | Knowledge Base Retrieval Specialist | Retrieve grounding content for the classified intent from the active domain's KB | KB search | KB path/content resolved from domain config (FR-012/FR-013) |
| `sentiment_analyzer` | Guest Sentiment Analyst | Score sentiment/frustration in the inbound message | sentiment scorer | Output feeds the escalation gate (FR-006, AC-002) |
| `response_composer` | Response Composer | Compose a tone-adjusted response from classification + retrieved knowledge + sentiment | — (LLM only) | Must not fabricate an answer when the KB has no match (AC-003) |
| `escalation_manager` | Escalation Manager | Decide and simulate handoff to a human when confidence is low or sentiment is highly negative | escalation flag | Simulated only for MVP — no real ticketing integration (FR-006) |
| `pii_guard` | PII Redaction Guard | Detect and redact/mask PII before logging or passing content to retrieval/LLM steps | PII detector | Applies pre-log and pre-retrieval (FR-011, NFR-004/006). Implemented as a **dedicated CrewAI agent** (stakeholder-confirmed), not a shared utility. |

**KB update approval is intentionally not an agent decision.** Per FR-014/NFR-008, a candidate KB entry (from `interaction_logger`) only reaches the live KB after explicit approval by the dedicated **Reviewer persona** via the UI — no agent has write access to the live KB. This keeps the human firmly in the loop and avoids automatic ingestion drift.
| `interaction_logger` | Interaction & Review-Queue Logger | Log every interaction; when an inquiry escalates, record the (simulated) human resolution and queue it as a candidate KB entry | logger | MVP-scoped interpretation of "self-improvement" (FR-007/FR-008) |

### Integration Requirements

- **Required APIs / external services**: none for MVP — chat UI is in-app, email is a simulated in-app inbox (FR-009/010), KB is mock/local domain data.
- **Database / storage**: lightweight local storage (file-based or embedded DB) for KB content, interaction logs, and the review queue. A real database/vector store is deferred (Out of Scope).
- **Domain configuration format**: JSON, schema-validated (stakeholder-confirmed) — satisfies FR-012's requirement that KB content, taxonomy, and prompts live outside core agent code.
- **Authentication & security**: no user auth for MVP (Out of Scope); PII redaction/encryption still required per NFR-004/NFR-006 regardless.
- **Performance / scalability targets**: single-query end-to-end response within a few seconds (NFR-002); no enterprise-scale throughput target for MVP.

### Infrastructure Specifications

- **Hosting**: local/dev execution for MVP; no cloud target selected — deferred to `@devops-eng` (Open Question).
- **Compute/memory**: standard development-machine scale is sufficient for MVP.
- **Network/security architecture**: N/A for MVP — no real external integrations.
- **Monitoring/logging**: interaction log (NFR-003) and PII-handling/redaction log (NFR-006).

## 4. Functional Requirements

### Core Features (P0)

All map to `system-description.md` "Must" priority FRs:

- **Chat inquiry intake & classification** — guest describes an issue in chat; system classifies it against the hotel domain taxonomy. *(FR-001, FR-002, FR-012/013 → AC-001, AC-008)*
- **Knowledge-grounded response** — response is generated from retrieved hotel KB content, never fabricated when no match exists. *(FR-003, FR-005 → AC-001, AC-003)*
- **Sentiment-aware handling** — detected sentiment measurably changes tone or escalation likelihood. *(FR-004 → AC-002)*
- **Simulated escalation** — low-confidence or highly negative-sentiment cases trigger a clearly flagged simulated human handoff. *(FR-006 → AC-003)*
- **Simulated email channel** — inquiries received and answered via a mock in-app email inbox through the same pipeline as chat. *(FR-009, FR-010 → AC-006)*
- **PII redaction** — PII in chat/email content is detected and redacted/masked before logging or LLM/retrieval use. *(FR-011 → AC-007)*
- **Domain-configurable hotel content** — KB, taxonomy, and prompts load from an external Hotel/Hospitality domain configuration, not hardcoded. *(FR-012, FR-013 → AC-008, AC-009)*
- **Human-curated KB feedback loop** — escalation resolutions are recorded and queued as candidate KB entries; staff must explicitly approve (optionally editing) or reject each one before it reaches the live KB. *(FR-008, FR-014, NFR-008 → AC-010, AC-011)*

### Enhanced Features (P1)

- Interaction logging of every processed inquiry (query, classification, sentiment, outcome). *(FR-007, "Should")*

### Future Features (P2)

Explicit future work (mirrors `system-description.md` §8 Out of Scope):

- Real helpdesk/CRM integration (Zendesk, Freshdesk, ServiceNow, Salesforce, etc.)
- Real email server integration (SMTP/IMAP, deliverability, spam/abuse handling)
- Live, continuously ingested knowledge base
- Fully autonomous (unreviewed) self-learning / dynamic skill acquisition — MVP requires explicit staff approval (FR-014) for every KB update
- Voice and social-media channels
- Enterprise-scale load handling and formal SLA guarantees
- Authentication, multi-tenancy, and formal regulatory certification (GDPR/HIPAA audit, DPA agreements)
- Fully built-out domain configurations for other verticals (IT, retail, etc.)
- Multi-domain simultaneous operation

## 5. Non-Functional Requirements

Mirrors `system-description.md` §4 directly:

- **Performance**: single-query resolution within a few seconds for MVP; no enterprise-scale throughput/uptime target. *(NFR-002)*
- **Security & Compliance**: PII in chat/email content and logs must be minimized, encrypted at rest, and redacted/masked wherever practical, per general data-protection best practice — no specific named regulation targeted for MVP. PII-handling actions must themselves be logged for auditability. *(NFR-004, NFR-006)*
- **Scalability & Reliability**: each agent role is a distinct CrewAI agent so roles/tools can be added later without rewriting existing ones; domain swapping requires only new configuration, not core code changes. *(NFR-005, NFR-007)*
- **Data Integrity**: the live knowledge base is modified only through the staff-approval step — no code path allows a candidate entry to reach the KB without explicit human approval. *(NFR-008)*
- **Usability**: chat UI usable by a non-technical demo audience without instructions. *(NFR-001)*
- **Observability**: interaction log must be inspectable for debugging/demo purposes. *(NFR-003)*

## 6. User Experience Design

### Interface Requirements

- Single-page web chat widget plus a simple simulated "inbox" view demonstrating the email channel. Web-only for MVP; mobile-specific design is out of scope.
- Accessibility: basic usability (readable contrast, labeled inputs) targeted; formal WCAG certification is not an MVP requirement — flagged as future work if needed.

### Agent Interaction Design

- Guest-facing: responses read as a normal chat/email reply grounded in hotel KB content; when escalation triggers, the UI must clearly state a human is being simulated as looped in (never silently drop or fabricate an answer — AC-003).
- Ops-facing: an internal log/review view exposes classification, sentiment score, and PII-redaction outcome per interaction, supporting the framework's "context-first, explainable" principle (traceability of every response back to its inputs). This same ops view hosts the **KB review queue**: candidate entries generated from escalation resolutions, with approve/edit/reject actions restricted to the Reviewer persona (FR-014).

## 7. Success Metrics & KPIs

### Business / Operational Metrics

- Qualitative for MVP: correct classification, grounded response, and appropriate escalation behavior demonstrated across all four in-scope hotel scenario categories (reservations & booking, check-in/check-out & billing, room service & amenities, general complaints & feedback). The `usecase.txt` industry figures are aspirational context, not MVP KPIs (see Assumptions).

### Technical Metrics

- Response latency in line with NFR-002 (a few seconds per query).
- Pass rate against acceptance criteria AC-001 through AC-009.
- Classification/escalation correctness across a hand-built test set covering the four in-scope hotel scenarios.

### User Experience Metrics

- Qualitative usability check against NFR-001 (a non-technical person can use the chat UI without instructions). No quantitative CSAT survey for MVP — no real user base.

## 8. Implementation Strategy

### Development Phases

- **Phase 1 (Define)** — system description (done) → this PRD (this document) → SAD/SFS via `@system-arch`.
- **Phase 2 (Build)** — `@project-mgr` sets up environment/structure/dependencies → `@backend-eng` implements the CrewAI crew and API → `@frontend-eng` builds the chat UI and simulated email inbox → `@integration-eng` wires frontend to backend → `@qa-eng` validates against AC-001–009.
- **Phase 3 (Deliver)** — `@security-eng` assessment before Deliver (required per `aamad.config.yml` `security.require_security_assessment: true`, and materially relevant given FR-011/NFR-004/006 PII handling) → `@devops-eng` packages deploy config, runbook, and user documentation.

### Resource Requirements

- Single-developer, AAMAD-agent-assisted build. **5-week project timeline** (stakeholder-confirmed). No dedicated infrastructure budget identified — remains an Open Question.

### Risk Mitigation

- **Risk**: domain-agnostic architecture adds complexity versus a hotel-only hardcoded build. *Mitigation*: enforce the config/core-code boundary early via AC-009 architectural review; keep the domain-config schema minimal (deferred to `@system-arch`).
- **Risk**: PII handling is "best practice" only, without a named regulation. *Mitigation*: document this explicitly as non-certified; flag before any real deployment (open question already recorded).
- **Risk**: scope creep — email, PII, and domain-agnosticism were all layered onto the original 4-agent concept in one elicitation session. *Mitigation*: the Out of Scope / Future Work list (§4 P2) keeps real integrations, live KB, other-domain content, and voice/social explicitly out of MVP.

## 9. Launch & Go-to-Market Strategy

N/A — internal/portfolio demonstration project, not a commercial launch. See Assumptions (MRD skip rationale applies here too).

## Quality Assurance Checklist

- [x] Requirements traceable to `system-description.md` FR/NFR/AC IDs or recorded Assumptions
- [x] Technical specifications feasible with the selected runtime adapter (CrewAI)
- [x] Success metrics aligned with stated objectives (qualitative MVP demo, not live-traffic KPIs)
- [x] MVP vs. Future Work boundaries explicit (§4 P0/P1/P2)
- [x] Market sections marked N/A with rationale (MRD intentionally skipped)

## Sources

- `project-context/1.define/system-description.md`
- `project-context/usecase.txt`
- `aamad.config.yml` (`runtime.target: crewai`)

## Assumptions

- MRD was skipped because this is an internal/portfolio project (per `usecase.txt` "Selection Considerations": a technical-mastery exercise in coordinated multi-agent systems), not a funded product launch requiring market sizing — per the `product-mgr` persona's own guidance to skip MRD for internal/personal tools when appropriate.
- The `usecase.txt` industry benchmark figures (resolution-time reduction, CSAT, cost savings, daily interaction volume) are treated as market-opportunity framing, not MVP acceptance targets, consistent with `system-description.md` §6 Assumptions.
- Single language/locale (English) assumed for the hotel domain content, since none was specified.
- Whether `pii_guard` is implemented as a dedicated CrewAI agent or a shared pre/post-processing utility is left open — either satisfies FR-011, and the choice is an implementation detail for `@system-arch`/`@backend-eng`.

## Open Questions

- What is the actual budget for this project? (Timeline confirmed: 5 weeks.)
- Which specific regulation, if any, must PII handling ultimately comply with (GDPR, CCPA/CPRA, HIPAA, other)?
- **Under active discussion**: what should the *full* vision for "self-improvement" include beyond the MVP-scoped human-curated loop (escalation resolution → review queue → Reviewer approve/reject → KB update, FR-008/FR-014)? MVP behavior is settled; see the roadmap discussion with the stakeholder.
- Mailbox/provider and sending domain for a real (post-MVP) email channel: confirmed **TBD**, to be decided if/when real email integration is built.
- Hosting/infrastructure target for MVP is undecided — for `@devops-eng` to propose during Phase 3 planning.

**Resolved this round**: user-facing name is `customer-support-agent` (not `usecase.txt`'s "Multi-Agent Customer Support Crew"); Reviewer persona approves KB entries; domain config format is JSON, schema-validated; PII redaction is a dedicated agent (`pii_guard`); next vertical after hotel deferred, no second domain built for MVP.

## Audit

- **Timestamp**: 2026-08-05
- **Persona**: `product-mgr`
- **Action**: `create-prd`
- **Resolved runtime**: `crewai` (from `aamad.config.yml`; no `AAMAD_TARGET_RUNTIME` env override)
- **Inputs used**: `system-description.md` only (MRD intentionally skipped — see Assumptions)
- **Timestamp**: 2026-08-05
- **Persona**: `product-mgr`
- **Action**: `create-prd` (follow-up: brought the human-in-the-loop KB feedback loop into MVP scope — FR-008 upgraded to Must, new FR-014/NFR-008/AC-010/AC-011 — mirroring the same update in `system-description.md`)
- **Timestamp**: 2026-08-05
- **Persona**: `product-mgr`
- **Action**: `create-prd` (follow-up: resolved 6 of 7 outstanding open questions per stakeholder input — see updated Open Questions section. Full "self-improvement" vision intentionally left open pending stakeholder brainstorm.)
