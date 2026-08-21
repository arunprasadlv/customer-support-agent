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

The rest of the API contract (`POST /email`, `POST /escalations/{id}/
resolve`, `GET /review-queue`, `POST /review-queue/{id}/approve`,
`POST /review-queue/{id}/reject`) remains explicitly out of scope (sad.md
§4, Phase 2/3 of MVP Build Sequencing) — do not add route logic for those
here.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Load backend/.env (ANTHROPIC_API_KEY, etc.) into the process environment
# before anything below might need it (sad.md §4 Authentication & Secrets:
# "API key via env var only"). python-dotenv is already a declared
# dependency (pyproject.toml) but was previously unused.
load_dotenv()

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
    """Raised when `run_inquiry` fails unexpectedly (not its own internal
    timeout/escalation handling, which already degrades gracefully and
    returns a normal payload). Caught by `chat_processing_error_handler`
    below and mapped to the sad.md §4 `{error_code, message}` error
    envelope, so no stack trace ever reaches the client."""


@app.exception_handler(ChatProcessingError)
def chat_processing_error_handler(
    request: Request, exc: ChatProcessingError
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "chat_processing_failed",
            "message": "Something went wrong processing your message. Please try again.",
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
