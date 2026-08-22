"""Integration tests for `POST /email` (Phase 2 of sad.md's "MVP Build
Sequencing" — see backend.md). Mirrors test_chat_endpoint.py's pattern:

1. Request validation (422 on malformed input) — deterministic, no
   LLM/network required.
2. A full live round-trip through `InquiryFlow` (channel=email) via the
   real HTTP route — requires a live ANTHROPIC_API_KEY; skipped otherwise.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.integration

_HAS_ANTHROPIC_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))

client = TestClient(app)


def test_email_missing_from_returns_422() -> None:
    response = client.post(
        "/email", json={"subject": "Question", "body": "What time is check-in?"}
    )
    assert response.status_code == 422


def test_email_missing_subject_returns_422() -> None:
    response = client.post(
        "/email", json={"from": "guest@example.com", "body": "What time is check-in?"}
    )
    assert response.status_code == 422


def test_email_missing_body_returns_422() -> None:
    response = client.post(
        "/email", json={"from": "guest@example.com", "subject": "Question"}
    )
    assert response.status_code == 422


@pytest.mark.skipif(
    not _HAS_ANTHROPIC_KEY,
    reason="Full POST /email round-trip requires a live ANTHROPIC_API_KEY "
    "(not available in this environment) — see backend.md Open Questions.",
)
def test_email_end_to_end_returns_reply_body_and_escalated(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))

    response = client.post(
        "/email",
        json={
            "from": "guest-email-endpoint-test@example.com",
            "subject": "Check-in / check-out times",
            "body": "What time is check-in and check-out?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["reply_body"], str) and body["reply_body"]
    assert isinstance(body["escalated"], bool)


@pytest.mark.skipif(
    not _HAS_ANTHROPIC_KEY,
    reason="Full POST /email round-trip requires a live ANTHROPIC_API_KEY "
    "(not available in this environment) — see backend.md Open Questions.",
)
def test_email_logs_interaction_with_channel_email(monkeypatch, tmp_path) -> None:
    """Confirms the `channel=email` mapping actually reaches
    InquiryFlow/interaction_log (sad.md §4: 'Triggers InquiryFlow with
    channel=email')."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))

    response = client.post(
        "/email",
        json={
            "from": "guest-email-channel-test@example.com",
            "subject": "Room service",
            "body": "Can I get extra towels sent to my room?",
        },
    )
    assert response.status_code == 200

    interactions = client.get("/interactions").json()
    matches = [
        r for r in interactions if r["sender_id"] == "guest-email-channel-test@example.com"
    ]
    assert len(matches) == 1
    assert matches[0]["channel"] == "email"
