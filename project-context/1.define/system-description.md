# AAMAD System Description

## Input Requirements

**Working title**: customer-support-agent  
**Author / stakeholder**: arun venkatram (arunprasad.lv@gmail.com)  
**Selected Runtime**: crewai (from `aamad.config.yml` → `runtime.target`; no `AAMAD_TARGET_RUNTIME` override set)  
**Domain**: Architecture is domain-agnostic by design (portable to IT, retail, etc.); **Hotel/Hospitality** is the concrete MVP pilot domain

## System Description

### 1. Intent and Problem

- **Problem statement**: Traditional single-agent/simple chatbot helpdesk systems can't handle enterprise-scale support complexity — they lack specialization, contextual handoffs, and adaptive escalation, which slows resolution and hurts customer satisfaction. This system replaces that with a coordinated crew of specialized AI agents (routing, knowledge retrieval, sentiment analysis, escalation) that collaborate to resolve inquiries. The crew's core logic must be **domain-agnostic**: the same architecture should serve IT helpdesk, hotel/hospitality, retail, or other verticals by swapping domain configuration/content, not by rewriting agents.
- **Primary users / operators**: For the MVP pilot domain (Hotel/Hospitality) — hotel guests submitting inquiries and complaints through a chat interface or email; internal hotel support/ops staff who receive simulated escalations and review interaction logs; a dedicated **Reviewer** persona who approves, edits, or rejects candidate KB entries generated from escalation resolutions (FR-014).
- **Success definition (MVP)**: A working chat UI and a simulated email inbox, both backed by a CrewAI-orchestrated crew that classifies an inquiry, retrieves a grounded answer from a mock **hotel-domain** knowledge base, factors in detected sentiment, applies basic PII protection, and either returns a resolution (chat reply or simulated email reply) or visibly triggers a simulated human escalation — demonstrable end-to-end, with domain content (KB, intents, prompts) kept out of core agent code so another vertical could be plugged in later.

### 2. Domain Context

- **Cross-domain vocabulary**: inquiry/ticket, intent/category, knowledge base article, sentiment score, escalation, resolution, first-contact resolution (FCR), handoff, domain configuration (the swappable KB/taxonomy/prompt set that specializes the crew to a vertical).
- **MVP pilot domain vocabulary (Hotel/Hospitality)**: reservation/booking, check-in/check-out, folio/bill, deposit, refund, no-show, room service, housekeeping, amenities (spa, pool, wifi), guest complaint, upgrade, loyalty program.
- **Existing systems/data sources**: None real for MVP. Knowledge base is mock/sample hotel-domain data created for this project; no live external source. Other verticals (IT, retail, etc.) are not built out for MVP — the domain layer must simply be structured so they could be added later without touching core agent code.
- **Regulatory/organizational constraints**: System must handle PII according to general data-protection best practices (minimization, encryption, redaction in logs). No specific named regulation (GDPR/CCPA/HIPAA) confirmed yet — see Open Questions.

### 3. Functional Requirements

| ID | Description | Priority |
|----|-------------|----------|
| FR-001 | Accept a free-text customer inquiry via a chat interface. | Must |
| FR-002 | Classify and route the inquiry to the appropriate handling path (query classification/routing agent). | Must |
| FR-003 | Retrieve relevant content from a knowledge base (mock/sample KB for MVP) to ground the response (knowledge retrieval agent). | Must |
| FR-004 | Analyze the sentiment of the customer's message and factor it into response tone and escalation likelihood (sentiment analysis agent). | Must |
| FR-005 | Generate a coherent response combining classification, retrieved knowledge, and sentiment context. | Must |
| FR-006 | When confidence is low or sentiment indicates high frustration, trigger a simulated escalation to a human agent, visibly flagged in the UI (escalation management agent). | Must |
| FR-007 | Log each interaction (query, classification, retrieved sources, sentiment, resolution/escalation outcome). | Should |
| FR-008 | When an inquiry is escalated, record the simulated human agent's resolution response alongside the original query and add it to a review queue as a candidate knowledge-base entry — MVP-scoped interpretation of "self-improvement"; see Open Questions for the full vision. | Must |
| FR-014 | A dedicated Reviewer persona can review a candidate KB entry in the queue and approve (optionally editing it first) or reject it; only approved entries are added to the active knowledge base and become available for future retrieval. Rejected entries are discarded without modifying the KB. | Must |
| FR-009 | Receive customer inquiries/complaints via a simulated email inbox (mock, in-app — no real SMTP/IMAP server for MVP). | Must |
| FR-010 | Respond to email inquiries via a simulated outbound email reply, routed through the same classification/retrieval/sentiment/escalation pipeline as chat. | Must |
| FR-011 | Detect and redact/mask PII (e.g., names, emails, phone numbers, account numbers) in stored logs and any content passed to the knowledge-retrieval or LLM components. | Must |
| FR-012 | Knowledge base content, intent/category taxonomy, and agent prompts must be defined via an external, swappable domain configuration (config/data, not hardcoded into core agent logic), so a new vertical (IT, retail, etc.) can be added by supplying new configuration only. | Must |
| FR-013 | MVP ships with a Hotel/Hospitality domain configuration as the reference implementation, covering: reservations & booking changes, check-in/check-out & billing/folio issues, room service & amenities requests, and general complaints & feedback. | Must |

