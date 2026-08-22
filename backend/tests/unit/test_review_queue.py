"""Unit tests for app.persistence.review_queue (SQLite local store, sad.md
§4 Data Architecture — shares one db file with interaction_log.py, per that
module's docstring). Mirrors test_interaction_log.py's style."""

from __future__ import annotations

from pathlib import Path

from app.persistence.review_queue import init_db, list_review_queue, record_review_queue_entry


def test_init_db_creates_file(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    assert not db_path.exists()
    init_db(db_path)
    assert db_path.exists()


def test_record_and_list_review_queue_entry(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    record = {
        "id": "rq-1",
        "created_at": "2026-08-21T00:00:00+00:00",
        "original_inquiry_id": "inq-1",
        "original_query_text": "The room was dirty and I'm very unhappy.",
        "resolution_text": "Offered a partial refund and had housekeeping re-clean the room.",
        "candidate_intent": "general_complaints",
        "candidate_section": "operator_resolution",
        "candidate_keywords": [],
        "candidate_content": "Offered a partial refund and had housekeeping re-clean the room.",
    }
    record_review_queue_entry(record, db_path=db_path)

    rows = list_review_queue(db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["id"] == "rq-1"
    assert rows[0]["original_inquiry_id"] == "inq-1"
    assert rows[0]["candidate_intent"] == "general_complaints"
    assert rows[0]["status"] == "pending"
    assert rows[0]["candidate_keywords"] == []


def test_record_without_optional_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    record_review_queue_entry(
        {
            "id": "rq-2",
            "created_at": "2026-08-21T00:00:00+00:00",
            "original_inquiry_id": "inq-2",
            "resolution_text": "Resolved via phone call.",
            "candidate_content": "Resolved via phone call.",
        },
        db_path=db_path,
    )
    rows = list_review_queue(db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["original_query_text"] is None
    assert rows[0]["candidate_intent"] is None
    assert rows[0]["candidate_keywords"] == []
    assert rows[0]["status"] == "pending"


def test_duplicate_id_is_ignored_not_duplicated(tmp_path: Path) -> None:
    """Mirrors interaction_log.py's INSERT OR IGNORE convention — a
    re-submitted resolution with the same generated id is a no-op."""
    db_path = tmp_path / "test.db"
    record = {
        "id": "rq-3",
        "created_at": "2026-08-21T00:00:00+00:00",
        "original_inquiry_id": "inq-3",
        "resolution_text": "first write",
        "candidate_content": "first write",
    }
    record_review_queue_entry(record, db_path=db_path)
    record_review_queue_entry({**record, "resolution_text": "second write"}, db_path=db_path)

    rows = list_review_queue(db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["resolution_text"] == "first write"


def test_multiple_records_ordered_most_recent_first(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    for i, ts in enumerate(["2026-08-21T00:00:00+00:00", "2026-08-21T01:00:00+00:00"]):
        record_review_queue_entry(
            {
                "id": f"rq-{i}",
                "created_at": ts,
                "original_inquiry_id": f"inq-{i}",
                "resolution_text": "r",
                "candidate_content": "r",
            },
            db_path=db_path,
        )
    rows = list_review_queue(db_path=db_path)
    assert [r["id"] for r in rows] == ["rq-1", "rq-0"]
