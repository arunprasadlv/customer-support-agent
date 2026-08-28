"""FastAPI application entrypoint.

Scaffolded by @project.mgr (*setup-project) per sad.md §4 (Backend
Architecture Specification) and §5 (DevOps & Deployment Architecture,
which requires a `/health` endpoint).

`*implement-endpoint` (Phase 1 of sad.md's "MVP Build Sequencing") added
`POST /chat` — the vertical slice for the `/chat` frontend surface, wired
to `InquiryFlow` via `app.flows.inquiry_flow.run_inquiry()`.

`*implement-endpoint` follow-up (2026-08-20) adds `GET /interactions` —
a deliberate, narrow pull-forward of a Phase 3 endpoint (sad.md's "MVP
Build Sequencing" table scopes `GET /interactions` to Phase 3, alongside
the `/ops` view). The operator explicitly chose to build it now, ahead of
that sequencing, to satisfy a reviewer comment requiring proof that
`POST /chat` produces a real, visible interaction-log row before
Integration wires up the frontend — see backend.md for the full rationale
and Audit entry. This does not pull forward any other Phase 2/3 endpoint.

`*develop-be`/`*implement-endpoint` Phase 2 (2026-08-21) adds `POST
/email` (triggers `InquiryFlow` with `channel=email`, per sad.md §4) and
`POST /escalations/{id}/resolve` (triggers the new
`EscalationResolutionFlow`, writing a candidate KB entry to the review
queue — sad.md §2, FR-008/AC-010). See backend.md's Phase 2 section for
the `{from, subject, body}` -> `raw_text`/`sender_id` mapping and the
`{id}` -> `original_inquiry_id` mapping, both `@backend.eng` judgment
calls documented there.

`*develop-be`/`*implement-endpoint` Phase 3 (2026-08-21) adds `GET
/review-queue`, `POST /review-queue/{id}/approve`, and `POST
/review-queue/{id}/reject` — sad.md §2's "Third, fully separate write
path", the *sole* path that can mutate the live KB (NFR-008, FR-014,
AC-011). Approve writes the (optionally Reviewer-edited) candidate to the
new live `knowledge_base` table (`app.persistence.knowledge_base`) and
marks the queue row `status='approved'`; reject marks it `status='rejected'`
with no KB write. See backend.md's Phase 3 section for the re-approve/
re-reject idempotency choice (409, not silently accepted) and the
optional-edit request shape.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

# Load backend/.env (ANTHROPIC_API_KEY, etc.) into the process environment
# before anything below might need it (sad.md §4 Authentication & Secrets:
# "API key via env var only"). python-dotenv is already a declared
# dependency (pyproject.toml) but was previously unused.
load_dotenv()

from app.domain.loader import derive_keywords, get_domain_config  # noqa: E402
from app.flows.escalation_resolution_flow import (  # noqa: E402
    OriginalInquiryNotFound,
    run_escalation_resolution,
)
from app.flows.inquiry_flow import run_inquiry  # noqa: E402
from app.persistence.interaction_log import list_interactions  # noqa: E402
from app.persistence.knowledge_base import insert_kb_entry  # noqa: E402
from app.persistence.review_queue import (  # noqa: E402
    get_review_queue_entry,
    list_review_queue,
    update_review_queue_status,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="customer-support-agent",
    version="0.1.0",
    description=(
        "CrewAI-orchestrated hotel-domain customer support backend. "
        "POST /chat is implemented (Phase 1) — see "
        "project-context/2.build/backend.md for build history and scope."
    ),
)

# `@integration.eng`'s `*integrate-api` (2026-08-24) — dev-time CORS so the
# Vite frontend (a different origin: localhost:5173/5174) can call this API
# from the browser; without this, all frontend fetch() calls fail on the
# preflight/response before ever reaching a route (curl/server-to-server
# calls are unaffected — CORS is a browser-enforced restriction only, which
# is why this gap wasn't visible in @backend.eng's curl-based manual
# testing). sad.md does not pin an allowed-origins list, so this is a
# judgment call, documented in integration.md: default to the two Vite dev
# ports FastAPI/Vite actually use, override via `CORS_ALLOWED_ORIGINS` (a
# comma-separated list) for any other deployment target rather than
# hardcoding further origins here. No credentials/cookies are used by this
# MVP (no auth), so `allow_credentials=False`.
_default_cors_origins = "http://localhost:5173,http://localhost:5174"
_cors_allowed_origins = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", _default_cors_origins).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness/readiness probe required by sad.md §5 (DevOps & Deployment)."""
    return {"status": "ok"}


