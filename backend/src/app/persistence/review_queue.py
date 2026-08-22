"""Local SQLite persistence for the KB review queue — Phase 2 of sad.md's
"MVP Build Sequencing" ("Add EscalationResolutionFlow ... write a candidate
KB entry to the review queue, linked to the original query", FR-008,
AC-010).

sad.md §4 Data Architecture groups the review queue with the interaction
log and (future) KB as one local SQLite store — this module keeps the
`review_queue` table in the same `backend/data/app.db` file as
`interaction_log.py`'s `interaction_log` table (same default path
resolution, same `INTERACTION_LOG_DB_PATH` env var for test isolation — no
new env var was introduced since both tables live in the same db file; see
backend.md Assumptions).

Plain stdlib `sqlite3` (no ORM), mirroring `interaction_log.py`'s style
exactly.

Write-only in this phase: `EscalationResolutionFlow` is the only writer
(`record_review_queue_entry`). `list_review_queue` exists for tests and as
a ready building block for Phase 3's `GET /review-queue` — no such
endpoint is registered yet. Nothing in this module reads or writes the
live KB (`domain_config.json` / a future `knowledge_base` table) — that
stays exclusively Phase 3's Reviewer approve/reject path per NFR-008.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

# backend/src/app/persistence/review_queue.py -> backend/
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DB_PATH = _BACKEND_ROOT / "data" / "app.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS review_queue (
    id                    TEXT PRIMARY KEY,
    created_at            TEXT NOT NULL,
    original_inquiry_id   TEXT NOT NULL,
    original_query_text   TEXT,
    resolution_text       TEXT NOT NULL,
    candidate_intent      TEXT,
    candidate_section     TEXT,
    candidate_keywords    TEXT NOT NULL DEFAULT '[]',
    candidate_content     TEXT NOT NULL,
    status                TEXT NOT NULL DEFAULT 'pending'
);
"""


def _resolve_db_path(db_path: str | os.PathLike[str] | None = None) -> Path:
    if db_path is not None:
        return Path(db_path)
    # Same env var as interaction_log.py — both tables share one db file
    # (sad.md §4: "one local SQLite store"), so one path-resolution knob is
    # sufficient and keeps test isolation consistent between the two
    # modules (a test that monkeypatches INTERACTION_LOG_DB_PATH isolates
    # both tables at once).
    env_path = os.environ.get("INTERACTION_LOG_DB_PATH")
    return Path(env_path) if env_path else _DEFAULT_DB_PATH


@contextmanager
def _connect(db_path: str | os.PathLike[str] | None = None) -> Iterator[sqlite3.Connection]:
    path = _resolve_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str | os.PathLike[str] | None = None) -> None:
    """Create the review_queue table if it doesn't already exist."""
    with _connect(db_path):
        pass


def record_review_queue_entry(
    record: dict[str, Any], db_path: str | os.PathLike[str] | None = None
) -> None:
    """Persist one candidate KB entry (`EscalationResolutionFlow`'s only
    write path, FR-008/AC-010).

    `record` is expected to carry: id, created_at, original_inquiry_id,
    resolution_text, candidate_content, and — when available —
    original_query_text, candidate_intent, candidate_section,
    candidate_keywords (list[str]).

    Uses `INSERT OR IGNORE` (keyed on `id`), the same idempotent-write
    convention as `interaction_log.py::record_interaction` — a re-submitted
    resolution with the same generated id is a no-op rather than a
    duplicate row, for the same defensive reasons documented there.
    """
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO review_queue (
                id, created_at, original_inquiry_id, original_query_text,
                resolution_text, candidate_intent, candidate_section,
                candidate_keywords, candidate_content, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["created_at"],
                record["original_inquiry_id"],
                record.get("original_query_text"),
                record["resolution_text"],
                record.get("candidate_intent"),
                record.get("candidate_section"),
                json.dumps(record.get("candidate_keywords") or []),
                record["candidate_content"],
                record.get("status", "pending"),
            ),
        )


def list_review_queue(db_path: str | os.PathLike[str] | None = None) -> list[dict[str, Any]]:
    """Return all queued candidate entries (pending + approved + rejected),
    most recent first. Backs `GET /review-queue` (Phase 3, `app.main`) —
    sad.md doesn't specify a status filter for this endpoint, so none is
    applied here."""
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM review_queue ORDER BY created_at DESC"
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["candidate_keywords"] = json.loads(d["candidate_keywords"])
            result.append(d)
        return result


def get_review_queue_entry(
    id: str, db_path: str | os.PathLike[str] | None = None
) -> dict[str, Any] | None:
    """Return one review-queue record by `id`, or `None` if not found.

    Added for Phase 3: `POST /review-queue/{id}/approve` and `POST
    /review-queue/{id}/reject` (`app.main`) use this to validate `{id}`
    before acting — a clean 404 when it doesn't exist, per this phase's
    task instructions.
    """
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM review_queue WHERE id = ?", (id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["candidate_keywords"] = json.loads(d["candidate_keywords"])
        return d


def update_review_queue_status(
    id: str, status: str, db_path: str | os.PathLike[str] | None = None
) -> None:
    """Set a review-queue record's `status` (`'approved'` | `'rejected'`).

    Added for Phase 3. Does not itself validate that `id` exists or that
    `status` is a recognized value — callers (`app.main`'s approve/reject
    routes) already call `get_review_queue_entry` first to return a clean
    404, and are the only production callers, so no extra guard is
    duplicated here.
    """
    with _connect(db_path) as conn:
        conn.execute("UPDATE review_queue SET status = ? WHERE id = ?", (status, id))
