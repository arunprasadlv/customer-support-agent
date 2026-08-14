"""FastAPI application entrypoint (scaffold only).

Scaffolded by @project.mgr (*setup-project) per sad.md §4 (Backend
Architecture Specification) and §5 (DevOps & Deployment Architecture,
which requires a `/health` endpoint).

Only `/health` is implemented here. The remaining API contract
(`POST /chat`, `POST /email`, `POST /escalations/{id}/resolve`,
`GET /review-queue`, `POST /review-queue/{id}/approve`,
`POST /review-queue/{id}/reject`, `GET /interactions`) is
@backend.eng's responsibility (sad.md §4) — do not add route logic here.
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(
    title="customer-support-agent",
    version="0.1.0",
    description=(
        "CrewAI-orchestrated hotel-domain customer support backend. "
        "Scaffold stage: only /health is implemented — see "
        "project-context/2.build/backend.md once @backend.eng runs *develop-be."
    ),
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness/readiness probe required by sad.md §5 (DevOps & Deployment)."""
    return {"status": "ok"}


# TODO(@backend.eng): register InquiryFlow / EscalationResolutionFlow-backed
# routers here (POST /chat, POST /email, POST /escalations/{id}/resolve,
# GET /review-queue, POST /review-queue/{id}/approve,
# POST /review-queue/{id}/reject, GET /interactions). See sad.md §4.
