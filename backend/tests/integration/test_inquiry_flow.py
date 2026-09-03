"""Integration tests for app.flows.inquiry_flow.InquiryFlow / run_inquiry.

Three tiers, per sad.md §9 ("Integration: full InquiryFlow run per hotel
scenario category ... Runtime-specific checks: reasoning-Crew task outputs
schema-checked at each context-chain step"):

1. Fail-closed pii_guard behavior and the max_execution_time(10s) hard
   ceiling — deterministic, monkeypatched, no LLM/network required.
2. Full end-to-end InquiryFlow.kickoff() across the four FR-013 scenario
   categories — requires a live ANTHROPIC_API_KEY; skipped otherwise (this
   run's environment has no key available, see backend.md Open
   Questions).
3. ADR-002 Addendum (2026-09-02) regression: the real dispute-threat
   message from the 2026-09-02 manual dashboard testing session, run
   through the full `InquiryFlow` (with the reasoning Crew/pii_guard
   monkeypatched to the exact confidence/sentiment/grounded values
   actually observed that day), proving the false negative is fixed.
"""

from __future__ import annotations

import os
import time
from types import SimpleNamespace

import pytest

from app.flows.inquiry_flow import InquiryFlow, PiiGuardFailure, run_inquiry
from app.persistence.interaction_log import list_interactions
from app.schemas.task_outputs import (
    ClassificationResult,
    ComposedResponse,
    KBRetrievalResult,
    RedactionResult,
    SentimentResult,
)

pytestmark = pytest.mark.integration

_HAS_ANTHROPIC_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))


