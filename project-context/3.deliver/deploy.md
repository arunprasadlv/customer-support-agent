# Deploy

> **Update (2026-09-02): Phase Gate now satisfied — see "Release Readiness (`*prepare-release`)" below.** The original 2026-09-01 Diagnostic/Halt (preserved below for history, per this project's repeated-dated-entry convention already used in `qa.md`/`security.md`) recorded that Deliver work could not start because `qa.md` and `security.md` did not exist. Both now exist, both were independently re-verified, and both recommend proceeding. `*define-deploy`/`*configure-cicd`/`*document-deploy` have not been run yet — this update is `*prepare-release` only.

## Release Readiness (`*prepare-release`, 2026-09-02)

### QA Gate — confirmed

`project-context/2.build/qa.md` exists, containing two dated passes (2026-09-01 original, 2026-09-02 fresh re-run triggered by this session's new work). Per the fresh pass:

- Backend automated suite: **150/150 passing**, 0 failed (`pytest -q`, real live Anthropic API calls, no skips). `ruff` clean (1 pre-existing, non-regressing nit). `mypy` clean, 20 files (the 2026-09-01 broken-mypyc environment defect is resolved).
- Frontend: `npm run lint`/`npm run build` both clean. No automated frontend test runner exists (`package.json` has no `test` script) — confirmed, unchanged gap.
- Acceptance criteria: **9 of 11 pass on direct automated evidence**; AC-005/AC-009 are architectural-review criteria `sad.md` itself scopes outside automated testing, not failures.
- The dispute/chargeback escalation fix (this session's headline change) was verified **live end-to-end**, not just via unit tests: a real `POST /chat` with the original bug-report message now returns `escalated: true`, cross-checked against `GET /interactions`/`GET /interactions/{id}/trace`.
- `sad.md`'s ADR-002 Addendum and its downstream §2/Typed-Task-Outputs edits are internally consistent with shipped code — no SAD-drift repeat of the `MAX_EXECUTION_TIME_SECONDS` pattern.

**Known gaps, explicitly carried forward (not silently dropped) — per `delivery-workflow.md`'s "pass or explicitly scoped known gaps" standard, these require operator sign-off, not `@devops.eng` resolution:**
1. **SAD §7 latency gate still open.** No clean 20+-request/4-category spike has ever completed (14/20 in the 2026-08-22 formal spike, 8/8 in a 2026-09-01 supplementary probe — different methodology, not a substitute). Every real measurement to date (22+ data points) exceeds both the 5s target and the 10s SAD-stated ceiling.
2. **Undocumented `MAX_EXECUTION_TIME_SECONDS = 30` vs. `sad.md`'s stated 10s** — a 2026-08-24 operator-directed deviation recorded only in a code comment and commit message, never formally reconciled with `sad.md` §7's text. Unlike the ADR-002 escalation change (which *was* properly amended into the SAD this session), this ceiling deviation remains un-amended.
3. **Zero automated frontend tests** — `aamad.config.yml`'s `testing.require_unit_tests`/`require_integration_tests` is satisfied on the backend only.

### Security Gate — confirmed

`project-context/2.build/security.md` exists. Current severity: **Critical 0 · High 0 · Medium 3 · Low 3 · Info 3** (the original High finding — unredacted exception text in fail-closed diagnostic logging — was fixed by `@backend.eng` and independently re-verified by `@security.eng` this session). `@security.eng`'s updated recommendation: **proceed to `@devops.eng`**.

**Medium findings carried forward as accepted/flagged, not blocking:**
1. No prompt-injection defenses on guest text reaching agent task prompts (bounded blast radius — escalation gate only reads four typed scalars).
2. `sad.md` §8 claims encryption-at-rest for PII-adjacent data that isn't implemented (plain SQLite).
3. Trace Log's redaction is pattern-based (same four categories as `pii_detector.py`), not a general PII classifier.

### Release Scope Summary

MVP hotel guest-support agent (branch `devops`, commit `350059a`, 2026-09-02) — CrewAI-based 4-agent reasoning pipeline (classify → retrieve → sentiment → compose) plus a standalone fail-closed PII guard, fronted by a FastAPI backend and a React/Vite `/chat`, `/inbox`, `/ops` frontend. This release adds, on top of the previously-delivered chat/email/escalation/KB-review functionality:
- A Trace Log recording every LLM/tool call per interaction (`GET /interactions/{id}/trace`), satisfying the previously-unimplemented `adapter-crewai.md` Logging requirement.
- Per-step latency pass/fail against `sad.md` §7's existing 5s/10s thresholds, surfaced in a new `/ops` trace-timeline dashboard panel with a "slowest step" highlight.
- A fourth, deterministic escalation condition (`dispute_language_detected`, ADR-002 Addendum) fixing a real false-negative where dispute/chargeback threats weren't escalating.
- A security fix for unredacted exception text in fail-closed diagnostic logging.

### Version

No formal release-versioning scheme currently exists: `backend/pyproject.toml` is at `0.1.0` (unbumped since scaffold), `frontend/package.json` is at the Vite-scaffold default `0.0.0`. **Recommendation for `*define-deploy`**: adopt an explicit version (e.g. `0.2.0` given the functional additions above) across both, and consider tagging the release commit — not done here, `*prepare-release` is a readiness check, not a version bump.

### Next steps

Phase Gate is satisfied — `*define-deploy`, `*configure-cicd`, and `*document-deploy` can now proceed. Not run as part of this action.

## Deploy Configuration (`*define-deploy`, 2026-09-02)

### Hosting decision: Railway

`sad.md` §5 left "Specific cloud target" as an explicit Open Question for `@devops.eng` to propose. **The operator has since made this decision directly: Railway (railway.com).** This is recorded here as an operator decision, not a `@devops.eng` proposal being adopted unilaterally — it resolves that Open Question. Everything below is shaped around Railway's actual execution model, which is per-service Dockerfile builds wired together via Railway's own dashboard/env-var/networking layer — **not** `docker compose up`. This still matches `sad.md` §5's "single-service local/dev target for MVP demo" framing in spirit: two small Railway services (backend, frontend), no orchestration platform, no IaC, no multi-region.

### Files created this action

| File | Purpose |
|---|---|
| `backend/Dockerfile` | Backend container: `python:3.11.11-slim-bookworm`, installs `pyproject.toml` (runtime deps only, no `[dev]` extra), runs `uvicorn app.main:app` bound to `$PORT` (falling back to 8000 when unset, e.g. local `docker run`/compose). This is what both Railway and local `docker compose` build from. |
| `backend/.dockerignore` | Keeps `backend/.venv/`, `tests/`, `data/`, caches, and `.env` out of the build context. |
| `backend/railway.json` | Railway per-service config: `builder: DOCKERFILE`, `dockerfilePath: Dockerfile`, `healthcheckPath: /health` (sad.md §5's required endpoint, used directly as Railway's own health probe), a bounded `ON_FAILURE` restart policy. Railway-native declarative config for one service — not IaC in the multi-region/Terraform sense `sad.md` rules out. |
| `frontend/Dockerfile` | Frontend container, two stages: `node:22.12.0-bookworm-slim` builds the Vite production bundle, `nginx:1.27.3-alpine` serves the static `dist/` output. No Node runtime ships in the final image. |
| `frontend/nginx.conf` | SPA fallback (`try_files ... /index.html`) so `/chat`, `/inbox`, `/ops` (React Router `BrowserRouter`) resolve on direct navigation/refresh, not a raw 404. |
| `frontend/.dockerignore` | Keeps `node_modules/`, `dist/`, `.env*` out of the build context. |
| `frontend/railway.json` | Railway per-service config for the frontend: `builder: DOCKERFILE`, bounded restart policy. No `healthcheckPath` set — Railway falls back to a TCP check on the exposed port, which is sufficient for a static file server (see Docker `HEALTHCHECK` in the Dockerfile for the container-level check). |
| `docker-compose.yml` (repo root) | **Local/dev convenience only** — builds and runs both Dockerfiles together for laptop testing, using named volumes (see below). Explicitly documented in its own header comment as not the Railway deploy mechanism. |
| `.env.docker.example` (repo root) | Committed template for `docker-compose.yml`'s env vars. Operator copies to `.env.docker` (already covered by the repo's existing `.env.*` gitignore rule) and fills in real values — never `backend/.env` itself, and never read by Railway. |
| `.gitignore` (edited) | Added `!.env.docker.example` alongside the existing `!.env.example` exception, so the new committed template isn't swept up by the `.env.*` ignore rule. No other lines changed. |

**Why Dockerfile-per-service instead of Railway's Nixpacks auto-build**: both services already have an explicit, reviewed dependency surface (`pyproject.toml`, `package.json`+`package-lock.json`) and the backend needs a precise runtime-only install (excluding `[dev]` extras) that a fully automatic buildpack wouldn't distinguish. A Dockerfile is also what makes `docker-compose.yml` possible for local parity testing — one build definition, two execution contexts (local compose, Railway).

**Why nginx-served static build instead of Railway's native static-site hosting**: keeps exactly one deploy artifact (`frontend/Dockerfile`) that behaves identically locally (via compose) and on Railway, rather than a Railway-only static-hosting path with no local equivalent. Noted as a real alternative Railway offers, not chosen here for that consistency reason.

### Railway service setup (manual, dashboard-driven — not run by this action)

No Railway account, project, or live deploy was created or attempted — no credentials exist for that in this environment, and per `delivery-workflow.md`'s Continuous Deployment Policy, `@devops.eng` generates config only, never triggers live deploys. The following are the manual steps an operator follows in the Railway dashboard:

1. Create a Railway project; add **two services** from this same GitHub repo (monorepo), each with a different **Root Directory**:
   - Service `backend` → root directory `backend/`. Railway detects `backend/Dockerfile` (via `backend/railway.json`'s `dockerfilePath: Dockerfile`, relative to that root) and builds it.
   - Service `frontend` → root directory `frontend/`. Same mechanism, `frontend/Dockerfile`.
2. **Backend service environment variables** (set in Railway's dashboard, never committed):
   - `ANTHROPIC_API_KEY` — required, entered as a Railway secret/variable directly (sad.md §4, `security.md` INFO-1's standard: real values never appear in this repo, `.env.example`, or any artifact — only the variable *name* is documented).
   - `CORS_ALLOWED_ORIGINS` — set to the frontend service's Railway-assigned public URL (e.g. `https://<frontend-service>.up.railway.app`) once that URL is known from step 1. Defaults in code to the Vite dev-server ports, which don't apply once both services are deployed (`backend/src/app/main.py`'s `_default_cors_origins`).
   - `INTERACTION_LOG_DB_PATH` = `/app/state/data/app.db` and `TRACE_LOG_DIR` = `/app/state/logs` — **different from the `docker-compose.yml`/local values** (`/app/data`, `/app/logs`) because of the Volumes constraint below; both are already-supported env-var overrides (`interaction_log.py`, `knowledge_base.py`, `review_queue.py` share `INTERACTION_LOG_DB_PATH`; `trace_log.py` reads `TRACE_LOG_DIR`), no code change needed.
   - **Railway `$PORT` — resolved, not an operator action item.** Railway assigns each service a dynamic `$PORT` at runtime and routes external traffic (and its own healthcheck probes) to whatever port the container actually listens on — a hardcoded `--port 8000` would silently receive no traffic whenever Railway's assigned port isn't 8000 (the common case), breaking the deployment outright. `backend/Dockerfile`'s `CMD` now runs in shell form, `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --app-dir src`, so it binds to whatever `$PORT` Railway injects and falls back to 8000 only when nothing sets it (local `docker run`/`docker-compose`, where the fallback matches the app's pre-existing local-dev default and needs no other change). The `HEALTHCHECK` instruction was updated the same way (`os.environ.get('PORT', '8000')` inside the Python one-liner) so the container-level check keeps probing the right port too. No operator action needed for this — nothing to set in the Railway dashboard beyond leaving `PORT` alone (Railway manages it automatically). Verified locally: built the exact shell-form command through `/bin/sh -c` with `PORT=9123` exported and confirmed `uvicorn` actually bound to `0.0.0.0:9123` (a real `GET /health` on 9123 returned `200`, an unrelated control port returned nothing); separately ran the `HEALTHCHECK` Python one-liner with `PORT` matching a live server (succeeded) and with `PORT` pointed at a genuinely empty port (failed with a connection timeout, non-zero exit) — see Audit for the exact commands. `EXPOSE 8000` in the Dockerfile is unchanged and doesn't need to track `$PORT` — it's documentation only and does not affect runtime port binding; `backend/railway.json`'s `healthcheckPath: /health` also needs no port, since Railway probes whatever port it already assigned to the service internally.
3. **Frontend service environment variables**:
   - `VITE_API_BASE_URL` — set to the backend service's Railway-assigned public URL (e.g. `https://<backend-service>.up.railway.app`). **This must be set before the frontend service's first build**, not just before it starts running: Vite inlines every `VITE_`-prefixed variable into the static JS bundle at `vite build` time (confirmed against `frontend/Dockerfile`'s `ARG VITE_API_BASE_URL` → `ENV` → `RUN npm run build` sequence — there is no runtime read of this value once the bundle is built). Railway is documented to pass a service's configured variables through as build args for Dockerfile-based builds when the Dockerfile declares a matching `ARG` name (exactly what `frontend/Dockerfile` does) — **this project has not verified that behavior against a live Railway build**, so treat it as the expected mechanism, not a confirmed one; see Open Questions.
   - Changing `VITE_API_BASE_URL` later requires a new Railway build/redeploy of the frontend service, not just a restart — same constraint as the local compose setup.
4. Confirm the backend service's health check: `backend/railway.json` already sets `healthcheckPath: /health`; verify in the dashboard that Railway is using it (it should auto-detect from `railway.json`).

### Persistent data on Railway

Both `backend/data/` (SQLite — `interaction_log`, `knowledge_base`, `review_queue` tables, all in one `app.db` file) and `project-context/2.build/logs/` (Trace Log JSONL, `adapter-crewai.md` Logging requirement) must not live on Railway's ephemeral container filesystem, or all data is lost on every redeploy/restart.

- Railway supports attaching a **Volume** to a service, mounted at one path. **Constraint**: Railway allows one Volume per service (as of this writing) — this app needs two distinct writable locations (`.db` file, log directory). Resolution: mount a single Volume at `/app/state` on the backend service, then set `INTERACTION_LOG_DB_PATH=/app/state/data/app.db` and `TRACE_LOG_DIR=/app/state/logs` (both already-supported env-var overrides, per step 2 above) so both live as subdirectories of the one mounted volume. No code change required — this is purely a deploy-time path choice, the same mechanism `docker-compose.yml`'s two separate named volumes use locally (compose has no such one-volume limit, so the local and Railway path layouts intentionally differ).
- The frontend service is stateless (a static build served by nginx) — no volume needed.
- **Known, flagged, non-blocking constraint**: a single SQLite file assumes a single writer/single backend instance. Railway horizontal scaling (multiple instances of the backend service) would risk concurrent-write corruption on `app.db` — not safe without moving to a real client-server database first. `sad.md` §7 already scopes concurrency as "not a design driver for MVP (no real traffic) — single-process FastAPI is sufficient" and scaling as "deferred entirely (Out of Scope)," so this isn't a new gap introduced by choosing Railway — just made explicit here so it's a known constraint, not a silent one, if the operator is ever tempted to bump the Railway service's replica count.

### Secrets handling

No real secret values appear anywhere in this repo or in this artifact (`security.md` INFO-1's standard, `aamad.config.yml` `security.forbid_committed_secrets: true`). `ANTHROPIC_API_KEY` is documented by name only (`backend/.env.example`, this section, `.env.docker.example`) and is supplied by the operator directly into Railway's dashboard for the live deploy, or into a local, gitignored `.env.docker` file for `docker-compose` testing — both paths never touch git.

### Version

No version bump was performed (see `*prepare-release`'s recommendation above, not acted on by this action either — still not this command's job). `backend/pyproject.toml` remains `0.1.0`, `frontend/package.json` remains `0.0.0`. Locally-built compose images are tagged `:local` (not a semantic version, not `:latest`) to avoid implying a version bump that hasn't actually happened.

### Explicitly NOT built (confirms SAD Future Work stayed out of scope)

- No Kubernetes manifests, no Terraform/CloudFormation/other IaC, no multi-region configuration — `railway.json` is Railway-native per-service declarative config, not general-purpose IaC.
- No APM/advanced monitoring — observability stays exactly `sad.md` §5's baseline (structured logs + `/health`), unchanged by this action. Railway's own platform-level logs/metrics (visible in its dashboard) are Railway's existing product surface, not something this action added.
- No CI/CD pipeline — that is `*configure-cicd`, a separate, later Deliver-module step, not run here.
- No runbook/user-guide content — that is `*document-deploy`, likewise not run here.
- No live Railway project, service, or deploy was created.

### Sources

- `project-context/1.define/sad.md` §5 (DevOps & Deployment Architecture — hosting scope, `/health` requirement, IaC/APM Future Work)
- `project-context/2.build/setup.md` (local dev commands, `backend/.venv` Python 3.11.16, dependency install/run instructions)
- `backend/pyproject.toml` (`requires-python = ">=3.11,<3.15"`, dependency list, version `0.1.0`)
- `backend/.env.example`, `frontend/.env.example` (required/optional env vars)
- `frontend/package.json` (Node-dependent scripts, version `0.0.0`, no `engines`/`.nvmrc` pin found — Node version chosen independently, see Assumptions)
- `backend/src/app/main.py` (`GET /health` at line ~125; `CORS_ALLOWED_ORIGINS` env var and its dev-port default at `_default_cors_origins`)
- `backend/src/app/persistence/interaction_log.py`, `knowledge_base.py`, `review_queue.py` (shared `INTERACTION_LOG_DB_PATH` env var, default `backend/data/app.db` via a `Path(__file__).resolve().parents[3]` repo-root inference)
- `backend/src/app/persistence/trace_log.py` (`TRACE_LOG_DIR` env var, default `project-context/2.build/logs` via `parents[4]` repo-root inference)
- `project-context/2.build/security.md` (INFO-1 standard for never committing real secret values, cited above)
- `project-context/3.deliver/deploy.md`'s own `*prepare-release` (2026-09-02) Release Readiness section, read in full before this action, per this action's own instructions
- Operator instruction (2026-09-02, relayed mid-action): Railway as the chosen hosting target, resolving `sad.md` §5's Open Question

### Assumptions

- Railway passes a Dockerfile-build service's dashboard-configured variables through as build-time `ARG`s when the Dockerfile declares a matching `ARG` name (used for `VITE_API_BASE_URL`) — this is Railway's documented behavior as of this action's knowledge, but has **not** been verified against a live Railway build in this session (no Railway credentials/access here). Flagged again under Open Questions.
- Base image versions (`python:3.11.11-slim-bookworm`, `node:22.12.0-bookworm-slim`, `nginx:1.27.3-alpine`) are pinned, real, current-as-of-writing minor/patch releases chosen to satisfy "pin specific versions, not `:latest`" — not stakeholder-confirmed, and not re-verified against the actual current latest patch at deploy time. An operator should bump these periodically for security patches; that is routine maintenance, not a new Future Work item.
- Railway's default single-volume-per-service limit was assumed accurate for this action (based on general Railway product knowledge, not re-verified live) — if Railway has since added multi-volume support, the single-`/app/state`-root approach documented above still works (it's a valid layout either way), it just becomes unnecessary rather than wrong.
- `docker-compose.yml` and `.env.docker.example` are provided as a genuine local-testing convenience, not a second, competing deploy target — Railway is the one hosting decision recorded here, per the operator's instruction.

### Open Questions

- **Not yet verified**: whether Railway actually forwards dashboard-set variables as build `ARG`s for a Dockerfile-based service build (affects whether `VITE_API_BASE_URL` reaches the frontend build the way this action assumes). First real Railway deploy attempt should confirm this before assuming the frontend is correctly wired.
- Carried forward, unresolved, from `sad.md`/this file's earlier entries: actual project budget; which PII regulation (if any) must ultimately be complied with; the SAD §7 latency gate (still open per `*prepare-release`'s Known gap 1) and the undocumented `MAX_EXECUTION_TIME_SECONDS` deviation (Known gap 2) — neither is a deploy-config concern, both remain the operator's/`@backend.eng`'s to resolve.
- Whether the operator wants a Railway volume snapshot/backup policy for `app.db` (Railway supports volume backups on some plans) — not specified, not assumed here; SQLite's single-writer constraint (above) makes this more important than it would be for a real managed database, but configuring it is a dashboard action outside this artifact's scope.

### Audit

- **Timestamp**: 2026-09-02
- **Persona**: `@devops.eng`
- **Action**: `*define-deploy`
- **Resolved runtime**: `crewai` (`AAMAD_TARGET_RUNTIME` not set in environment; resolved from `aamad.config.yml` `runtime.target: crewai`, no conflict — note this governs the *application's* CrewAI runtime, unrelated to the Railway hosting decision recorded above)
- **Hosting target**: Railway (railway.com) — **operator decision**, relayed mid-action, resolving `sad.md` §5's previously-open "specific cloud target" question. Not a `@devops.eng` proposal; recorded verbatim as directed.
- **Inputs read in full**: `sad.md` §5, `setup.md`, `backend/pyproject.toml`, `backend/.env.example`, `frontend/.env.example`, `frontend/package.json`, `backend/src/app/main.py`, `backend/src/app/persistence/interaction_log.py` (and confirmed the shared `INTERACTION_LOG_DB_PATH` pattern in `knowledge_base.py`/`review_queue.py`), `backend/src/app/persistence/trace_log.py`, this file's own prior `*prepare-release` entry
- **Files created**: `backend/Dockerfile`, `backend/.dockerignore`, `backend/railway.json`, `frontend/Dockerfile`, `frontend/nginx.conf`, `frontend/.dockerignore`, `frontend/railway.json`, `docker-compose.yml`, `.env.docker.example`
- **Files edited**: `.gitignore` (added `!.env.docker.example` exception only), `project-context/3.deliver/deploy.md` (this section)
- **Verification performed**: read-only confirmation of `GET /health`'s existence and route path in `main.py`; confirmed `CORS_ALLOWED_ORIGINS`/`INTERACTION_LOG_DB_PATH`/`TRACE_LOG_DIR` are genuine, already-supported env-var overrides (not invented) by reading their resolution functions in `main.py`/the three `persistence/*.py` modules; no `docker build`/`docker compose up`/Railway CLI commands were actually executed in this environment (no Docker daemon assumed available; this is config authoring, consistent with `delivery-workflow.md`'s "generate CI/CD configuration files only; do not trigger live deploys")
- **Prohibited actions confirmed avoided**: no application code modified (`main.py` and all `persistence/*.py` files read-only); no `qa.md`/`security.md` modified; no CI workflow authored (`*configure-cicd`, not this action); no runbook/user-guide authored (`*document-deploy`, not this action); no Kubernetes/Terraform/multi-region config produced; no live Railway account/project/deploy created; no real secret values written anywhere

- **Timestamp**: 2026-09-02
- **Persona**: `@devops.eng`
- **Action**: `*define-deploy` (follow-up correction, same day: the initial `$PORT`-vs-8000 mismatch flagged above as an Open Question was mis-scoped — it is a hard Railway platform requirement, not an operator judgment call. Railway assigns each service a dynamic `$PORT` and routes traffic/healthchecks to it; a hardcoded `--port 8000` would have made the deployment fail to receive traffic outright whenever Railway's assigned port isn't 8000.)
- **Fix applied**: `backend/Dockerfile`'s `CMD` changed from exec-form `["uvicorn", ..., "--port", "8000", ...]` to shell-form `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --app-dir src` (exec-form does not perform env-var substitution; shell-form runs via `/bin/sh -c`, which does). `HEALTHCHECK`'s Python one-liner changed to read `os.environ.get('PORT', '8000')` so the container-level check keeps probing whatever port uvicorn actually bound. Stale in-Dockerfile comment claiming "the PORT env var ... is deliberately not wired up here" was rewritten to describe the new behavior. `EXPOSE 8000` and `backend/railway.json` were reviewed and confirmed to need no change: `EXPOSE` is documentation-only and doesn't affect runtime binding; Railway's `healthcheckPath` probes whatever port it already assigned internally, no port number needed there.
- **Verification performed (real, not just read-through)**: no Docker daemon is available in this environment (`docker`/`docker version` both fail — confirmed via both Bash and PowerShell), so the exact shell-form command was exercised directly instead of via `docker build`/`docker run`: (1) ran `sh -c 'uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --app-dir src'` (activating `backend/.venv`) with `PORT=9123` exported — confirmed via the uvicorn startup log ("Uvicorn running on http://0.0.0.0:9123") and a real `curl http://127.0.0.1:9123/health` returning `200 {"status":"ok"}`, while an unrelated control port returned nothing; (2) ran the same construct with `PORT` unset — bound to the documented 8000 fallback; (3) ran the exact `HEALTHCHECK` Python one-liner (`os.environ.get('PORT','8000')`) with `PORT` matching a live server — succeeded, exit 0 — and with `PORT` pointed at a genuinely empty port (9999) — failed with a connection timeout, exit 1 (correctly unhealthy). This confirms the `${PORT:-8000}`/`os.environ.get('PORT','8000')` logic itself works as intended; it does not substitute for a full `docker build && docker run` smoke test on the actual image, which remains untested (no Docker daemon here) and is worth a first-deploy sanity check.
- **`docker-compose.yml` reviewed, not changed**: confirmed `.env.docker.example`/`.env.docker` never set a `PORT` variable, so the container continues to fall back to 8000 under compose exactly as before — the existing `"${BACKEND_HOST_PORT:-8000}:8000"` port mapping stays correct with no edit needed.
- **Files edited**: `backend/Dockerfile` (`CMD`, `HEALTHCHECK`, and their comments), `project-context/3.deliver/deploy.md` (this entry — moved the `$PORT` item out of Open Questions/Assumptions into the resolved description above, per the coordinator's correction)
- **Prohibited actions confirmed avoided**: `docker-compose.yml` left untouched (reviewed only, per instruction); no other application code modified; `qa.md`/`security.md` untouched

---

## CI/CD Configuration (`*configure-cicd`, 2026-09-02)

### Scope

Per `delivery-workflow.md`'s Continuous Deployment Policy ("Generate CI/CD configuration files only; do not trigger live deploys without explicit operator authorization") and this persona's own `*configure-cicd` command definition ("Scaffold CI workflow for lint, test, and build only"): this action authors **one new file**, `.github/workflows/ci.yml`, and nothing else. No Railway CLI step, no Docker image build/push, no publish step of any kind exists in it — that remains out of scope for this command regardless of Railway now being the known hosting target from `*define-deploy` above.

### Platform choice: GitHub Actions

`git remote -v` confirms the repo's remote is `https://github.com/arunprasadlv/customer-support-agent.git` — GitHub. No other CI platform config (CircleCI, GitLab CI, Jenkinsfile, Azure Pipelines, etc.) was found anywhere in the repo, and `.github/workflows/` did not exist before this action (confirmed via directory check) — this is the gap being filled, not a switch away from an existing choice. GitHub Actions is the natural, zero-additional-infrastructure fit.

### What was authored: `.github/workflows/ci.yml`

Two independent jobs in one workflow, each scoped to its own subdirectory via `defaults.run.working-directory` (this is a monorepo — `backend/` and `frontend/` each need their own dependency install and tool invocations, confirmed against `setup.md`'s documented commands rather than invented):

**`backend` job** — `actions/checkout` → `actions/setup-python@v5` pinned to **Python 3.11** (matches `backend/pyproject.toml`'s `requires-python = ">=3.11,<3.15"` floor and `backend/Dockerfile`'s `python:3.11.11-slim-bookworm` base — same line the shipped runtime uses, not an arbitrary CI-only choice) → `pip install -e ".[dev]"` (the exact command `setup.md` §5 documents) → `ruff check .` → `mypy src` → `pytest -q` (all three read directly from `setup.md`/`qa.md`, not guessed). `actions/setup-python`'s pip cache is enabled, keyed off `backend/pyproject.toml`.

**`frontend` job** — `actions/checkout` → `actions/setup-node@v4` pinned to **Node 22.12.0** (matches `frontend/Dockerfile`'s build-stage base, `node:22.12.0-bookworm-slim`, chosen for CI/build parity since `package.json` has no `engines` field or `.nvmrc` to otherwise pin to, per `setup.md`'s own note that "Node version chosen independently") → `npm ci` → `npm run lint` (oxlint) → `npm run build` (`tsc -b && vite build`). `frontend/package.json`'s `scripts` block (`dev`, `build`, `lint`, `preview` — confirmed by direct read, no `test` entry) has no test script, so no frontend test step was added; this matches `qa.md`'s own repeatedly-confirmed "zero automated frontend tests" gap (Known Defect #4) rather than fabricating a step that would immediately fail.

### Triggers

`push`/`pull_request` on `main` and `devops` (the current working branch, confirmed via `git branch --show-current`). Reasoning: `main` is the repo's stated main branch; `devops` is where this Deliver-phase work is actually landing and where a broken CI config would need to be caught before merge. Narrower than "all branches" to avoid running on throwaway/experiment branches not headed toward `main`; broader triggers (e.g. all PRs regardless of target branch) can be added later with no structural change if the branching model evolves — not assumed here beyond what's currently observed (`qa`, `devops`, `integration`, `main` per recent `git log`/merge history).

### Decision: `ANTHROPIC_API_KEY` in CI — use a GitHub Actions secret

This is the real judgment call the task called out, so the reasoning is recorded in full rather than just the conclusion:

**What the skip conditions actually do (verified by reading the test files, not assumed):** `backend/tests/integration/test_chat_endpoint.py`, `test_email_endpoint.py`, and `test_inquiry_flow.py` each compute `_HAS_ANTHROPIC_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))` at module load and gate their live-round-trip tests with `@pytest.mark.skipif(not _HAS_ANTHROPIC_KEY, reason="...")`. Confirmed these are genuine `SKIPPED` outcomes, not silent passes or hidden failures — `pytest` reports skips distinctly, and `qa.md`'s own 2026-09-01 pass independently observed exactly this behavior when credits were briefly unavailable. `test_escalation_gate.py`, `test_trace_log.py`, `test_escalation_resolution_flow.py`, `test_escalation_resolve_endpoint.py`, and `test_review_queue_endpoints.py` were confirmed (via `grep` for `skipif`/`_HAS_ANTHROPIC_KEY`) to carry **no such gate at all** — they are fully deterministic and always run regardless of key availability. So: CI without a key would still execute the large majority of the 150-test suite and would not error — it would just skip roughly a dozen live-round-trip tests, degrading gracefully rather than failing noisily.

**Decision: wire `ANTHROPIC_API_KEY` as a GitHub Actions repository secret (`${{ secrets.ANTHROPIC_API_KEY }}`), passed as an env var to the `pytest -q` step.** Reasoning: `qa.md`'s own standard for this project is explicitly *not* unit-tests-only — its highest-confidence verification of this session's headline bug fix was a live end-to-end `POST /chat` call against the real Anthropic API, with unit tests treated as necessary but not sufficient corroboration. A CI gate that silently skips exactly the tests that give that live-verification confidence would be a materially weaker gate than what `@qa.eng` itself relies on, even though it would technically stay green either way. Setting the secret costs nothing extra when it's present (pushes/PRs from this repo) and still degrades safely when it's absent (e.g. a fork PR, where GitHub Actions does not expose repository secrets by design) — the skip conditions verified above mean that absence is a graceful skip, not a broken pipeline. This is recorded as an **operator action item**, not something this action can do itself: the operator must add `ANTHROPIC_API_KEY` under the repo's Settings → Secrets and variables → Actions before CI runs will exercise the live-round-trip tests; until then, CI still passes, just with those dozen tests skipped, which is a safe, non-blocking default.

### Explicitly NOT built (confirms scope stayed within `*configure-cicd`)

- No deploy/publish job or step — no Railway CLI action, no `docker build`/`docker push`, no `railway up`. That remains an explicit operator action (see `*document-deploy` below).
- No workflow badge added to any README (cosmetic, not requested, not part of this command's scope).
- No branch-protection rule configuration (a GitHub repo *setting*, not a workflow file — outside "generate CI/CD configuration files").
- No caching/artifact upload beyond `setup-python`/`setup-node`'s built-in dependency caches — no build-artifact upload step, since nothing downstream in this repo consumes one yet.
- No matrix build (single Python/Node version each) — `pyproject.toml`'s version range is a compatibility floor/ceiling, not a support matrix this MVP has committed to testing across; revisit only if that need arises.

### Sources

- `.claude/rules/delivery-workflow.md` (Continuous Deployment Policy — config-only, lint/test/build stages, manual promotion documentation)
- `project-context/2.build/setup.md` §5 (exact backend install/lint/type-check/test commands; frontend install/lint/build commands; Python 3.11.16 in `backend/.venv`, Node v24.16.0 used at scaffold time but no `engines` pin — confirmed no conflict with pinning CI to 3.11/22.12.0 instead, since neither is SAD-mandated)
- `project-context/2.build/qa.md` (2026-09-02 fresh pass: exact `pytest -q`/`ruff check .`/`mypy src`/`npm run lint`/`npm run build` commands and their current clean/passing state; the live-verification standard cited in the `ANTHROPIC_API_KEY` decision above; confirmed zero frontend test script exists)
- `backend/pyproject.toml` (`requires-python = ">=3.11,<3.15"`, `[project.optional-dependencies].dev` exact package list)
- `backend/Dockerfile`, `frontend/Dockerfile` (base image versions used for CI version-pin parity)
- `frontend/package.json` (`scripts` block — confirmed no `test` entry)
- `backend/tests/integration/test_chat_endpoint.py`, `test_email_endpoint.py`, `test_inquiry_flow.py` (read directly for the exact `skipif`/`_HAS_ANTHROPIC_KEY` gating logic)
- `backend/tests/unit/test_escalation_gate.py`, `backend/tests/unit/test_trace_log.py`, `backend/tests/integration/test_escalation_resolution_flow.py`, `test_escalation_resolve_endpoint.py`, `test_review_queue_endpoints.py` (grepped, confirmed no key-gating present — fully deterministic)
- `git remote -v` (confirms GitHub); `git branch --show-current` (confirms `devops`); `git log --oneline` (confirms recent branch/merge history: `qa`, `devops`, `integration`, `main`)

### Assumptions

- The operator has not yet added `ANTHROPIC_API_KEY` as a GitHub Actions secret — this action cannot create repository secrets itself (no such tool/credential available in this environment), only recommend and wire the reference. Until added, CI passes with the live-round-trip tests skipped (verified graceful, not a broken pipeline).
- `main` and `devops` are treated as the two trigger branches worth gating on now; other topic branches (`qa`, `integration`, etc., visible in `git log`'s merge history) are assumed to feed into `devops`/`main` via PR, at which point the PR trigger already covers them — not given their own explicit trigger entries to avoid over-specifying a branching model that isn't formally documented anywhere in `sad.md`/`setup.md`.
- Ubuntu (`ubuntu-latest`) runners are assumed sufficient for both jobs — nothing in `backend/Dockerfile`/`frontend/Dockerfile` requires a non-Linux build environment, and Railway's own builds are Linux-based, so this keeps CI and the real deploy target's OS aligned.

### Open Questions

- Should the operator also add branch-protection rules requiring this workflow's two jobs to pass before merging to `main`? That's a repository setting, not a file this action produces — flagged here as a natural follow-up, not assumed or configured.
- If Anthropic billing/credits are ever exhausted (as `qa.md`'s 2026-08-22 spike observed happening once already), live-round-trip CI tests would start failing (a real API error), not skipping (the skip only triggers on a *missing* key, not a key that's present but rate-limited/out of credits) — worth the operator's awareness if CI ever goes red on `pytest` for a reason unrelated to code changes.
- Whether a future frontend test runner (Vitest/RTL, per `qa.md` Known Defect #4, still unresolved) should be added to the `frontend` job once it exists — not addressed here since the runner itself doesn't exist yet; this workflow can add a step trivially once it does.

### Audit

- **Timestamp**: 2026-09-02
- **Persona**: `@devops.eng`
- **Action**: `*configure-cicd`
- **Resolved runtime**: `crewai` (`AAMAD_TARGET_RUNTIME` not set in environment; resolved from `aamad.config.yml` `runtime.target: crewai`, no conflict — unrelated to the GitHub Actions CI platform choice above)
- **Inputs read in full**: `project-context/2.build/setup.md` §5, `project-context/2.build/qa.md` (2026-09-02 fresh pass, §1/§2), `backend/pyproject.toml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/package.json`, `backend/tests/integration/test_chat_endpoint.py`, `test_email_endpoint.py`, `test_inquiry_flow.py` (full `skipif` gating logic), this file's own `*define-deploy` section above
- **Verification performed**: `git remote -v` (GitHub confirmed), `ls .github/workflows` (confirmed absent before this action), `git branch --show-current` (`devops`), `grep` across `backend/tests/` for `skipif`/`ANTHROPIC_API_KEY` (confirmed which test files gate on the key and which don't), direct read of `frontend/package.json`'s `scripts` block (confirmed no `test` entry). No `git push`/no workflow run was triggered by this action — the file was authored and reviewed locally only.
- **Files created**: `.github/workflows/ci.yml`
- **Prohibited actions confirmed avoided**: no deploy/publish/Railway CLI/Docker-push step added; no live Railway or GitHub Actions run triggered by this action; no application code, test file, `qa.md`, or `security.md` modified; no repository settings (branch protection, secrets) configured — secrets addition remains an explicit operator action item, documented above, not performed here

---

## Deploy Runbook (`*document-deploy`, 2026-09-02)

This section is the standalone operational runbook per `delivery-workflow.md`'s Artifact Contract and this persona's `*document-deploy` command. It consolidates decisions already made in `*define-deploy` above (referenced, not restated verbatim) into the specific sections `delivery-workflow.md` requires: hosting, env-var matrix, access control, rollback, and manual promotion steps. A future reader should be able to follow this section alone to actually operate a deploy — cross-references to `*define-deploy` above are for the *why*, not the *how*.

### Hosting

**Platform**: Railway (railway.com) — operator decision, recorded and justified in the `*define-deploy` section above; not re-litigated here.

**Topology**: two Railway services in one Railway project, both built from this same GitHub repo (monorepo) via per-service Dockerfiles:

| Service | Root Directory | Builds from | Public? |
|---|---|---|---|
| `backend` | `backend/` | `backend/Dockerfile` (via `backend/railway.json`) | Yes — its Railway-assigned URL is the API origin the frontend calls |
| `frontend` | `frontend/` | `frontend/Dockerfile` (via `frontend/railway.json`) | Yes — this is the URL guests/operators open in a browser |

Full first-time setup steps (creating the two services, wiring their Root Directories, confirming healthcheck detection) are already documented step-by-step in the `*define-deploy` section's "Railway service setup" subsection above — not repeated here. This section assumes that one-time setup is done and focuses on the ongoing operational picture: what env vars each service needs, how to promote new code, and how to roll back.

**Persistent data**: the backend service requires one Railway Volume mounted at `/app/state` (SQLite DB + Trace Log JSONL both live under it) — see `*define-deploy`'s "Persistent data on Railway" subsection for the full mechanism and the single-writer/no-horizontal-scaling constraint that comes with it. The frontend service is stateless and needs no volume.

### Env-var matrix

Every env var this app uses at deploy time, consolidated into one table (previously scattered across `*define-deploy`'s prose):

| Variable | Service | Secret? | Set where | Notes |
|---|---|---|---|---|
| `ANTHROPIC_API_KEY` | backend | **Yes** | Railway dashboard (backend service → Variables); local: `backend/.env` (gitignored) | Never committed anywhere; name-only in `backend/.env.example`. Required for every `/chat`/`/email` call — the app's core LLM dependency. |
| `CORS_ALLOWED_ORIGINS` | backend | No | Railway dashboard (backend service → Variables); local: falls back to Vite dev-server default ports if unset | Must be set to the frontend service's Railway-assigned public URL once known (chicken-and-egg with first deploy — see Manual promotion steps below for the two-pass sequencing this implies). |
| `INTERACTION_LOG_DB_PATH` | backend | No | Railway dashboard (backend service → Variables) | Railway value: `/app/state/data/app.db` (differs from local/compose default `backend/data/app.db` / compose's `/app/data` — see `*define-deploy`'s Persistent Data subsection for why). |
| `TRACE_LOG_DIR` | backend | No | Railway dashboard (backend service → Variables) | Railway value: `/app/state/logs` (differs from local default; same reasoning as above). |
| `PORT` | backend | No | **Not set manually — Railway-injected** | Railway assigns this dynamically per service and routes traffic/healthchecks to it. `backend/Dockerfile`'s `CMD` already reads `${PORT:-8000}`. Do not set this in the dashboard; leave it alone. |
| `VITE_API_BASE_URL` | frontend | No | Railway dashboard (frontend service → Variables), consumed as a Docker build `ARG` | **Build-time only** — inlined into the static JS bundle by `vite build`, not read at container runtime. Must be set to the backend service's Railway-assigned public URL *before* the frontend's first build; changing it later requires a rebuild, not just a restart. |
| `DATABASE_URL` | backend | No | Local only (`backend/.env`), **not used on Railway** | Legacy/local-dev-only var from `backend/.env.example`'s original scaffold (`setup.md` §4); the app's actual persistence path is governed by `INTERACTION_LOG_DB_PATH` above, confirmed by reading `interaction_log.py`/`knowledge_base.py`/`review_queue.py`. Listed here only so an operator copying `.env.example` isn't confused about which var actually matters on Railway. |

Local (non-Railway) `.env`/`.env.docker` file usage — `backend/.env` for bare local `uvicorn`, `.env.docker` (from `.env.docker.example`) for `docker-compose` — is unchanged from `*define-deploy`'s "Secrets handling" subsection above; not restated here.

### Access control

Per `delivery-workflow.md`'s Access Control section: secrets are documented here as **names only**, consistent with everything above and with `security.md` INFO-1's standard — no real value for `ANTHROPIC_API_KEY` or any Railway credential appears anywhere in this repo or artifact set, and that stays true going forward.

- **Anthropic API key**: least-privilege in this context means exactly one live value exists (the operator's own Anthropic account key), held only in Railway's dashboard (backend service variables) and, for local dev, in each individual developer's own gitignored `backend/.env`. It is never shared via chat, artifact, or commit. Rotation (if the key is ever suspected compromised) is a Railway-dashboard variable edit plus an Anthropic-console key revocation — no code change needed since the app reads it purely from the environment.
- **Railway project/deployment credentials**: this MVP has no user authentication layer (`sad.md` §8, already an accepted risk recorded in `security.md` — cross-referenced here, not re-litigated). Given that, Railway project access is the *only* access-control boundary that meaningfully exists for this app's infrastructure, which raises its importance: for MVP scale, the recommendation is that **the operator** holds sole Railway project ownership/admin access. If a second person ever needs deploy access (e.g. a co-developer), Railway supports inviting collaborators at the project level with role-based permissions (Railway's own product feature) — not configured here, since no second operator has been named; add only when actually needed, per least-privilege.
- **GitHub repository access**: since CI (`*configure-cicd` above) reads `secrets.ANTHROPIC_API_KEY` from GitHub's own secret store, GitHub repository admin access is itself a sensitive privilege boundary (anyone who can edit workflow files or add collaborators with sufficient permission could potentially exfiltrate that secret via a modified workflow run). Keep repository write access limited to the same trust boundary as Railway access above — no separate policy invented here beyond noting the linkage exists.

### Rollback procedure

**Primary mechanism (Railway-native, assumption flagged below)**: Railway retains a history of previous successful deployments per service and exposes a "redeploy" / rollback action from its dashboard's Deployments tab — selecting an earlier deployment and redeploying it routes traffic back to that earlier build without requiring a new git push or CI run. **This is documented as the expected mechanism based on general knowledge of Railway's product, not re-verified against Railway's current live UI in this session** (no Railway account/credentials exist in this environment) — treat the exact click-path as approximate and confirm against the dashboard's actual current labels before relying on it during a real incident. Flagged again under Open Questions.

**Fallback procedure (git-based, always available regardless of Railway UI specifics)**, use this if the dashboard rollback option isn't where expected or doesn't behave as described above:

1. Identify the last known-good commit (e.g. via `git log` on `main`, or Railway's own deployment history showing which commit each past deployment built from).
2. `git revert <bad-commit-sha>` (preferred over `git reset --hard` + force-push, which rewrites history other collaborators may have already pulled) on `main`, or open a revert PR if branch protection requires review.
3. Push the revert to `main`. If Railway is connected for git-push-to-deploy (see Manual promotion steps below), this alone triggers a new build/deploy of the reverted code on both affected services (rebuild only the service(s) whose files actually changed, if Railway's monorepo change-detection is enabled; otherwise both services rebuild).
4. If Railway is *not* connected for auto-deploy (manual `railway up` model), run `railway up` from the reverted working tree for the affected service(s) — see Manual promotion steps below for the exact command.
5. Confirm recovery via each service's `/health` endpoint (backend) and a manual page load (frontend) before considering the rollback complete.

Either path restores code; neither path touches the persisted SQLite volume (`/app/state`) — a rollback does not itself undo any data written by the bad deployment (e.g. interaction-log rows), which is a separate, not-yet-built capability (no volume snapshot/backup policy is configured — carried forward from `*define-deploy`'s Open Questions above).

### Manual promotion steps

Since CI (`*configure-cicd` above) explicitly does not deploy, an operator must promote a merged PR to a live Railway deployment. **Two models exist; this runbook documents the git-push-to-deploy model as primary**, since it's Railway's own default/native workflow for a GitHub-connected project (matching how the "Railway service setup" steps in `*define-deploy` above describe connecting each service to this repo) and requires the least manual, error-prone CLI usage for routine promotions. The manual-CLI model is documented second as the fallback for whenever git-push-to-deploy isn't configured or isn't desired for a specific change.

**Primary model — Railway git-push-to-deploy** (assumes each Railway service was connected to this GitHub repo per `*define-deploy`'s setup steps, with its deploy trigger branch set to `main`):

1. Merge the approved PR into `main` (CI's `backend`/`frontend` jobs, per `*configure-cicd` above, must have passed on that PR first — this is the actual quality gate, since CI itself never deploys).
2. Railway detects the push to `main` and automatically starts a new build for whichever service(s) have changed files under their configured Root Directory (`backend/` or `frontend/`) — Railway's own per-service change detection, not something this repo's config controls.
3. Watch the build/deploy progress in the Railway dashboard for each affected service.
4. Once live, verify: `GET https://<backend-service>.up.railway.app/health` returns `{"status": "ok"}`, and the frontend's public URL loads and can complete a real `/chat` round-trip end-to-end.
5. **First-deploy-only sequencing note** (carried from the env-var matrix above): `CORS_ALLOWED_ORIGINS` and `VITE_API_BASE_URL` each depend on the *other* service's Railway-assigned URL, which isn't known until each service is created once. First deploy is therefore two passes in practice: (a) create both services and let them get their public URLs assigned, (b) set `CORS_ALLOWED_ORIGINS` on backend and `VITE_API_BASE_URL` on frontend, then (c) redeploy the frontend at minimum (its `VITE_API_BASE_URL` is a build-time value — see env-var matrix). Routine promotions *after* this first deploy don't need this dance, since both URLs stay stable across redeploys.

**Fallback model — manual `railway up` (Railway CLI)**, if git-push-to-deploy isn't set up or a specific change needs a targeted manual deploy:

1. Install the Railway CLI locally (`npm i -g @railway/cli` or the platform-appropriate install method) and `railway login`.
2. `railway link` to select the correct project (one-time per local machine/checkout).
3. From `backend/` or `frontend/` (whichever changed), run `railway up` — this builds and deploys that directory's Dockerfile directly from the local working tree, bypassing GitHub entirely for that one deploy. **Caution, worth flagging explicitly**: this deploys whatever is in the local working tree at that moment, including any uncommitted changes — an operator using this path should confirm `git status` is clean and matches the intended commit before running it, so what's deployed matches what's reviewed/merged.
4. Verify the same way as step 4 above.

Both models produce the same running artifact (a container built from the same Dockerfile); the choice is about *how* a deploy gets triggered, not what gets deployed.

### Sources

- This file's own `*prepare-release` and `*define-deploy` sections above (read in full before authoring this section, per this action's own instructions) — Railway hosting decision, per-service setup steps, `$PORT` fix, persistent-volume plan, and the full list of env vars each already establishes; referenced rather than restated per this action's explicit instruction not to duplicate that content verbatim
- `project-context/2.build/security.md` (§8-adjacent no-auth accepted risk, cross-referenced rather than re-litigated, per this action's instructions)
- `project-context/1.define/sad.md` §8 (no user-auth-layer MVP scope, cited by `security.md` and cross-referenced here)
- `backend/.env.example`, `frontend/.env.example` (env var names, confirming `DATABASE_URL`'s legacy/local-only status against actual code)
- `backend/src/app/persistence/interaction_log.py`, `knowledge_base.py`, `review_queue.py`, `trace_log.py` (confirmed `INTERACTION_LOG_DB_PATH`/`TRACE_LOG_DIR` are the actual runtime-read vars, not `DATABASE_URL`)
- `backend/Dockerfile`, `frontend/Dockerfile`, `backend/railway.json`, `frontend/railway.json` (reviewed again for this section; no bugs found, no changes made)
- General product knowledge of Railway's dashboard rollback/redeploy feature and git-push-to-deploy behavior — **not verified against a live Railway account in this session** (no credentials available), flagged as an assumption/Open Question below, consistent with `*define-deploy`'s own prior treatment of unverified Railway behaviors (e.g. the build-`ARG` passthrough question)

### Assumptions

- Railway's dashboard exposes a "redeploy a previous deployment" / rollback action substantively as described above — based on general product knowledge, not re-verified live. The git-revert fallback procedure works regardless of whether this assumption holds, so the runbook isn't solely dependent on it.
- Railway's git-push-to-deploy model (auto-build on push to a configured branch, per-service change detection scoped to each service's Root Directory) is documented as the primary promotion model because it's Railway's typical default for GitHub-connected projects and requires the least manual operator action for routine changes — not yet confirmed against this specific project's live Railway configuration (no live project exists yet, per `*define-deploy`'s own "no live Railway project, service, or deploy was created" note, carried forward unchanged by this action).
- "The operator" is assumed to be the sole holder of Railway project access and the Anthropic API key for MVP purposes, consistent with `sad.md` §8's no-auth, single-operator framing — not a new assumption invented here, just applied to the access-control question this section had to answer.
- No Railway volume backup/snapshot policy is assumed configured (carried forward, unresolved, from `*define-deploy`'s Open Questions) — the rollback procedure above explicitly notes it does not restore data, only code.

### Open Questions

- **Not yet verified**: the exact current Railway dashboard UI/labels for redeploying a previous deployment (rollback) — confirm against the live dashboard before the first real incident, per the flag above.
- **Not yet verified**: whether each Railway service in this project will actually be configured for git-push-to-deploy (the primary model documented above) versus manual `railway up` only — this depends on choices made during the one-time Railway service setup (`*define-deploy`'s dashboard steps), which has not been performed yet in a live Railway project. Confirm which model is actually in effect once that setup happens, and update this section's "primary" framing if manual-only turns out to be the operator's actual choice.
- Whether a second person will ever need Railway project or GitHub repository access — not currently needed (single-operator MVP), addressed above only at a policy level per `delivery-workflow.md`'s "policy level" instruction, not configured.
- Carried forward, unresolved, from `*define-deploy`/earlier sections, not re-litigated here: the Railway build-`ARG` passthrough assumption for `VITE_API_BASE_URL`; the SAD §7 latency gate; the undocumented `MAX_EXECUTION_TIME_SECONDS` deviation; whether to configure a Railway volume backup/snapshot policy for `app.db`.

### Audit

- **Timestamp**: 2026-09-02
- **Persona**: `@devops.eng`
- **Action**: `*document-deploy`
- **Resolved runtime**: `crewai` (`AAMAD_TARGET_RUNTIME` not set in environment; resolved from `aamad.config.yml` `runtime.target: crewai`, no conflict — unrelated to the Railway hosting/runbook content above)
- **Inputs read in full**: this file's own `*prepare-release`/`*define-deploy`/`*configure-cicd` sections above (in full, per this action's instructions), `project-context/2.build/security.md` (§8-adjacent no-auth risk section), `project-context/1.define/sad.md` §8, `backend/.env.example`, `frontend/.env.example`, `backend/src/app/persistence/interaction_log.py`/`knowledge_base.py`/`review_queue.py`/`trace_log.py` (re-confirmed which env vars are actually live-read, to catch the `DATABASE_URL` legacy-var discrepancy called out in the env-var matrix above), `backend/Dockerfile`, `frontend/Dockerfile`, `backend/railway.json`, `frontend/railway.json` (re-reviewed for bugs; none found, no changes made)
- **Verification performed**: read-only cross-referencing of already-established facts from `*define-deploy` against actual code (`DATABASE_URL` vs. `INTERACTION_LOG_DB_PATH` discrepancy confirmed as a pre-existing, already-documented-elsewhere legacy-var note, not a bug — `backend/.env.example` scaffolds `DATABASE_URL` from `setup.md`'s original setup action, but the actual persistence code never reads it; this is called out for operator clarity in the env-var matrix above, not silently left ambiguous). No Dockerfile/railway.json/docker-compose.yml bugs were found during this cross-reference — none fixed, since none needed fixing.
- **Files edited**: `project-context/3.deliver/deploy.md` (this section and the `*configure-cicd` section above it, appended in this same action sequence)
- **Prohibited actions confirmed avoided**: no application code, `qa.md`, or `security.md` modified; no Dockerfile/railway.json/docker-compose.yml modified (reviewed only, cross-referenced against this section's claims — no bug found, so nothing to fix); no live Railway rollback, redeploy, or `railway up` command actually executed (no Railway account/credentials exist in this environment); no duplication of `*prepare-release`/`*define-deploy`'s full content — referenced by section name instead, per this action's explicit instruction

---

## Diagnostic — Halt and Report (2026-09-01, superseded — preserved for history)

**Status**: HALTED. Deliver-phase work has not started (no deploy config, CI scaffolding, or runbook content produced) because the Phase Gate defined in `delivery-workflow.md` is not satisfied.

**Trigger for this action**: operator requested `@devops.eng` configure observability for the customer support agent.

**Blockers**:

1. **Missing QA gate artifact.** `delivery-workflow.md` requires `project-context/2.build/qa.md` to exist and document MVP verification results (pass, or explicitly scoped known gaps) before any Deliver work begins. It does not exist yet — confirmed via directory listing of `project-context/2.build/` (contains `backend.md`, `backend-test-report.md`, `frontend.md`, `integration.md`, `setup.md`, `logs/`; no `qa.md`).
2. **Missing required Security Assessment.** `aamad.config.yml` sets `security.require_security_assessment: true`. `delivery-workflow.md` therefore expects `project-context/2.build/security.md` before Deliver; it does not exist yet.
3. **Requested scope exceeds what PRD/SAD authorize for MVP.** `sad.md` (DevOps/NFR section) already fixes the observability scope for MVP as: baseline structured logs (interaction log, PII-action log) + `GET /health`; explicitly **"no APM for MVP"**; and lists **"IaC / multi-region / advanced monitoring"** under Future Work — not scoped. Per `aamad-core.md` ("do not invent requirements"), building new observability infrastructure (APM, dashboards, alerting) beyond that baseline would be scope creep not traceable to PRD/SAD, and per `delivery-workflow.md` any such deferred ops item belongs under this document's Future Work section, not as active Deliver-phase work.

**Halt action taken**: no Dockerfile/compose/platform config, CI workflow, or runbook content has been written. This file records the Diagnostic only, per `aamad-core.md` Failure Policy ("On iteration/time limits or missing prerequisites, write a Halt and Report section with blockers; do not continue.").

**Handoff**: `@qa.eng` (`*qa`) is being engaged to produce `qa.md` against the existing build artifacts (`backend.md`, `backend-test-report.md`, `frontend.md`, `integration.md`) so the Phase Gate can close. `@security.eng` (`*assess-security`) still needs to run separately to produce `security.md` given `require_security_assessment: true`.

**Safe retry steps**:
1. `@qa.eng` runs `*qa`, producing `project-context/2.build/qa.md` with MVP verification results.
2. `@security.eng` runs `*assess-security`, producing `project-context/2.build/security.md`.
3. Once both exist, `@devops.eng` resumes with `*prepare-release`, confirming the gate, then `*define-deploy` / `*configure-cicd` / `*document-deploy`, carrying forward the SAD's fixed observability baseline (structured logs + `/health`) and listing APM/advanced monitoring under Future Work as already directed by `sad.md`.

## Future Work (carried forward from sad.md, for when this document is actively authored)
- IaC, multi-region deployment, advanced monitoring/APM: out of MVP scope per `sad.md` DevOps/NFR section.
- Any expansion of observability beyond baseline structured logs + `/health` requires an explicit PRD/SAD scope change first, not a unilateral Deliver-phase addition.

## Sources
- `.claude/rules/delivery-workflow.md` (Phase Gate, Failure Policy)
- `.claude/rules/aamad-core.md` (Failure Policy, Security and Compliance)
- `aamad.config.yml` (`security.require_security_assessment: true`, `runtime.target: crewai`)
- `project-context/1.define/sad.md` (DevOps/NFR observability scope, Future Work)
- `project-context/2.build/` directory listing (confirms `qa.md`, `security.md` absent)

## Assumptions
- None made beyond what is directly observed in the repository; no fabricated qa.md/security.md content.

## Open Questions
- Should `@qa.eng` be run now to unblock this gate, or does the operator want to explicitly accept the QA/security gap and proceed anyway (per `delivery-workflow.md`, that would require operator acceptance to be recorded here under Assumptions before continuing)?
- Confirm whether "configure observability" was intended as MVP-scope (already covered by the existing structured-log baseline) or as a scope-expansion request (would need a PRD/SAD update before `@devops.eng` can act on it).

## Audit
- **Timestamp**: 2026-09-01
- **Persona**: `@devops.eng`
- **Action**: `*document-deploy` (invoked to configure observability; halted at Phase Gate check before any deploy content was authored)
- **Resolved runtime**: `crewai` (`AAMAD_TARGET_RUNTIME` not set in environment; resolved from `aamad.config.yml` `runtime.target: crewai`, no conflict)
- **Files changed/added**: `project-context/3.deliver/deploy.md` (new — Diagnostic/Halt only)
- **Verification performed**: directory listing of `project-context/2.build/` confirming absence of `qa.md` and `security.md`; read of `aamad.config.yml` confirming `security.require_security_assessment: true`; read of `sad.md` observability/Future Work lines
- **Prohibited actions confirmed avoided**: no deploy config, CI workflow, or monitoring/APM infrastructure created; no application logic modified

---

- **Timestamp**: 2026-09-02
- **Persona**: `@devops.eng`
- **Action**: `*prepare-release` — confirmed QA gate from `qa.md`, noted `security.md` status, summarized release scope and version.
- **Resolved runtime**: `crewai` (`AAMAD_TARGET_RUNTIME` not set in environment; resolved from `aamad.config.yml` `runtime.target: crewai`, no conflict)
- **Inputs read in full**: `project-context/2.build/qa.md` (both dated passes), `project-context/2.build/security.md` (both the original and follow-up sections), `frontend/package.json`/`backend/pyproject.toml` (version fields), `git rev-parse --short HEAD`/`git log -1 --format=%cd` (commit `350059a`, 2026-09-02)
- **Verification performed**: read-only — confirmed both gate artifacts exist and their current (not stale) recommendations both support proceeding; no test/lint/build commands re-run by this action (already fresh per `qa.md`'s own 2026-09-02 live verification, re-run would be redundant for a readiness check)
- **Files changed/added**: `project-context/3.deliver/deploy.md` (this update — Release Readiness section added; 2026-09-01 Diagnostic/Halt preserved below, not deleted)
- **Prohibited actions confirmed avoided**: no deploy config (Dockerfile/compose/platform config), CI workflow, or runbook content authored yet — that is `*define-deploy`/`*configure-cicd`/`*document-deploy`, not this command; no application code modified; no version number actually bumped (recommendation only)
