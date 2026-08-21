"""Integration tests for `POST /chat` (`*implement-endpoint`, Phase 1 of
sad.md's "MVP Build Sequencing" — see backend.md) and `GET /interactions`
(`*implement-endpoint` follow-up, 2026-08-20 — a deliberate Phase 3 -> now
pull-forward per operator decision; see backend.md).

Two tiers, mirroring `test_inquiry_flow.py`'s pattern:

1. Request validation (422 on malformed input) / empty-state responses —
   deterministic, no LLM/network required.
2. A full live round-trip through `InquiryFlow` via the real HTTP route —
   requires a live `ANTHROPIC_API_KEY`; skipped otherwise.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.integration

_HAS_ANTHROPIC_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))

client = TestClient(app)


def test_chat_missing_message_returns_422() -> None:
    """FastAPI/Pydantic validation (sad.md §4) — a malformed request must
    surface as a 422, never an unhandled 500."""
    response = client.post("/chat", json={"session_id": "guest-1"})
    assert response.status_code == 422


def test_chat_missing_session_id_returns_422() -> None:
    response = client.post("/chat", json={"message": "hello"})
    assert response.status_code == 422


@pytest.mark.skipif(
    not _HAS_ANTHROPIC_KEY,
    reason="Full POST /chat round-trip requires a live ANTHROPIC_API_KEY "
    "(not available in this environment) — see backend.md Open Questions.",
)
def test_chat_end_to_end_returns_reply_and_escalated(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))

    response = client.post(
        "/chat",
        json={
            "message": "What time is check-in and check-out?",
            "session_id": "guest-chat-endpoint-test",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["reply"], str) and body["reply"]
    assert isinstance(body["escalated"], bool)


def test_interactions_empty_list_when_no_interactions(monkeypatch, tmp_path) -> None:
    """`GET /interactions` (sad.md §4) returns `[]`, not a 404/error, when
    the interaction log is empty — deterministic, no LLM/network."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))

    response = client.get("/interactions")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.skipif(
    not _HAS_ANTHROPIC_KEY,
    reason="Full POST /chat -> GET /interactions round-trip requires a live "
    "ANTHROPIC_API_KEY (not available in this environment) — see "
    "backend.md Open Questions.",
)
def test_interactions_shows_record_after_chat_call(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))

    chat_response = client.post(
        "/chat",
        json={
            "message": "What time is check-in and check-out?",
            "session_id": "guest-interactions-endpoint-test",
        },
    )
    assert chat_response.status_code == 200

    interactions_response = client.get("/interactions")
    assert interactions_response.status_code == 200
    rows = interactions_response.json()

    # Filter to this test's own row by sender_id rather than asserting a
    # total row count: an unrelated *prior* test's un-killable straggler
    # background thread (documented in backend.md §11 — CrewAI's Flow
    # thread can't be forcibly killed once started) can land its own row
    # in this test's tmp_path-scoped db if it finally writes while this
    # test's INTERACTION_LOG_DB_PATH monkeypatch is still active. This
    # mirrors test_inquiry_flow.py's same per-inquiry-id defensive pattern.
    matches = [r for r in rows if r["sender_id"] == "guest-interactions-endpoint-test"]
    assert len(matches) == 1
    row = matches[0]
    assert row["channel"] == "chat"
    assert row["sender_id"] == "guest-interactions-endpoint-test"
    assert row["outcome"] in ("responded", "escalated")
    assert isinstance(row["query_text"], str) and row["query_text"]
    assert isinstance(row["redaction_count"], int)
    assert isinstance(row["redaction_actions"], list)
    # response_text mirrors whatever `POST /chat` actually replied with —
    # except on the sad.md §7 max_execution_time timeout-escalation path
    # (`run_inquiry`'s `except FutureTimeoutError` branch, inquiry_flow.py),
    # which persists only a diagnostic row (no response_text/intent/etc.)
    # and returns a reply that was never itself written to the DB.
    if row.get("diagnostic"):
        assert row["response_text"] is None
    else:
        assert row["response_text"] == chat_response.json()["reply"]
    assert row["outcome"] == ("escalated" if chat_response.json()["escalated"] else "responded")