def test_pii_redact_is_fail_closed_on_pii_guard_failure(monkeypatch, tmp_path) -> None:
    """sad.md §2 Error handling: "on pii_guard failure, the Flow halts and
    logs a Diagnostic rather than passing unredacted text forward"."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))

    def _boom(raw_text: str):
        raise RuntimeError("simulated pii_guard crew failure")

    monkeypatch.setattr("app.flows.inquiry_flow.kickoff_pii_guard", _boom)

    flow = InquiryFlow()
    flow.state["channel"] = "chat"
    flow.state["raw_text"] = "call me at 415-555-0100"
    flow.state["sender_id"] = "guest-1"
    intake = flow.intake_normalize()

    with pytest.raises(PiiGuardFailure):
        flow.pii_redact(intake)

    # A Diagnostic record was persisted, and it never contains the raw text.
    rows = list_interactions(db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["outcome"] == "diagnostic_halt"
    assert "415-555-0100" not in rows[0]["query_text"]


def test_pii_redact_diagnostic_never_leaks_raw_text_on_echoing_exception(
    monkeypatch, tmp_path
) -> None:
    """security.md HIGH-1 (2026-09-02): the ORIGINAL `test_pii_redact_is_
    fail_closed_on_pii_guard_failure` above only proves `query_text` is
    scrubbed on a pii_guard failure — it uses a synthetic
    RuntimeError("simulated pii_guard crew failure") that never echoes any
    guest text, so it could not catch a real bug where the `diagnostic`
    column/`self.state["diagnostic"]` persisted `str(exc)` verbatim
    (confirmed present before this fix: `pii_redact`'s except-block did
    `self.state["diagnostic"] = f"pii_guard failure: {exc}"` and passed
    `str(exc)` straight into `_log_diagnostic_halt`, with no redaction at
    all).

    This test simulates the plausible real-world failure mode instead: an
    Anthropic/CrewAI API client error that echoes part of the raw request
    text back in its own error message. `raw_text` deliberately mixes a
    PII-*shaped* span (a phone number, which a naive "just run
    detect_pii/_redact over str(exc)" fix would mask) with ordinary free
    text (which detect_pii's deterministic email/phone/account/name
    patterns would NOT mask) — proving the fix does not merely redact
    str(exc), it never persists exception text at all. Would have failed
    before the fix: the phone number and the free-text fragment both
    appeared verbatim in `self.state["diagnostic"]` and the persisted
    `interaction_log.diagnostic` column.
    """
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))

    raw_text = "call me at 415-555-0187 about my broken lamp in room 214"

    def _boom(text: str):
        # Simulates an API client error that echoes the request text back.
        raise RuntimeError(f"API rejected request: {text}")

    monkeypatch.setattr("app.flows.inquiry_flow.kickoff_pii_guard", _boom)

    flow = InquiryFlow()
    flow.state["channel"] = "chat"
    flow.state["raw_text"] = raw_text
    flow.state["sender_id"] = "guest-1"
    intake = flow.intake_normalize()

    with pytest.raises(PiiGuardFailure):
        flow.pii_redact(intake)

    # Neither the PII-shaped span nor the ordinary free-text fragment may
    # appear in the in-memory diagnostic state...
    assert "415-555-0187" not in flow.state["diagnostic"]
    assert "broken lamp in room 214" not in flow.state["diagnostic"]

    # ...or in the persisted interaction_log.diagnostic column.
    rows = list_interactions(db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["outcome"] == "diagnostic_halt"
    assert rows[0]["diagnostic"] is not None
    assert "415-555-0187" not in rows[0]["diagnostic"]
    assert "broken lamp in room 214" not in rows[0]["diagnostic"]


def test_run_inquiry_degrades_to_escalate_on_timeout(monkeypatch, tmp_path) -> None:
    """sad.md §7: Flow-level max_execution_time hard ceiling — "a stuck or
    abnormally slow run degrades automatically to the escalate branch
    rather than hanging indefinitely"."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))

    def _slow_kickoff(self, inputs=None, **kwargs):  # noqa: ANN001
        time.sleep(5)
        return {"escalated": False, "reply": "should never get here"}

    monkeypatch.setattr(InquiryFlow, "kickoff", _slow_kickoff)

    result = run_inquiry(
        channel="chat", raw_text="hello", sender_id="guest-1", timeout_seconds=1
    )

    assert result["escalated"] is True
    assert "reason" in result and "max_execution_time_exceeded" in result["reason"]

    rows = list_interactions(db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["outcome"] == "escalated"
    assert "max_execution_time" in rows[0]["diagnostic"]


@pytest.mark.skipif(
    not _HAS_ANTHROPIC_KEY,
    reason="Full InquiryFlow.kickoff() requires a live ANTHROPIC_API_KEY "
    "(not available in this environment) — see backend.md Open Questions.",
)
@pytest.mark.parametrize(
    "raw_text",
    [
        "Hi, I'd like to check availability for a room next weekend.",
        "What time is check-in and check-out?",
        "Can I get extra towels sent to my room?",
        "The room was dirty when I checked in and I'm very unhappy about it.",
    ],
)
def test_inquiry_flow_end_to_end_per_scenario_category(
    raw_text: str, monkeypatch, tmp_path
) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))

    result = run_inquiry(channel="chat", raw_text=raw_text, sender_id="guest-1")

    assert "escalated" in result
    assert "reply" in result
    assert isinstance(result["reply"], str) and result["reply"]

    # Filter to the row for *this specific* inquiry (matched on the
    # `inquiry_id` run_inquiry() now returns) rather than asserting the
    # whole db has exactly one row. Reason: when run_inquiry() legitimately
    # hits its 10s max_execution_time ceiling (sad.md §7) against a real
    # end-to-end call that takes longer, the abandoned background flow
    # thread cannot be killed (Python/stdlib limitation, documented in
    # inquiry_flow.py/backend.md) and keeps running after this function
    # returns. In a live, back-to-back parametrized run, a *different,
    # still-running* prior test case's straggler thread can call
    # record_interaction() while this test's monkeypatched
    # INTERACTION_LOG_DB_PATH is active, landing an unrelated row (a
    # different inquiry_id, from a different scenario or even the same
    # placeholder text on a repeated timeout) in this test's db.
    # record_interaction()'s `INSERT OR IGNORE` (see
    # persistence/interaction_log.py) already guarantees at most one row
    # *per inquiry id*; filtering on `inquiry_id` here asserts that exact
    # per-inquiry guarantee without being sensitive to an unrelated
    # scenario's leftover row.
    assert "inquiry_id" in result
    rows = list_interactions(db_path=db_path)
    matching = [r for r in rows if r["id"] == result["inquiry_id"]]
    assert len(matching) == 1
    assert matching[0]["outcome"] in ("escalated", "responded")