class CommonQuery(BaseModel):
    """One suggested guest-facing question, tied back to the KB entry it
    answers (so a frontend quick-reply chip can identify which topic it
    represents without duplicating the phrasing anywhere)."""

    kb_entry_id: str
    query: str


class TaxonomyEntry(BaseModel):
    """`GET /taxonomy` response item: one taxonomy category plus the
    suggested questions for it, for a frontend "common queries" quick-reply
    UI. Read-only, no request body."""

    intent: str
    label: str
    common_queries: list[CommonQuery]


@app.get("/taxonomy", response_model=list[TaxonomyEntry])
def get_taxonomy() -> list[TaxonomyEntry]:
    """Domain taxonomy + per-category suggested questions, for a chat
    quick-reply UI (e.g. "Reservations & Booking" -> "What is your
    cancellation policy?"). Deliberately reads the static, `lru_cache`d
    `domain_config.json` (`get_domain_config()`) directly, NOT the live
    mutable `knowledge_base` SQLite table `kb_search` uses (`app.persistence.
    knowledge_base`) — this endpoint surfaces the curated, seed-authored FAQ
    topics only; Reviewer-approved entries (`POST /review-queue/{id}/
    approve`) have no `example_query` and are not meant to appear here.
    KB entries without an `example_query` are simply omitted (a KB entry
    doesn't have to have one).
    """
    config = get_domain_config()
    result = []
    for taxonomy_entry in config.taxonomy:
        common_queries = [
            CommonQuery(kb_entry_id=kb_entry.kb_entry_id, query=kb_entry.example_query)
            for kb_entry in config.knowledge_base
            if kb_entry.intent == taxonomy_entry.intent and kb_entry.example_query
        ]
        result.append(
            TaxonomyEntry(
                intent=taxonomy_entry.intent,
                label=taxonomy_entry.label,
                common_queries=common_queries,
            )
        )
    return result


class ChatRequest(BaseModel):
    """sad.md §4 API Architecture: `POST /chat` request schema."""

    message: str
    session_id: str


class ChatResponse(BaseModel):
    """sad.md §4 API Architecture: `POST /chat` response schema."""

    reply: str
    escalated: bool


class ChatProcessingError(RuntimeError):
    """Raised when `run_inquiry`/`run_escalation_resolution` fail
    unexpectedly (not `run_inquiry`'s own internal timeout/escalation
    handling, which already degrades gracefully and returns a normal
    payload). Shared across `POST /chat`, `POST /email`, and `POST
    /escalations/{id}/resolve` — one error-envelope shape for every
    unexpected-failure case, per sad.md §4 `{error_code, message}`. Caught
    by `chat_processing_error_handler` below, so no stack trace ever
    reaches the client. Kept under its original Phase-1 name (`Chat...`)
    rather than renamed, to avoid an unrequested rename churning Phase 1's
    reviewed code — see backend.md Assumptions."""


@app.exception_handler(ChatProcessingError)
def chat_processing_error_handler(
    request: Request, exc: ChatProcessingError
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "chat_processing_failed",
            "message": "Something went wrong processing your request. Please try again.",
        },
    )


class EscalationNotFoundError(RuntimeError):
    """Raised when `POST /escalations/{id}/resolve`'s `{id}` doesn't match
    any persisted interaction-log record (see
    `app.flows.escalation_resolution_flow.OriginalInquiryNotFound`). Mapped
    to a 404 by `escalation_not_found_handler` below, using the same sad.md
    §4 `{error_code, message}` envelope shape as `ChatProcessingError`."""


