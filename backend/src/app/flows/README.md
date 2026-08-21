# flows/

CrewAI `Flow` orchestration (`*develop-be`, Phase 1).

- `escalation_gate.py` — pure-function escalation decision (ADR-002),
  directly unit-tested in `../../tests/unit/test_escalation_gate.py`.
- `inquiry_flow.py` — `InquiryFlow`, the top-level orchestrator for one
  inquiry (sad.md §1 ADR-001, §2). Implements the 6 steps: intake_normalize
  -> pii_redact -> run_reasoning_crew -> escalation_gate -> deliver_response
  -> log_interaction. Public entry point for Python/pytest callers:
  `run_inquiry(channel, raw_text, sender_id)`.

`EscalationResolutionFlow` and the Reviewer KB-write path are Phase 2/3 of
`project-context/1.define/sad.md`'s MVP Build Sequencing — **not** built
here. FastAPI route wiring (`POST /chat`) is `*implement-endpoint`'s scope,
not this directory's.
