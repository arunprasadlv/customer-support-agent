"""Unit tests for app.persistence.knowledge_base (SQLite live KB store,
Phase 3 of sad.md's "MVP Build Sequencing" — the live-KB migration behind
`domain/loader.py::kb_search`). Mirrors test_review_queue.py's style.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.loader import KBEntry, kb_search
from app.persistence.knowledge_base import (
    count_entries,
    init_db,
    insert_kb_entry,
    list_kb_entries,
    seed_from_domain_config,
)


def test_init_db_creates_file(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    assert not db_path.exists()
    init_db(db_path)
    assert db_path.exists()


def test_count_entries_zero_on_fresh_db(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    assert count_entries(db_path=db_path) == 0


def test_seed_from_domain_config_populates_table(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    entries = [
        KBEntry(
            kb_entry_id="kb-seed-1",
            intent="reservations_booking",
            section="Test section",
            keywords=["book", "reservation"],
            content="Seed content.",
        ),
    ]
    seed_from_domain_config(entries, db_path=db_path)

    assert count_entries(db_path=db_path) == 1
    rows = list_kb_entries(db_path=db_path)
    assert rows[0]["kb_entry_id"] == "kb-seed-1"
    assert rows[0]["keywords"] == ["book", "reservation"]


def test_seed_from_domain_config_is_idempotent(tmp_path: Path) -> None:
    """INSERT OR IGNORE keyed on kb_entry_id — calling seed twice must not
    duplicate rows or overwrite an existing entry's content."""
    db_path = tmp_path / "test.db"
    entry = KBEntry(
        kb_entry_id="kb-seed-1",
        intent="reservations_booking",
        section="Test section",
        keywords=["book"],
        content="Original content.",
    )
    seed_from_domain_config([entry], db_path=db_path)
    seed_from_domain_config(
        [
            KBEntry(
                kb_entry_id="kb-seed-1",
                intent="reservations_booking",
                section="Test section",
                keywords=["book"],
                content="Different content — must not overwrite.",
            )
        ],
        db_path=db_path,
    )

    assert count_entries(db_path=db_path) == 1
    rows = list_kb_entries(db_path=db_path)
    assert rows[0]["content"] == "Original content."


def test_insert_kb_entry_adds_a_new_row(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    insert_kb_entry(
        {
            "kb_entry_id": "kb-approved-1",
            "intent": "general_complaints",
            "section": "operator_resolution",
            "keywords": ["refund", "voucher"],
            "content": "Offered a service credit for the inconvenience.",
        },
        db_path=db_path,
    )

    assert count_entries(db_path=db_path) == 1
    rows = list_kb_entries(intent="general_complaints", db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["kb_entry_id"] == "kb-approved-1"
    assert rows[0]["keywords"] == ["refund", "voucher"]


def test_list_kb_entries_filters_by_intent(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    insert_kb_entry(
        {
            "kb_entry_id": "kb-a",
            "intent": "reservations_booking",
            "section": "s",
            "keywords": ["book"],
            "content": "c",
        },
        db_path=db_path,
    )
    insert_kb_entry(
        {
            "kb_entry_id": "kb-b",
            "intent": "general_complaints",
            "section": "s",
            "keywords": ["complain"],
            "content": "c",
        },
        db_path=db_path,
    )

    reservations_entries = list_kb_entries(intent="reservations_booking", db_path=db_path)
    assert [e["kb_entry_id"] for e in reservations_entries] == ["kb-a"]
    assert len(list_kb_entries(db_path=db_path)) == 2


def test_kb_search_finds_a_manually_inserted_live_entry(monkeypatch, tmp_path: Path) -> None:
    """The concrete proof this module exists for: an entry inserted
    directly into the live table (standing in for a Reviewer approval, see
    the integration test for the real end-to-end proof through the
    endpoints) is retrievable via domain/loader.py::kb_search — no
    domain_config.json edit, no restart."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))

    insert_kb_entry(
        {
            "kb_entry_id": "kb-manual-1",
            "intent": "room_service_amenities",
            "section": "operator_resolution",
            "keywords": ["late night snack", "vending machine"],
            "content": "Vending machines are available on every floor 24/7.",
        },
        db_path=db_path,
    )

    result = kb_search(
        intent="room_service_amenities",
        query_text="Is there a vending machine for a late night snack?",
    )

    assert result.match_found is True
    assert any(s.kb_entry_id == "kb-manual-1" for s in result.retrieved_snippets)


def test_kb_search_still_finds_seeded_entries_when_table_is_fresh(
    monkeypatch, tmp_path: Path
) -> None:
    """Regression guard for the live-KB migration: a completely fresh db
    (no prior seeding, no manual insert) must still self-seed from the real
    domain_config.json on first kb_search call, matching pre-Phase-3
    behavior exactly (test_inquiry_flow.py's scenario-category tests rely
    on this)."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))

    result = kb_search(
        intent="checkin_checkout_billing",
        query_text="What time is check-in and check-out?",
    )

    assert result.match_found is True
    assert count_entries(db_path=db_path) > 0