@app.exception_handler(EscalationNotFoundError)
def escalation_not_found_handler(
    request: Request, exc: EscalationNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error_code": "original_inquiry_not_found",
            "message": str(exc),
        },
    )


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Triggers `InquiryFlow` with `channel=chat` (sad.md §4). Request
    validation (missing/wrong-typed fields) is handled by FastAPI/Pydantic
    automatically (422), per sad.md §4 "Validation: request schemas
    enforced (FastAPI/Pydantic)"."""
    try:
        result = run_inquiry(
            channel="chat",
            raw_text=request.message,
            sender_id=request.session_id,
        )
    except Exception as exc:  # noqa: BLE001 - deliberate catch-all at the API boundary
        logger.exception("Unexpected error from run_inquiry for /chat")
        raise ChatProcessingError(str(exc)) from exc

    return ChatResponse(reply=result["reply"], escalated=result["escalated"])


class EmailRequest(BaseModel):
    """sad.md §4 API Architecture: `POST /email` request schema.

    `from_` (Python can't name a field `from`, a reserved word) is bound to
    the JSON key `from` via `Field(alias=...)`; `populate_by_name=True`
    also allows constructing the model with the Python name directly
    (tests do this).
    """

    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(..., alias="from")
    subject: str
    body: str


class EmailResponse(BaseModel):
    """sad.md §4 API Architecture: `POST /email` response schema."""

    reply_body: str
    escalated: bool


@app.post("/email", response_model=EmailResponse)
def email(request: EmailRequest) -> EmailResponse:
    """Triggers `InquiryFlow` with `channel=email` (sad.md §4, Phase 2 of
    MVP Build Sequencing). `InquiryFlow.intake_normalize` already reads
    `channel` generically from `kickoff(inputs={...})` — no Flow changes
    were needed for this channel, only this route (see backend.md).

    Mapping from `{from, subject, body}` to `run_inquiry`'s
    `raw_text`/`sender_id` (a `@backend.eng` judgment call, documented in
    backend.md Assumptions — sad.md pins the request/response shape but
    not this mapping):
      - `sender_id = from` (the guest's identifying handle for this
        channel, same role `session_id` plays for `/chat`).
      - `raw_text = "Subject: {subject}\\n\\n{body}"` — both fields carry
        guest intent (a short subject like "Billing question" can matter
        for classification/PII-scan just as much as the body), so both are
        included rather than discarding `subject`; a plain, readable
        concatenation was chosen over a structured/templated format since
        `pii_guard`/the reasoning Crew only ever consume it as plain text.
    """
    raw_text = f"Subject: {request.subject}\n\n{request.body}"
    try:
        result = run_inquiry(
            channel="email",
            raw_text=raw_text,
            sender_id=request.from_,
        )
    except Exception as exc:  # noqa: BLE001 - deliberate catch-all at the API boundary
        logger.exception("Unexpected error from run_inquiry for /email")
        raise ChatProcessingError(str(exc)) from exc

    return EmailResponse(reply_body=result["reply"], escalated=result["escalated"])


class ResolveEscalationRequest(BaseModel):
    """sad.md §4 API Architecture: `POST /escalations/{id}/resolve`
    request schema."""

    resolution_text: str


class ResolveEscalationResponse(BaseModel):
    """`POST /escalations/{id}/resolve` response schema. sad.md §4 doesn't
    pin an exact response shape for this route ("Response shape isn't
    pinned by the SAD table exactly" per this run's task) — `status` +
    `review_queue_id` was chosen as the minimal useful confirmation that a
    candidate KB entry was queued, without exposing the full candidate
    record (Phase 3's `GET /review-queue` is the right place for that).
    Documented as a judgment call in backend.md Assumptions."""

    status: str
    review_queue_id: str


