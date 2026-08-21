"""Local SQLite persistence for the live, mutable knowledge base — Phase 3
of sad.md's "MVP Build Sequencing" ("Review-queue endpoints + the Reviewer
approve/reject write path ... AC-011").

sad.md §4 Data Architecture: KB content is "seeded from domain_config.json,
then mutable only via approved review-queue writes." Before this phase,
`domain/loader.py::kb_search` read `knowledge_base` directly out of the
static, `lru_cache`d `DomainConfig` singleton (`domain_config.json`, loaded
once at process start) — there was no mutable live KB at all, so an
approved review-queue entry could never actually become retrievable
without a process restart, contradicting AC-011 ("retrievable by
knowledge_retriever from that point on"). This module introduces the
missing mutable layer: a `knowledge_base` table in the same
`backend/data/app.db` file (same `INTERACTION_LOG_DB_PATH` env var
convention as `interaction_log.py`/`review_queue.py`, for the same test-
isolation reasons), seeded once from `domain_config.json`'s
`knowledge_base` array, then extended in-place by `insert_kb_entry` on
Reviewer approval (`POST /review-queue/{id}/approve`, `app.main`).

Taxonomy is explicitly OUT of scope here and stays exactly as-is (static
JSON via `domain/loader.py`'s `DomainConfig.taxonomy`, no write path in
MVP) — only `knowledge_base` entries move to this mutable store, per this
phase's task boundary.

Seeding trigger (a documented judgment call, since sad.md doesn't pin one):
this module does NOT self-seed on import or on every read — `count_entries`
and `seed_from_domain_config` are separate, composable primitives.
`domain/loader.py::kb_search` is the actual trigger: it calls
`count_entries()` (a single `SELECT COUNT(*)`, no writes) at the top of
every invocation and only calls `seed_from_domain_config(...)` when the
table is genuinely empty. This is cheap on the common case (the table has
rows — whether from the original seed or a later approval — after the
first call in a process/db lifetime) and self-healing/idempotent on a
fresh or test-isolated db (each `tmp_path`-scoped test db starts empty and
gets seeded from the real `domain_config.json` on first use, matching the
pre-Phase-3 in-memory behavior exactly). An alternative — seeding once at
process start via an `lru_cache`-guarded singleton, mirroring
`domain/loader.py::get_domain_config` — was rejected: it would not reseed
a *different* db path within the same process, breaking the test isolation
that `tests/integration/test_inquiry_flow.py`'s `INTERACTION_LOG_DB_PATH`
monkeypatching already relies on, and buys no real performance benefit at
MVP's KB scale (a handful of rows per intent).

Deliberately no dependency on `app.domain.loader` in this module (avoids a
circular import, since `domain/loader.py` imports from here) — seeding
*data* (the `knowledge_base` entries) is always passed in by the caller,
not looked up here.

Plain stdlib `sqlite3` (no ORM), mirroring `interaction_log.py`/
`review_queue.py`'s style exactly.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

# backend/src/app/persistence/knowledge_base.py -> backend/
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DB_PATH = _BACKEND_ROOT / "data" / "app.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_base (
    kb_entry_id  TEXT PRIMARY KEY,
    intent       TEXT NOT NULL,
    section      TEXT NOT NULL,
    keywords     TEXT NOT NULL DEFAULT '[]',
    content      TEXT NOT NULL
);
"""


def _resolve_db_path(db_path: str | os.PathLike[str] | None = None) -> Path:
    if db_path is not None:
        return Path(db_path)
    # Same env var as interaction_log.py/review_queue.py — all three tables
    # share one db file (sad.md §4: "one local SQLite store"), so one
    # path-resolution knob keeps test isolation consistent across modules.
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
    """Create the knowledge_base table if it doesn't already exist."""
    with _connect(db_path):
        pass


def count_entries(db_path: str | os.PathLike[str] | None = None) -> int:
    """Number of rows currently in the live knowledge_base table. Used by
    `domain/loader.py::kb_search` as the seeding trigger — see module
    docstring."""
    with _connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) FROM knowledge_base").fetchone()
        return int(row[0])


def _entry_to_row(entry: Any) -> tuple[str, str, str, str, str]:
    """Normalize one entry (a `domain/loader.py::KBEntry` pydantic model, or
    an equivalent plain dict — e.g. the shape `app.main`'s approve endpoint
    builds) into the 5-tuple `knowledge_base` expects."""
    e = entry.model_dump() if hasattr(entry, "model_dump") else entry
    return (
        e["kb_entry_id"],
        e["intent"],
        e["section"],
        json.dumps(e.get("keywords") or []),
        e["content"],
    )


def seed_from_domain_config(
    entries: Iterable[Any], db_path: str | os.PathLike[str] | None = None
) -> None:
    """Idempotently seed the live table from `domain_config.json`'s
    `knowledge_base` array (`entries` — typically
    `get_domain_config().knowledge_base`, a `list[KBEntry]`, but any
    iterable of objects/dicts with the same 5 fields works). `INSERT OR
    IGNORE` keyed on `kb_entry_id` — safe to call more than once; existing
    rows (seed or Reviewer-approved) are never overwritten."""
    with _connect(db_path) as conn:
        for entry in entries:
            conn.execute(
                """
                INSERT OR IGNORE INTO knowledge_base
                    (kb_entry_id, intent, section, keywords, content)
                VALUES (?, ?, ?, ?, ?)
                """,
                _entry_to_row(entry),
            )


def insert_kb_entry(entry: dict[str, Any], db_path: str | os.PathLike[str] | None = None) -> None:
    """Insert one new approved KB entry — the sole way `knowledge_base`
    grows beyond its `domain_config.json` seed (Phase 3's Reviewer-approval
    write path, `POST /review-queue/{id}/approve`, `app.main` — NFR-008:
    "no path exists to the live knowledge base except through explicit
    human approval").

    `entry` must carry `kb_entry_id`, `intent`, `section`, `keywords`
    (list[str]), `content`. `INSERT OR IGNORE` keyed on `kb_entry_id` for
    the same idempotent-write reasons as every other persistence module
    here — callers are expected to generate a fresh id per approval, so in
    practice this behaves as a plain insert.
    """
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO knowledge_base
                (kb_entry_id, intent, section, keywords, content)
            VALUES (?, ?, ?, ?, ?)
            """,
            _entry_to_row(entry),
        )


def list_kb_entries(
    intent: str | None = None, db_path: str | os.PathLike[str] | None = None
) -> list[dict[str, Any]]:
    """Return live KB entries, optionally filtered by `intent` (ADR-005
    step 1's filter — `domain/loader.py::kb_search` always passes one).
    Does NOT seed — callers that need seeding-on-empty should call
    `count_entries`/`seed_from_domain_config` themselves first (see
    `domain/loader.py::kb_search`, the one production call site that does).
    """
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if intent is not None:
            rows = conn.execute(
                "SELECT * FROM knowledge_base WHERE intent = ?", (intent,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM knowledge_base").fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["keywords"] = json.loads(d["keywords"])
            result.append(d)
        return result
