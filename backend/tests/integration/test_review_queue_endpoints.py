"""Integration tests for `GET /review-queue`, `POST
/review-queue/{id}/approve`, `POST /review-queue/{id}/reject` — Phase 3 of
sad.md's "MVP Build Sequencing" (the sole live-KB write path, NFR-008).

Fully deterministic — none of these three routes trigger an LLM call
(they operate on `review_queue`/`knowledge_base` rows directly), so no
ANTHROPIC_API_KEY / skip-if-no-key pattern is needed, matching
test_escalation_resolve_endpoint.py's pattern.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.persistence.knowledge_base import list_kb_entries
from app.persistence.review_queue import list_review_queue, record_review_queue_entry

pytestmark = pytest.mark.integration

client = TestClient(app)


def _seed_pending_candidate(db_path, review_queue_id: str, **overrides) -> None:
    record = {
        "id": review_queue_id,
        "created_at": "2026-08-21T00:00:00+00:00",
        "original_inquiry_id": "inq-1",
        "original_query_text": "The room was dirty and I'm very unhappy about it.",
        "resolution_text": "Offered a partial refund and had housekeeping re-clean the room.",
        "candidate_intent": "general_complaints",
        "candidate_section": "operator_resolution",
        "candidate_keywords": [],
        "candidate_content": "Offered a partial refund and had housekeeping re-clean the room.",
        **overrides,
    }
    record_review_queue_entry(record, db_path=db_path)


def test_get_review_queue_empty_list_when_no_entries(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))

    response = client.get("/review-queue")
    assert response.status_code == 200
    assert response.json() == []


def test_get_review_queue_lists_entries_most_recent_first(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))
    _seed_pending_candidate(
        db_path, "rq-1", created_at="2026-08-21T00:00:00+00:00", original_inquiry_id="inq-1"
    )
    _seed_pending_candidate(
        db_path, "rq-2", created_at="2026-08-21T01:00:00+00:00", original_inquiry_id="inq-2"
    )

    response = client.get("/review-queue")
    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == ["rq-2", "rq-1"]
    assert body[0]["status"] == "pending"


def test_approve_writes_live_kb_entry_and_marks_status_approved(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))
    _seed_pending_candidate(db_path, "rq-approve-1")

    response = client.post(
        "/review-queue/rq-approve-1/approve",
        json={"keywords": ["refund", "housekeeping", "re-clean"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "general_complaints"
    assert body["section"] == "operator_resolution"
    assert body["keywords"] == ["refund", "housekeeping", "re-clean"]
    assert body["content"] == (
        "Offered a partial refund and had housekeeping re-clean the room."
    )
    assert isinstance(body["kb_entry_id"], str) and body["kb_entry_id"]

    kb_rows = list_kb_entries(intent="general_complaints", db_path=db_path)
    assert any(r["kb_entry_id"] == body["kb_entry_id"] for r in kb_rows)

    queue_rows = list_review_queue(db_path=db_path)
    assert queue_rows[0]["id"] == "rq-approve-1"
    assert queue_rows[0]["status"] == "approved"


def test_approve_optional_edit_overrides_all_fields(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))
    _seed_pending_candidate(db_path, "rq-approve-2")

    response = client.post(
        "/review-queue/rq-approve-2/approve",
        json={
            "intent": "room_service_amenities",
            "section": "Reviewer-edited section",
            "keywords": ["towel", "extra towels"],
            "content": "Reviewer-edited content, not the raw resolution text.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "room_service_amenities"
    assert body["section"] == "Reviewer-edited section"
    assert body["keywords"] == ["towel", "extra towels"]
    assert body["content"] == "Reviewer-edited content, not the raw resolution text."


def test_approve_unknown_id_returns_404(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))

    response = client.post("/review-queue/does-not-exist/approve", json={})
    assert response.status_code == 404
    assert response.json()["error_code"] == "review_queue_entry_not_found"


def test_reapprove_already_approved_entry_returns_409(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))
    _seed_pending_candidate(db_path, "rq-approve-3")

    first = client.post("/review-queue/rq-approve-3/approve", json={"keywords": ["k"]})
    assert first.status_code == 200

    second = client.post("/review-queue/rq-approve-3/approve", json={"keywords": ["k"]})
    assert second.status_code == 409
    assert second.json()["error_code"] == "review_queue_already_actioned"

    # No duplicate KB entry from the rejected second attempt.
    kb_rows = list_kb_entries(intent="general_complaints", db_path=db_path)
    assert len(kb_rows) == 1


def test_approve_missing_intent_with_no_override_returns_422(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))
    _seed_pending_candidate(db_path, "rq-approve-4", candidate_intent=None)

    response = client.post("/review-queue/rq-approve-4/approve", json={})
    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_kb_entry"


def test_reject_marks_status_rejected_with_no_kb_write(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))
    _seed_pending_candidate(db_path, "rq-reject-1")

    response = client.post("/review-queue/rq-reject-1/reject")
    assert response.status_code == 200
    body = response.json()
    assert body == {"id": "rq-reject-1", "status": "rejected"}

    queue_rows = list_review_queue(db_path=db_path)
    assert queue_rows[0]["status"] == "rejected"
    assert list_kb_entries(db_path=db_path) == []


def test_reject_unknown_id_returns_404(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))

    response = client.post("/review-queue/does-not-exist/reject")
    assert response.status_code == 404
    assert response.json()["error_code"] == "review_queue_entry_not_found"


def test_rereject_already_rejected_entry_returns_409(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))
    _seed_pending_candidate(db_path, "rq-reject-2")

    first = client.post("/review-queue/rq-reject-2/reject")
    assert first.status_code == 200

    second = client.post("/review-queue/rq-reject-2/reject")
    assert second.status_code == 409
    assert second.json()["error_code"] == "review_queue_already_actioned"


def test_get_review_queue_shows_mixed_statuses(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))
    _seed_pending_candidate(
        db_path, "rq-mixed-1", created_at="2026-08-21T00:00:00+00:00"
    )
    _seed_pending_candidate(
        db_path, "rq-mixed-2", created_at="2026-08-21T01:00:00+00:00"
    )

    client.post("/review-queue/rq-mixed-1/approve", json={"keywords": ["k"]})
    client.post("/review-queue/rq-mixed-2/reject")

    body = client.get("/review-queue").json()
    statuses = {item["id"]: item["status"] for item in body}
    assert statuses == {"rq-mixed-1": "approved", "rq-mixed-2": "rejected"}