@app.post("/escalations/{id}/resolve", response_model=ResolveEscalationResponse)
def resolve_escalation(id: str, request: ResolveEscalationRequest) -> ResolveEscalationResponse:
    """Triggers `EscalationResolutionFlow` (sad.md §2, Phase 2 of MVP Build
    Sequencing) — writes a candidate KB entry to the review queue, linked
    to the original query (FR-008, AC-010). Does NOT touch the live KB;
    that stays exclusively Phase 3's Reviewer approve/reject path
    (NFR-008).

    The path `{id}` is taken as the `interaction_log` row `id` of the
    escalated interaction being resolved (a `@backend.eng` judgment call —
    sad.md's indicative table doesn't name a separate "escalation id"
    concept, and `InquiryFlow` already persists exactly one interaction-log
    row per inquiry with that `id`; see backend.md Assumptions). Returns
    404 (`original_inquiry_not_found`) if no such interaction-log record
    exists.
    """
    try:
        result = run_escalation_resolution(
            original_inquiry_id=id, resolution_text=request.resolution_text
        )
    except OriginalInquiryNotFound as exc:
        raise EscalationNotFoundError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - deliberate catch-all at the API boundary
        logger.exception("Unexpected error from run_escalation_resolution for /escalations/resolve")
        raise ChatProcessingError(str(exc)) from exc

    return ResolveEscalationResponse(
        status="queued", review_queue_id=result["review_queue_id"]
    )


class InteractionRecord(BaseModel):
    """sad.md §4: `GET /interactions` response item — one row per persisted
    interaction-log record. Field set and types mirror `interaction_log.py`
    `_SCHEMA` exactly (see that module for the authoritative column list),
    so FastAPI generates a real OpenAPI schema and validates responses
    instead of returning untyped dicts.

    Two deliberate, narrow typing choices beyond a literal column copy
    (documented here, not scope creep — no new data, no new columns):
    - `match_found`/`grounded` are `bool | None` rather than the SQLite
      column's raw `INTEGER` — `record_interaction` already stores them as
      `int(bool(...))`, so this just restores the semantic type on the way
      out.
    - `redaction_actions` is `list[dict[str, Any]]` rather than the raw
      `TEXT` column's JSON string — the route below `json.loads()`s it
      before constructing this model, since a JSON-string-typed API field
      would defeat the purpose of a typed response model / OpenAPI schema.
    """

    id: str
    created_at: str
    channel: str
    sender_id: str
    query_text: str
    intent: str | None = None
    confidence: float | None = None
    sentiment_score: float | None = None
    sentiment_label: str | None = None
    match_found: bool | None = None
    grounded: bool | None = None
    response_text: str | None = None
    outcome: str
    redaction_count: int
    redaction_actions: list[dict[str, Any]] = []
    diagnostic: str | None = None


@app.get("/interactions", response_model=list[InteractionRecord])
def get_interactions() -> list[InteractionRecord]:
    """sad.md §4: `GET /interactions` — interaction log for the ops view.

    Deliberate Phase 3 -> now pull-forward (operator decision, see
    backend.md and main.py's module docstring above). No query params,
    pagination, or filtering — sad.md's contract line for this endpoint
    ("interaction log for the ops view") specifies none for MVP, and none
    are invented here. Delegates directly to
    `app.persistence.interaction_log.list_interactions()`, which already
    returns rows most-recent-first.
    """
    rows = list_interactions()
    for row in rows:
        row["redaction_actions"] = json.loads(row["redaction_actions"])
    return [InteractionRecord(**row) for row in rows]


class ReviewQueueItem(BaseModel):
    """sad.md §4: `GET /review-queue` response item — one row per queued
    candidate KB entry (`EscalationResolutionFlow`'s write, sad.md §2 /
    FR-008/AC-010), field set mirrors `review_queue.py`'s schema exactly."""

    id: str
    created_at: str
    original_inquiry_id: str
    original_query_text: str | None = None
    resolution_text: str
    candidate_intent: str | None = None
    candidate_section: str | None = None
    candidate_keywords: list[str] = []
    candidate_content: str
    status: str


