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

The rest of the API contract (`GET /review-queue`, `POST
/review-queue/{id}/approve`, `POST /review-queue/{id}/reject` — the sole
KB-write path, NFR-008) remains explicitly out of scope (sad.md §4, Phase
3 of MVP Build Sequencing) — do not add route logic for those here.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

# Load backend/.env (ANTHROPIC_API_KEY, etc.) into the process environment
# before anything below might need it (sad.md §4 Authentication & Secrets:
# "API key via env var only"). python-dotenv is already a declared
# dependency (pyproject.toml) but was previously unused.
load_dotenv()

from app.flows.escalation_resolution_flow import (  # noqa: E402
    OriginalInquiryNotFound,
    run_escalation_resolution,
)
from app.flows.inquiry_flow import run_inquiry  # noqa: E402
from app.persistence.interaction_log import list_interactions  # noqa: E402

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


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness/readiness probe required by sad.md §5 (DevOps & Deployment)."""
    return {"status": "ok"}


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
