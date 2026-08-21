"""Integration tests for `POST /escalations/{id}/resolve` (Phase 2 of
sad.md's "MVP Build Sequencing" — see backend.md). Mirrors
test_chat_endpoint.py's pattern, but — like
test_escalation_resolution_flow.py — this endpoint triggers no LLM calls
(`EscalationResolutionFlow` only reads the interaction log and writes to
the review queue), so every test here is fully deterministic: no
ANTHROPIC_API_KEY / skip-if-no-key pattern needed.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.persistence.interaction_log import record_interaction
from app.persistence.review_queue import list_review_queue

pytestmark = pytest.mark.integration

client = TestClient(app)


def _seed_escalated_interaction(db_path, inquiry_id: str) -> None:
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


def test_resolve_escalation_returns_queued_status_and_review_queue_id(
    monkeypatch, tmp_path
) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))
    _seed_escalated_interaction(db_path, "inq-resolve-endpoint-1")

    response = client.post(
        "/escalations/inq-resolve-endpoint-1/resolve",
        json={"resolution_text": "Offered a partial refund and re-cleaned the room."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert isinstance(body["review_queue_id"], str) and body["review_queue_id"]

    rows = list_review_queue(db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["id"] == body["review_queue_id"]
    assert rows[0]["original_inquiry_id"] == "inq-resolve-endpoint-1"
    assert rows[0]["resolution_text"] == (
        "Offered a partial refund and re-cleaned the room."
    )


def test_resolve_escalation_missing_resolution_text_returns_422(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))
    _seed_escalated_interaction(db_path, "inq-resolve-endpoint-2")

    response = client.post("/escalations/inq-resolve-endpoint-2/resolve", json={})
    assert response.status_code == 422


def test_resolve_escalation_unknown_id_returns_404_error_envelope(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))

    response = client.post(
        "/escalations/does-not-exist/resolve",
        json={"resolution_text": "Resolved."},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "original_inquiry_not_found"
    assert "message" in body
    assert list_review_queue(db_path=db_path) == []