class ReviewQueueNotFoundError(RuntimeError):
    """Raised when `{id}` in `POST /review-queue/{id}/approve` or `.../reject`
    doesn't match any persisted `review_queue` record. Mapped to 404 by
    `review_queue_not_found_handler` below, same `{error_code, message}`
    envelope convention as `EscalationNotFoundError`."""


@app.exception_handler(ReviewQueueNotFoundError)
def review_queue_not_found_handler(
    request: Request, exc: ReviewQueueNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error_code": "review_queue_entry_not_found", "message": str(exc)},
    )


class ReviewQueueConflictError(RuntimeError):
    """Raised when approve/reject is called against a `review_queue` row
    that has already been actioned (`status != 'pending'`). A `@backend.eng`
    judgment call (sad.md leaves this open) — re-approving/re-rejecting is
    treated as a 409 Conflict, not a silent no-op, because approve has a
    real side effect (a live-KB write) that must not be repeatable/
    ambiguous: idempotent-safe re-approval would either silently write a
    second KB entry for the same candidate or require yet another dedup
    key, and NFR-008's "no path to the live KB except explicit human
    approval" reads more safely as "each approval decision happens exactly
    once" than as "approving twice is harmless." See backend.md
    Assumptions."""


@app.exception_handler(ReviewQueueConflictError)
def review_queue_conflict_handler(request: Request, exc: ReviewQueueConflictError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"error_code": "review_queue_already_actioned", "message": str(exc)},
    )


class InvalidApprovalError(RuntimeError):
    """Raised when the fields that would form the new KB entry (after
    applying any Reviewer overrides on top of the queued candidate's stored
    values) are missing a required piece — specifically `intent`/`content`
    empty or absent. Mapped to 422, same envelope convention."""


@app.exception_handler(InvalidApprovalError)
def invalid_approval_handler(request: Request, exc: InvalidApprovalError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error_code": "invalid_kb_entry", "message": str(exc)},
    )


@app.get("/review-queue", response_model=list[ReviewQueueItem])
def get_review_queue() -> list[ReviewQueueItem]:
    """sad.md §4: `GET /review-queue` — list all queued candidate entries
    (pending + approved + rejected), most recent first. sad.md doesn't
    specify a status filter for this endpoint, so none is invented here —
    the `/ops` view (sad.md §3) is expected to filter/group client-side if
    it wants to. Delegates directly to
    `app.persistence.review_queue.list_review_queue()`.
    """
    rows = list_review_queue()
    return [ReviewQueueItem(**row) for row in rows]


class ApproveReviewQueueRequest(BaseModel):
    """`POST /review-queue/{id}/approve` request body — sad.md §2 step 2:
    "Approve (optionally edited) -> entry written to live KB". All fields
    are optional overrides; any field left unset falls back to the queued
    candidate's stored `candidate_*` value. `keywords` in particular
    matters in practice: ADR-005's keyword-overlap scoring means an entry
    approved with empty keywords can never actually be retrieved (a
    0-length `entry.keywords` list is skipped by `kb_search` outright).
    `EscalationResolutionFlow` now auto-derives `candidate_keywords` at
    queue-time (`domain/loader.py::derive_keywords`) so this usually isn't
    empty to begin with, and this route re-derives as a fallback if it
    still is after applying any override (see `approve_review_queue_entry`
    below) — a Reviewer supplying `keywords` here remains the way to
    override that default, not the only way to get a retrievable entry."""

    intent: str | None = None
    section: str | None = None
    keywords: list[str] | None = None
    content: str | None = None


class KBEntryResponse(BaseModel):
    """The resulting live KB entry, mirrors `domain/loader.py::KBEntry`'s
    shape exactly (same 5 fields ADR-005 pins)."""

    kb_entry_id: str
    intent: str
    section: str
    keywords: list[str]
    content: str


