# syntax=docker/dockerfile:1
#
# Backend container for customer-support-agent (sad.md §5: "single-service
# local/dev target for MVP demo"). Single stage — the backend is pure
# Python (fastapi/uvicorn/pydantic/crewai/python-dotenv/jsonschema/pyyaml,
# see pyproject.toml), no compiled-asset build step needed, unlike the
# frontend's Node build → static-serve split.
FROM python:3.11.11-slim-bookworm AS runtime

WORKDIR /app

# Only the files needed to install the package and run it — backend/.venv,
# tests/, data/, and local dev artifacts are excluded via .dockerignore so
# they never enter the build context.
COPY pyproject.toml ./
COPY src ./src

# Runtime-only install (no [dev] extra — pytest/ruff/mypy stay out of the
# shipped image; qa.md's gate already ran them locally/in CI, not here).
RUN pip install --no-cache-dir .

# backend/data/app.db (SQLite — interaction_log/knowledge_base/review_queue,
# per interaction_log.py _BACKEND_ROOT/data/app.db default) and the Trace
# Log directory (trace_log.py _REPO_ROOT/project-context/2.build/logs
# default) are both repointed to absolute, volume-mountable paths here
# instead. Reason: both defaults are computed via Path(__file__).resolve()
# .parents[N] — an inferred repo-root walk that assumes the exact on-disk
# nesting of a checked-out working copy (backend/ two levels under the
# repo root). That assumption breaks once source is copied into a
# container image with a different layout, so this image pins both paths
# explicitly via the app's existing env-var overrides
# (INTERACTION_LOG_DB_PATH, TRACE_LOG_DIR) rather than relying on the
# inferred defaults resolving to something sane. docker-compose.yml mounts
# named volumes at these exact paths so data survives container restarts.
ENV INTERACTION_LOG_DB_PATH=/app/data/app.db
ENV TRACE_LOG_DIR=/app/logs

# Documentation only — EXPOSE does not publish or bind a port at runtime,
# it's metadata for humans/tooling (e.g. `docker inspect`). It does not
# need to track $PORT and is left at the conventional default.
EXPOSE 8000

# sad.md §5: "/health endpoint required". Reads $PORT the same way the CMD
# below does (os.environ.get, not shell substitution — HEALTHCHECK CMD
# runs the command through /bin/sh -c either way, and the container's env
# vars, including PORT, are visible to the Python process regardless), so
# the healthcheck keeps probing the port uvicorn actually bound, whatever
# that is. Used directly as this container's healthcheck and as
# docker-compose's `service_healthy` gate for the frontend's `depends_on`.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/health', timeout=3)" || exit 1

# Railway (the operator-chosen host, see deploy.md's *define-deploy entry)
# assigns each service a dynamic $PORT at runtime and routes external
# traffic — and its own healthcheck probes — to whatever port the
# container actually listens on. A CMD hardcoded to --port 8000 would
# silently fail to receive any traffic whenever Railway's assigned port
# isn't 8000 (the common case), breaking the deployment outright, not just
# leaving it suboptimal. Shell form (not the ["exec", "form"] array) is
# required here so ${PORT:-8000} actually gets expanded — Docker only
# does that substitution when CMD runs via /bin/sh -c. Falls back to 8000
# when $PORT isn't set (local `docker run`/docker-compose use, where
# nothing injects PORT) — matches backend/.env.example's documented local
# default and setup.md's local-dev instructions, and leaves
# docker-compose.yml's existing `${BACKEND_HOST_PORT:-8000}:8000` mapping
# correct as-is (compose doesn't set PORT either, so the container still
# listens on 8000 in that path). ${VAR:-default} is POSIX parameter
# expansion (not a bashism) — this image's /bin/sh is dash (Debian
# default), which supports it natively.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --app-dir src