### 4. Non-Functional Requirements

| ID | Description |
|----|-------------|
| NFR-001 | Usability: chat UI must be usable by a non-technical demo audience without instructions. |
| NFR-002 | Performance: a single query should resolve end-to-end within a few seconds for MVP; no enterprise-scale SLA required yet. |
| NFR-003 | Observability: the interaction log (FR-007) must be inspectable for debugging and demos. |
| NFR-004 | Security/Privacy: PII in inbound messages (chat and email) and stored logs must be minimized, encrypted at rest, and redacted/masked wherever practical, per general data-protection best practice. |
| NFR-005 | Extensibility: each agent role is a distinct CrewAI agent so new roles/tools can be added post-MVP without rewriting existing ones. |
| NFR-006 | Auditability: PII handling and redaction actions must be logged so compliance behavior can be reviewed, even though no specific regulatory certification is targeted for MVP. |
| NFR-007 | Domain portability: swapping the active domain (e.g., hotel → IT helpdesk) must require only new configuration/data, not changes to core agent/orchestration code. Architecturally required; not exercised with a second built domain in MVP. |
| NFR-008 | KB update integrity: the live knowledge base is only ever modified through the staff-approval step (FR-014); no path exists for a candidate entry to reach the KB without explicit human approval. |

### 5. Constraints

- **Technology**: Python; CrewAI runtime (per `aamad.config.yml`); domain configuration expressed as JSON, schema-validated (stakeholder-confirmed).
- **Budget / timeline**: 5-week project timeline (stakeholder-confirmed). Budget not specified — remains an Open Question.
- **Integration**: No real helpdesk/CRM integration for MVP (simulated escalation only, per stakeholder decision); knowledge base is mock/sample data, not a live external source.
- **Channels**: Chat (real-time UI) and email (simulated inbox, in-app) for MVP; no real SMTP/IMAP server, no voice or social channels.
- **Domain scope**: Architecture must be domain-agnostic/config-driven; MVP content and demo are Hotel/Hospitality only — other verticals (IT, retail, etc.) are not built out for MVP.

### 6. Assumptions

- Two channels for MVP: chat and email, both real-time UI-simulated (no real mail server); voice/social remain out of scope.
- "Self-improvement / learning new skills" is scoped for MVP as a human-curated feedback loop: escalation resolutions are recorded and queued (FR-008), then require explicit staff approval before updating the KB (FR-014, NFR-008) — not autonomous unsupervised retraining. The full adaptive-learning vision is deferred — see Open Questions.
- "PII data for regulatory compliance" is scoped for MVP as general best-practice PII protection (minimization, encryption, redaction) rather than certification against a named regulation, since no specific regulation was confirmed.
- Hotel/Hospitality is the single MVP pilot domain. Domain-agnostic extensibility is an architectural requirement (FR-012, NFR-007) but will not be demonstrated with a second built-out domain in MVP, per stakeholder decision.
- The business-case figures in `usecase.txt` (58% resolution-time reduction, 92% CSAT, 50,000+ daily interactions, etc.) are market/ROI framing for the use case pitch, not MVP acceptance targets.

### 7. Acceptance Criteria

- **AC-001**: Given a customer submits a question in the chat UI, when the crew processes it, then the response includes an answer grounded in the mock knowledge base.
- **AC-002**: Given a message with clearly negative/frustrated sentiment, when processed, then the sentiment analysis output measurably affects the response path (e.g., raises escalation likelihood or softens tone).
- **AC-003**: Given a query the knowledge base cannot answer, when processed, then the system simulates an escalation and clearly indicates this in the UI rather than fabricating an answer.
- **AC-004**: Given any processed interaction, when it completes, then a log entry exists capturing query, classification, sentiment, and outcome.
- **AC-005**: Given the crew architecture, when a new agent role or tool is added, then it integrates without rewriting existing agents (reviewed structurally by `@system-arch`, not an automated test).
- **AC-006**: Given a customer submits an inquiry through the simulated email inbox, when the crew processes it, then a reply is generated and delivered back through the simulated email channel via the same pipeline used for chat.
- **AC-007**: Given an inbound message (chat or email) contains PII (e.g., an email address, phone number, or account number), when it is logged or passed to the knowledge-retrieval/LLM components, then the PII is redacted or masked in accordance with NFR-004.
- **AC-008**: Given the Hotel/Hospitality domain configuration (KB, intents, prompts), when the system starts, then classification, retrieval, and response generation operate using hotel-specific categories and content rather than hardcoded generic ones.
- **AC-009**: Given the domain configuration layer, when `@system-arch`/`@security-eng` review core agent code, then no hotel-specific (or any domain-specific) strings/logic are found hardcoded outside the domain configuration layer (architectural review, not an automated test for MVP).
- **AC-010**: Given an inquiry is escalated to a simulated human handoff and a resolution is entered, when the interaction completes, then the resolution is added to the review queue as a candidate KB entry linked to the original query.
- **AC-011**: Given a candidate KB entry in the review queue, when staff approves it (with or without edits), then it becomes part of the active knowledge base and is retrievable for future queries; when staff rejects it, then it is discarded and the KB is unchanged.

