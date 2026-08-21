# flows/

CrewAI `Flow` orchestration (`*develop-be`, Phase 1).

- `escalation_gate.py` — pure-function escalation decision (ADR-002),
  directly unit-tested in `../../tests/unit/test_escalation_gate.py`.
- `inquiry_flow.py` — `InquiryFlow`, the top-level orchestrator for one
  inquiry (sad.md §1 ADR-001, §2). Implements the 6 steps: intake_normalize
  -> pii_redact -> run_reasoning_crew -> escalation_gate -> deliver_response
  -> log_interaction. Public entry point for Python/pytest callers:
  `run_inquiry(channel, raw_text, sender_id, timeout_seconds=10) -> dict` —
  returns `{"reply", "escalated", "inquiry_id", ...}`. Wired to the frontend
  via `POST /chat` (main.py, `*implement-endpoint`); `GET /interactions`
  (also main.py) reads back the log rows this Flow writes — manual curl
  examples for both are in `project-context/2.build/setup.md` SS5.

`EscalationResolutionFlow` and the Reviewer KB-write path are Phase 2/3 of
`project-context/1.define/sad.md`'s MVP Build Sequencing — **not** built
here. FastAPI route wiring (`POST /chat`) is `*implement-endpoint`'s scope,
not this directory's.
