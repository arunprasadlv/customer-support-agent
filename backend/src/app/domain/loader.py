"""Domain configuration loader + ADR-005 keyword/section-scored kb_search.

sad.md §2 ADR-005 (verbatim algorithm):
    1. Filter domain_config.json's knowledge_base array to entries where
       entry.intent == intent (the ClassificationResult.intent).
    2. Score each surviving entry by keyword overlap:
       relevance_score = |keywords(query) ∩ entry.keywords| / |entry.keywords|
    3. Floor: drop entries scoring below 0.20.
    4. Return the top 3 surviving entries as retrieved_snippets;
       match_found = true iff at least one entry cleared the floor.

Implementation note (recorded in backend.md Assumptions): the SAD defines
the score via `keywords(query) ∩ entry.keywords` but does not separately
specify a query-side keyword-extraction algorithm. This module interprets
`keywords(query) ∩ entry.keywords` as "the subset of entry.keywords that
appear as a case-insensitive substring of the raw query text" — this keeps
the algorithm fully deterministic/local (no NLP dependency) and matches
ADR-005's "fully explainable... every relevance_score traces to specific
overlapping words" rationale.

No hotel-specific strings/logic live in this module (AC-009) — everything
domain-specific is read from domain_config.json.

Phase 3 update (sad.md §4 Data Architecture: KB content is "seeded from
domain_config.json, then mutable only via approved review-queue writes"):
`kb_search`'s entry data source is now the live, mutable `knowledge_base`
table (`app.persistence.knowledge_base`) instead of `config.knowledge_base`
directly — the scoring/floor/top-3 algorithm below is unchanged. The live
table is seeded once (self-healing/idempotent — see
`persistence/knowledge_base.py`'s module docstring for the exact trigger)
from this same `DomainConfig.knowledge_base`, then grows only via
`POST /review-queue/{id}/approve` (`app.main`), never here. `taxonomy`
remains untouched — still read directly off the static `DomainConfig`
singleton, no live/mutable store for it in MVP.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

import jsonschema
from pydantic import BaseModel, Field

from app.persistence.knowledge_base import count_entries as _kb_count_entries
from app.persistence.knowledge_base import list_kb_entries as _list_kb_entries
from app.persistence.knowledge_base import seed_from_domain_config as _seed_kb_from_domain_config
from app.schemas.task_outputs import KBRetrievalResult, KBSnippet

RELEVANCE_FLOOR = 0.20
TOP_N = 3

# backend/src/app/domain/loader.py -> backend/
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG_PATH = _BACKEND_ROOT / "domain_config.json"
_DEFAULT_SCHEMA_PATH = _BACKEND_ROOT / "domain_config.schema.json"


class TaxonomyEntry(BaseModel):
    intent: str
    label: str
    keywords: list[str] = Field(default_factory=list)


class KBEntry(BaseModel):
    kb_entry_id: str
    intent: str
    section: str
    keywords: list[str] = Field(default_factory=list)
    content: str
    example_query: str | None = Field(
        default=None,
        description=(
            "Natural guest-phrased question this entry answers — surfaced by "
            "GET /taxonomy as a chat quick-reply suggestion. Not used by "
            "kb_search's retrieval scoring (ADR-005 is unchanged)."
        ),
    )


class DomainConfig(BaseModel):
    domain: str
    version: str
    description: str | None = None
    taxonomy: list[TaxonomyEntry]
    knowledge_base: list[KBEntry]
    prompts: dict = Field(default_factory=dict)


def load_domain_config(
    config_path: str | os.PathLike[str] | None = None,
    schema_path: str | os.PathLike[str] | None = None,
) -> DomainConfig:
    """Load + schema-validate domain_config.json (FR-012/FR-013, PRD "JSON,
    schema-validated"). Raises jsonschema.ValidationError on a malformed
    config rather than silently proceeding — fail-closed per aamad-core.md.
    """
    config_path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    schema_path = Path(schema_path) if schema_path else _DEFAULT_SCHEMA_PATH

    with open(config_path, encoding="utf-8") as f:
        raw = json.load(f)
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    jsonschema.validate(instance=raw, schema=schema)
    return DomainConfig.model_validate(raw)


@lru_cache(maxsize=1)
def get_domain_config() -> DomainConfig:
    """Process-wide singleton, loaded once at start (sad.md §4 Runtime
    Integration Layer: "domain_config.json loaded once at start and
    hot-swappable only by restart for MVP")."""
    return load_domain_config()


def kb_search(
    intent: str, query_text: str, config: DomainConfig | None = None
) -> KBRetrievalResult:
    """ADR-005 keyword/section-scored retrieval. Pure function apart from
    the live-KB read (Phase 3, see module docstring) — no network, no
    embeddings, no external call.

    `config` is still accepted (and still used to seed the live table when
    it's empty) for signature stability and because it's how the seed data
    itself is sourced; entries are otherwise read from the live
    `knowledge_base` table (`app.persistence.knowledge_base`), not from
    `config.knowledge_base` directly.
    """
    config = config or get_domain_config()

    # Seeding trigger (see persistence/knowledge_base.py's module docstring
    # for the full rationale): cheap no-op once the table has any rows;
    # self-healing on a fresh/empty (e.g. test-isolated) table.
    if _kb_count_entries() == 0:
        _seed_kb_from_domain_config(config.knowledge_base)

    query_lower = query_text.lower()

    scored: list[KBSnippet] = []
    for entry in _list_kb_entries(intent=intent):
        keywords = entry.get("keywords") or []
        if not keywords:
            continue
        matched = [kw for kw in keywords if kw.lower() in query_lower]
        relevance_score = len(matched) / len(keywords)
        if relevance_score < RELEVANCE_FLOOR:
            continue
        scored.append(
            KBSnippet(
                kb_entry_id=entry["kb_entry_id"],
                content=entry["content"],
                relevance_score=round(relevance_score, 4),
            )
        )

    scored.sort(key=lambda s: s.relevance_score, reverse=True)
    top = scored[:TOP_N]
    return KBRetrievalResult(retrieved_snippets=top, match_found=len(top) > 0)


MAX_DERIVED_KEYWORDS = 5


def derive_keywords(
    intent: str | None, texts: list[str], config: DomainConfig | None = None
) -> list[str]:
    """Deterministically derive KB retrieval keywords for a candidate entry
    when none were supplied — no LLM call, same "fully explainable" spirit
    as `kb_search` itself (ADR-005).

    Intersects `intent`'s taxonomy keyword hints (`domain_config.json`'s
    `taxonomy[].keywords` — the same list already primes `query_classifier`
    to recognize a topic) against `texts` (typically the original guest
    query plus the operator's resolution text), keeping only the taxonomy
    keywords that literally appear (case-insensitive substring) in that
    combined text. This guarantees every keyword returned here will
    actually match a future guest query containing it, since it's the exact
    same substring check `kb_search` performs at retrieval time.

    Capped at `MAX_DERIVED_KEYWORDS` (5) — ADR-005's relevance floor is
    `matched / len(entry.keywords) >= 0.20`, so a single future match needs
    `len(entry.keywords) <= 5` to ever clear it; a longer derived list would
    silently dilute a real match below the floor (the exact bug fixed in
    kb-checkin-001/kb-checkin-002/kb-room-002 — see domain_config.json's
    history). Returns `[]` if `intent` doesn't match a taxonomy entry (or is
    `None` — e.g. a diagnostic-halt/timeout original interaction with no
    classified intent) or if none of that intent's keywords appear in
    `texts`; callers should treat an empty result as "could not auto-derive
    anything useful," not an error.
    """
    if not intent:
        return []
    config = config or get_domain_config()
    taxonomy_entry = next((t for t in config.taxonomy if t.intent == intent), None)
    if taxonomy_entry is None:
        return []
    combined_text = " ".join(texts).lower()
    matched = [kw for kw in taxonomy_entry.keywords if kw.lower() in combined_text]
    return matched[:MAX_DERIVED_KEYWORDS]


def validate_config_file(
    config_path: str | os.PathLike[str] | None = None,
    schema_path: str | os.PathLike[str] | None = None,
) -> list[str]:
    """Returns a list of human-readable validation errors (empty = valid).
    Used by unit tests and can be reused by a future CLI/CI check."""
    config_path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    schema_path = Path(schema_path) if schema_path else _DEFAULT_SCHEMA_PATH
    try:
        with open(config_path, encoding="utf-8") as f:
            raw = json.load(f)
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
        jsonschema.validate(instance=raw, schema=schema)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Could not read/parse config or schema: {exc}"]
    except jsonschema.ValidationError as exc:
        return [str(exc)]
    return []