@app.post("/review-queue/{id}/approve", response_model=KBEntryResponse)
def approve_review_queue_entry(id: str, request: ApproveReviewQueueRequest) -> KBEntryResponse:
    """sad.md §2 step 2: "Approve (optionally edited) -> entry written to
    live KB, retrievable by knowledge_retriever from that point on (FR-014,
    AC-011)." The only route in the system that writes to
    `app.persistence.knowledge_base` (NFR-008).

    404 (`review_queue_entry_not_found`) if `{id}` doesn't exist. 409
    (`review_queue_already_actioned`) if the row isn't `status='pending'`
    (see `ReviewQueueConflictError`). 422 (`invalid_kb_entry`) if the
    resulting entry would have an empty `intent`/`content` even after
    applying overrides (e.g. the queued candidate's `candidate_intent` was
    never populated and the Reviewer didn't supply one either).
    """
    row = get_review_queue_entry(id)
    if row is None:
        raise ReviewQueueNotFoundError(f"No review_queue record found for id={id!r}")
    if row["status"] != "pending":
        raise ReviewQueueConflictError(
            f"review_queue entry id={id!r} has already been actioned "
            f"(status={row['status']!r}); re-approval is not permitted"
        )

    intent = request.intent if request.intent is not None else row["candidate_intent"]
    section = request.section if request.section is not None else row["candidate_section"]
    keywords = request.keywords if request.keywords is not None else row["candidate_keywords"]
    content = request.content if request.content is not None else row["candidate_content"]

    if not intent or not content:
        raise InvalidApprovalError(
            "Cannot approve: the resulting KB entry needs a non-empty 'intent' and "
            "'content' — the queued candidate is missing one and no override was "
            "supplied in the request body."
        )

    kb_entry_id = f"kb-approved-{uuid.uuid4().hex[:12]}"
    final_section = section or "operator_resolution"
    # Safety net, not the primary mechanism: `EscalationResolutionFlow` now
    # auto-derives `candidate_keywords` at queue-time (domain/loader.py::
    # derive_keywords), so this branch should rarely fire for new
    # candidates. It still exists for: candidates queued before that fix,
    # a Reviewer who explicitly clears the keywords field, or a query/
    # resolution pairing whose text shares nothing with its intent's
    # taxonomy keywords. Writing a KB entry with `keywords=[]` makes it
    # permanently unretrievable (ADR-005, `kb_search` skips zero-keyword
    # entries outright) — better to attempt one more deterministic
    # derivation here than silently accept a dead entry.
    final_keywords = keywords or derive_keywords(
        intent, [row["original_query_text"] or "", content]
    )
    entry: dict[str, Any] = {
        "kb_entry_id": kb_entry_id,
        "intent": intent,
        "section": final_section,
        "keywords": final_keywords,
        "content": content,
    }
    insert_kb_entry(entry)
    update_review_queue_status(id, "approved")

    return KBEntryResponse(
        kb_entry_id=kb_entry_id,
        intent=intent,
        section=final_section,
        keywords=final_keywords,
        content=content,
    )


class RejectReviewQueueResponse(BaseModel):
    """`POST /review-queue/{id}/reject` response schema."""

    id: str
    status: str


@app.post("/review-queue/{id}/reject", response_model=RejectReviewQueueResponse)
def reject_review_queue_entry(id: str) -> RejectReviewQueueResponse:
    """sad.md §2 step 3: "Reject -> entry discarded, KB unchanged." No
    request body — a rejection carries no editable content. Same 404/409
    handling as approve (see `approve_review_queue_entry`)."""
    row = get_review_queue_entry(id)
    if row is None:
        raise ReviewQueueNotFoundError(f"No review_queue record found for id={id!r}")
    if row["status"] != "pending":
        raise ReviewQueueConflictError(
            f"review_queue entry id={id!r} has already been actioned "
            f"(status={row['status']!r}); re-rejection is not permitted"
        )

    update_review_queue_status(id, "rejected")
    return RejectReviewQueueResponse(id=id, status="rejected")