# --- ADR-002 Addendum (2026-09-02) regression: real dispute-threat message ---

_REAL_DISPUTE_MESSAGE = (
    "I am not looking to reschedule. As I wasnt given cancellation policy "
    "I would not want me to be charged like I said - I will dispute that "
    "charge"
)


def _fake_task_with_pydantic(pydantic_obj: object) -> SimpleNamespace:
    return SimpleNamespace(output=SimpleNamespace(pydantic=pydantic_obj))


def test_dispute_message_now_escalates_end_to_end_reproducing_2026_09_02_false_negative(
    monkeypatch, tmp_path
) -> None:
    """Reproduces the exact 2026-09-02 manual dashboard testing false
    negative (sad.md ADR-002 Addendum "Trigger"): the guest message "I will
    dispute that charge" was NOT escalated even though the message text
    itself is a clear dispute/chargeback threat, because all three
    pre-addendum conditions independently missed it:
        confidence = 0.92        (well above the 0.70 escalate line)
        sentiment_score = 0.70   (below the 0.75 escalate line)
        grounded = True          (a KB entry matched)

    With the ADR-002 Addendum's 4th condition (`contains_dispute_language`
    over `redaction.clean_text`) now wired into `InquiryFlow.
    escalation_gate()`, the exact same confidence/sentiment/grounded
    values must now escalate, with "dispute_language_detected" in the
    escalation reason list.
    """
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))

    monkeypatch.setattr(
        "app.flows.inquiry_flow.kickoff_pii_guard",
        lambda raw_text: _fake_task_with_pydantic(
            RedactionResult(clean_text=_REAL_DISPUTE_MESSAGE, redaction_actions=[])
        ),
    )

    def _fake_kickoff_reasoning_crew(clean_text, domain_config):  # noqa: ANN001
        return {
            "classify_task": _fake_task_with_pydantic(
                ClassificationResult(intent="checkin_checkout_billing", confidence=0.92)
            ),
            "retrieve_knowledge_task": _fake_task_with_pydantic(
                KBRetrievalResult(retrieved_snippets=[], match_found=True)
            ),
            "analyze_sentiment_task": _fake_task_with_pydantic(
                SentimentResult(sentiment_score=0.70, sentiment_label="frustrated")
            ),
            "compose_response_task": _fake_task_with_pydantic(
                ComposedResponse(draft_response="Here is our cancellation policy...", grounded=True)
            ),
        }

    monkeypatch.setattr(
        "app.flows.inquiry_flow.kickoff_reasoning_crew", _fake_kickoff_reasoning_crew
    )

    result = run_inquiry(channel="chat", raw_text=_REAL_DISPUTE_MESSAGE, sender_id="guest-1")

    assert result["escalated"] is True
    assert result["reason"] == ["dispute_language_detected"]

    rows = list_interactions(db_path=db_path)
    matching = [r for r in rows if r["id"] == result["inquiry_id"]]
    assert len(matching) == 1
    assert matching[0]["outcome"] == "escalated"
    # sad.md FR-011/ADR-003: confirm the log's query_text is the (redacted)
    # clean_text this test supplied, i.e. contains_dispute_language ran
    # against clean_text, not raw_text (they're identical here since the
    # message has no PII, but the field itself must be clean_text).
    assert matching[0]["query_text"] == _REAL_DISPUTE_MESSAGE
