"""Unit tests for app.persistence.interaction_log (SQLite local store,
sad.md §4 Data Architecture)."""

from __future__ import annotations

from pathlib import Path

from app.persistence.interaction_log import init_db, list_interactions, record_interaction


def test_init_db_creates_file(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    assert not db_path.exists()
    init_db(db_path)
    assert db_path.exists()


def test_record_and_list_interaction(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    record = {
        "id": "abc-123",
        "created_at": "2026-08-19T00:00:00+00:00",
        "channel": "chat",
        "sender_id": "guest-1",
        "query_text": "What time is check-in?",
        "intent": "checkin_checkout_billing",
        "confidence": 0.92,
        "sentiment_score": 0.05,
        "sentiment_label": "neutral",
        "match_found": True,
        "grounded": True,
        "response_text": "Check-in is 3:00 PM.",
        "outcome": "responded",
        "redaction_actions": [],
    }
    record_interaction(record, db_path=db_path)

    rows = list_interactions(db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["id"] == "abc-123"
    assert rows[0]["intent"] == "checkin_checkout_billing"
    assert rows[0]["outcome"] == "responded"
    assert rows[0]["redaction_count"] == 0


def test_record_diagnostic_halt_without_optional_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    record_interaction(
        {
            "id": "halt-1",
            "created_at": "2026-08-19T00:00:00+00:00",
            "channel": "chat",
            "sender_id": "guest-2",
            "query_text": "[UNAVAILABLE - PII GUARD FAILURE, RAW TEXT NOT PERSISTED]",
            "outcome": "diagnostic_halt",
            "diagnostic": "pii_guard failure: boom",
        },
        db_path=db_path,
    )
    rows = list_interactions(db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["outcome"] == "diagnostic_halt"
    assert rows[0]["intent"] is None
    assert rows[0]["diagnostic"] == "pii_guard failure: boom"


def test_multiple_records_ordered_most_recent_first(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    for i, ts in enumerate(["2026-08-19T00:00:00+00:00", "2026-08-19T01:00:00+00:00"]):
        record_interaction(
            {
                "id": f"rec-{i}",
                "created_at": ts,
                "channel": "chat",
                "sender_id": "guest",
                "query_text": "q",
                "outcome": "responded",
            },
            db_path=db_path,
        )
    rows = list_interactions(db_path=db_path)
    assert [r["id"] for r in rows] == ["rec-1", "rec-0"]
