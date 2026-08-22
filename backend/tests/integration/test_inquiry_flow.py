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
"""

from __future__ import annotations

import os
import time

import pytest

from app.flows.inquiry_flow import InquiryFlow, PiiGuardFailure, run_inquiry
from app.persistence.interaction_log import list_interactions

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
