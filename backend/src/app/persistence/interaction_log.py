"""Local SQLite persistence for the interaction log — sad.md §4 Data
Architecture ("Local file-based or embedded DB (e.g., SQLite) ... No
vector DB / external database for MVP") and §2 step 6 ("always runs (both
branches) — persists one interaction-log record: query, classification,
sentiment, PII actions taken, outcome").

Plain `sqlite3` (stdlib) rather than an ORM — the schema is one table with
no relations, well within stdlib's capability for MVP data volume (four
hotel scenario categories, no real traffic, per setup.md Assumptions).
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

# backend/src/app/persistence/interaction_log.py -> backend/
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DB_PATH = _BACKEND_ROOT / "data" / "app.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS interaction_log (
    id                  TEXT PRIMARY KEY,
    created_at          TEXT NOT NULL,
    channel             TEXT NOT NULL,
    sender_id           TEXT NOT NULL,
    query_text          TEXT NOT NULL,
    intent              TEXT,
    confidence          REAL,
    sentiment_score     REAL,
    sentiment_label     TEXT,
    match_found         INTEGER,
    grounded            INTEGER,
    response_text       TEXT,
    outcome             TEXT NOT NULL,
    redaction_count     INTEGER NOT NULL DEFAULT 0,
    redaction_actions   TEXT NOT NULL DEFAULT '[]',
    diagnostic          TEXT
);
"""


def _resolve_db_path(db_path: str | os.PathLike[str] | None = None) -> Path:
    if db_path is not None:
        return Path(db_path)
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
    """Create the interaction_log table if it doesn't already exist."""
    with _connect(db_path):
        pass


def record_interaction(
    record: dict[str, Any], db_path: str | os.PathLike[str] | None = None
) -> None:
    """Persist one interaction-log record (sad.md §2 step 6 / §6).

    `record` is expected to carry (at minimum): id, created_at, channel,
    sender_id, query_text, outcome ("escalated" | "responded" |
    "diagnostic_halt"), and — when available — intent, confidence,
    sentiment_score, sentiment_label, match_found, grounded, response_text,
    redaction_actions (list of dicts matching RedactionAction).

    Uses `INSERT OR IGNORE` (not plain `INSERT`) keyed on the existing `id`
    PRIMARY KEY: normally every caller mints a fresh UUID per call, so this
    is functionally identical to a plain INSERT. The one deliberate
    exception is `inquiry_flow.py`'s timeout path, which shares one
    `inquiry_id` between its own timeout-escalation write and the
    (possibly still-running-in-the-background) flow's own `log_interaction`
    write for the same inquiry — `OR IGNORE` makes whichever of the two
    writes lands second a silent no-op instead of a duplicate row, so
    exactly one record ever persists per inquiry regardless of write order.
    See inquiry_flow.py::run_inquiry and backend.md for the full rationale.
    """
    redaction_actions = record.get("redaction_actions") or []
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO interaction_log (
                id, created_at, channel, sender_id, query_text, intent,
                confidence, sentiment_score, sentiment_label, match_found,
                grounded, response_text, outcome, redaction_count,
                redaction_actions, diagnostic
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["created_at"],
                record["channel"],
                record["sender_id"],
                record["query_text"],
                record.get("intent"),
                record.get("confidence"),
                record.get("sentiment_score"),
                record.get("sentiment_label"),
                None if record.get("match_found") is None else int(record["match_found"]),
                None if record.get("grounded") is None else int(record["grounded"]),
                record.get("response_text"),
                record["outcome"],
                len(redaction_actions),
                json.dumps(redaction_actions),
                record.get("diagnostic"),
            ),
        )


def get_interaction_by_id(
    inquiry_id: str, db_path: str | os.PathLike[str] | None = None
) -> dict[str, Any] | None:
    """Return one interaction-log record by `id` (the same id `InquiryFlow`
    persists per inquiry, sad.md §2 step 6), or `None` if not found.

    Added for Phase 2 of sad.md's "MVP Build Sequencing":
    `EscalationResolutionFlow` (`flows/escalation_resolution_flow.py`) uses
    this to link a review-queue candidate entry back to its original query
    (FR-008, AC-010), and `POST /escalations/{id}/resolve` uses it to
    validate the path `id` before triggering that flow.
    """
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM interaction_log WHERE id = ?", (inquiry_id,)
        ).fetchone()
        return dict(row) if row else None


def list_interactions(db_path: str | os.PathLike[str] | None = None) -> list[dict[str, Any]]:
    """Return all persisted interaction-log records, most recent first.
    Used by tests and by `GET /interactions` (`app.main`) — a deliberate
    Phase 3 -> now pull-forward per operator decision (2026-08-20), see
    backend.md; sad.md's own "MVP Build Sequencing" table still scopes this
    endpoint to Phase 3."""
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM interaction_log ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
