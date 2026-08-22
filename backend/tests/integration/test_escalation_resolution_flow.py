"""Integration tests for app.flows.escalation_resolution_flow.
EscalationResolutionFlow / run_escalation_resolution.

Unlike InquiryFlow, this flow has no LLM-backed steps (sad.md §2: it only
reads the interaction log and writes to the review queue), so every test
here is fully deterministic — no ANTHROPIC_API_KEY / skip-if-no-key
pattern needed, unlike test_inquiry_flow.py.
"""

from __future__ import annotations

import pytest

from app.flows.escalation_resolution_flow import (
    EscalationResolutionFlow,
    OriginalInquiryNotFound,
    run_escalation_resolution,
)
from app.persistence.interaction_log import record_interaction
from app.persistence.review_queue import list_review_queue

pytestmark = pytest.mark.integration


def _seed_escalated_interaction(db_path, inquiry_id: str = "inq-escalated-1") -> str:
    record_interaction(
        {
            "id": inquiry_id,
            "created_at": "2026-08-21T00:00:00+00:00",
            "channel": "chat",
            "sender_id": "guest-1",
            "query_text": "The room was dirty and I'm very unhappy about it.",
            "intent": "general_complaints",
            "confidence": 0.55,
            "sentiment_score": 0.82,
            "sentiment_label": "angry",
            "match_found": False,
            "grounded": False,
            "response_text": None,
            "outcome": "escalated",
            "redaction_actions": [],
        },
        db_path=db_path,
    )
    return inquiry_id


def test_run_escalation_resolution_writes_candidate_to_review_queue(monkeypatch, tmp_path) -> None:
    """sad.md §2: EscalationResolutionFlow writes a candidate KB entry to
    the review queue, linked to the original query (FR-008, AC-010)."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))
    inquiry_id = _seed_escalated_interaction(db_path)

    result = run_escalation_resolution(
        original_inquiry_id=inquiry_id,
        resolution_text="Offered a partial refund and re-cleaned the room personally.",
    )

    assert "review_queue_id" in result and result["review_queue_id"]

    rows = list_review_queue(db_path=db_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == result["review_queue_id"]
    assert row["original_inquiry_id"] == inquiry_id
    assert row["original_query_text"] == "The room was dirty and I'm very unhappy about it."
    assert row["candidate_intent"] == "general_complaints"
    assert row["candidate_content"] == (
        "Offered a partial refund and re-cleaned the room personally."
    )
    assert row["status"] == "pending"


def test_run_escalation_resolution_does_not_touch_live_kb(monkeypatch, tmp_path) -> None:
    """Explicit scope check: this flow must never import/touch domain
    config or a live knowledge_base table — Phase 3's job only (NFR-008)."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))
    inquiry_id = _seed_escalated_interaction(db_path)

    import app.flows.escalation_resolution_flow as module

    # Sanity: this module never imports domain_config/kb_search machinery —
    # the only persistence it touches is interaction_log (read) and
    # review_queue (write).
    assert not hasattr(module, "get_domain_config")
    assert not hasattr(module, "kb_search")

    run_escalation_resolution(
        original_inquiry_id=inquiry_id, resolution_text="Resolved."
    )
    # No assertion beyond "did not raise / did not import domain config" —
    # there is no live-KB write path in this module to assert against.


def test_run_escalation_resolution_raises_on_unknown_inquiry_id(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))

    with pytest.raises(OriginalInquiryNotFound):
        run_escalation_resolution(
            original_inquiry_id="does-not-exist", resolution_text="Resolved."
        )

    assert list_review_queue(db_path=db_path) == []


def test_flow_steps_directly(monkeypatch, tmp_path) -> None:
    """Exercise the Flow's own methods directly, mirroring
    test_inquiry_flow.py's pattern of calling steps without kickoff()."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))
    inquiry_id = _seed_escalated_interaction(db_path, inquiry_id="inq-direct-1")

    flow = EscalationResolutionFlow()
    flow.state["original_inquiry_id"] = inquiry_id
    flow.state["resolution_text"] = "Direct-call resolution."
    resolution = flow.receive_resolution()
    candidate = flow.build_candidate_entry(resolution)
    payload = flow.write_to_review_queue(candidate)

    assert payload["review_queue_id"]
    rows = list_review_queue(db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["original_inquiry_id"] == inquiry_id