### 8. Out of Scope / Future Work

- Real helpdesk/CRM integration (Zendesk, Freshdesk, ServiceNow, Salesforce, etc.)
- Real email server integration (SMTP/IMAP, deliverability, spam/abuse handling) — email is simulated for MVP
- Live, continuously ingested knowledge base
- Fully autonomous (unreviewed) self-learning / dynamic skill acquisition — MVP requires explicit staff approval (FR-014) for every KB update, no automatic ingestion
- Voice and social-media channels
- Enterprise-scale load handling (50,000+ daily interactions) and formal SLA guarantees
- Authentication, multi-tenancy, and formal regulatory certification (e.g., GDPR/HIPAA audit, DPA agreements) — MVP applies general best practice only
- Fully built-out domain configurations for other verticals (IT, retail, etc.) — the architecture must support them, but only Hotel/Hospitality ships with real content for MVP
- Multi-domain simultaneous operation — one active domain per deployment for MVP

## Sources

- `project-context/usecase.txt` (use case / business-case brief)
- Stakeholder responses during `*elicit-requirements` session (2026-08-04)
- `aamad.config.yml` (`runtime.target: crewai`)

## Assumptions

- Stakeholder identity inferred from local git config (`arun venkatram`, `arunprasad.lv@gmail.com`) — confirm if incorrect.
- Working title set to `customer-support-agent` (matches repo name) per stakeholder choice over the use case doc's own name, "Multi-Agent Customer Support Crew". Confirmed by stakeholder as the user-facing name too — `usecase.txt`'s naming is business-case framing only, not used in-product.

## Open Questions

- What is the actual budget for this project? (Timeline confirmed: 5 weeks.)
- Which specific regulation, if any, must PII handling ultimately comply with (GDPR, CCPA/CPRA, HIPAA, other)? Stakeholder deferred this for MVP ("general best practice / undecided") — needs an answer before any production/certification work.
- **Under active discussion**: what should the *full* vision for "self-improvement" include beyond the MVP-scoped human-curated loop (FR-008/FR-014)? MVP behavior is settled; the longer-term roadmap is being brainstormed with the stakeholder.
- Mailbox/provider and sending domain for a real (post-MVP) email channel: stakeholder has confirmed this is **TBD**, to be decided if/when real email integration is built.
- Which vertical(s) should be prioritized after hotel: stakeholder has confirmed the focus stays on Hotel/Hospitality only for now; next vertical to be discussed later.

## Audit

- **Timestamp**: 2026-08-04
- **Persona**: `product-mgr`
- **Action**: `elicit-requirements`
- **Resolved runtime**: `crewai` (from `aamad.config.yml`; no `AAMAD_TARGET_RUNTIME` env override)
- **Timestamp**: 2026-08-04
- **Persona**: `product-mgr`
- **Action**: `elicit-requirements` (follow-up: added PII/regulatory-compliance handling and simulated email channel to MVP scope per stakeholder input)
- **Timestamp**: 2026-08-04
- **Persona**: `product-mgr`
- **Action**: `elicit-requirements` (follow-up: added domain-agnostic/config-driven architecture requirement; set Hotel/Hospitality as the MVP pilot domain, scoped to reservations & booking, check-in/check-out & billing, room service & amenities, and general complaints & feedback; deferred a second domain stub per stakeholder decision)
- **Timestamp**: 2026-08-05
- **Persona**: `product-mgr`
- **Action**: `elicit-requirements` (follow-up: brought the human-in-the-loop KB feedback loop into MVP scope — recording escalation resolutions (FR-008, upgraded to Must) and requiring staff approval before any KB update (new FR-014, NFR-008, AC-010, AC-011), per stakeholder decision)
- **Timestamp**: 2026-08-05
- **Persona**: `product-mgr`
- **Action**: `elicit-requirements` (follow-up: resolved 6 of 7 outstanding open questions — 5-week timeline confirmed; dedicated Reviewer persona approves KB entries (FR-014 updated); user-facing name confirmed as `customer-support-agent`; domain config format set to JSON, schema-validated; hotel remains sole domain focus; email mailbox/domain explicitly deferred as TBD. Full "self-improvement" vision left open pending stakeholder brainstorm — see `prd.md` for discussion.)
