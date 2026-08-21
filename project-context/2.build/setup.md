# Environment & Project Setup — customer-support-agent

## Input Requirements

**PRD**: `project-context/1.define/prd.md`
**SAD**: `project-context/1.define/sad.md`
**Selected Runtime**: `crewai` (`aamad.config.yml` `runtime.target: crewai`; `.claude/settings.json` env `AAMAD_TARGET_RUNTIME=crewai` — consistent, no override conflict)

## Action Log (`*setup-project`)

This action scaffolds environment, structure, and dependency declarations only — **no business logic, no UI components, no agent logic**. Implementation is out of scope for `@project.mgr`; see the relevant epic/agent (`@backend.eng`, `@frontend.eng`).

### 1. Repository layout

The repo root already carried the AAMAD framework skeleton (`.claude/`, `.cursor/`, `project-context/`, root `.venv/`) with no pre-existing `backend/`/`frontend/` — no conflicts found, so a top-level split was scaffolded per `sad.md` §3/§4:

```
customer-support-agent/
├── backend/                      # Python + FastAPI + CrewAI (sad.md §4)
│   ├── pyproject.toml            # PEP 621 project + ruff + mypy + pytest config
│   ├── README.md                 # Pointer to this file
│   ├── .env.example              # ANTHROPIC_API_KEY, DATABASE_URL, PORT
│   ├── domain_config.json        # Domain-level config skeleton (FR-012/013, hotel)
│   ├── domain_config.schema.json # JSON Schema envelope (stakeholder-confirmed: schema-validated)
│   ├── data/                     # Local SQLite/file store (sad.md §4 Data Architecture)
│   │   └── .gitkeep
│   ├── src/app/
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI app + GET /health only
│   │   ├── config/
│   │   │   ├── agents.yaml       # Empty stub — @backend.eng (adapter-crewai.md)
│   │   │   └── tasks.yaml        # Empty stub — @backend.eng (adapter-crewai.md)
│   │   ├── flows/
│   │   │   └── README.md         # Placeholder for InquiryFlow/EscalationResolutionFlow
│   │   └── agents/
│   │       └── README.md         # Placeholder for reasoning Crew + pii_guard wiring
│   └── tests/
│       ├── __init__.py
│       ├── unit/__init__.py        # Empty — @backend.eng/@qa.eng add unit tests here
│       └── integration/
│           ├── __init__.py
│           └── test_health.py    # Smoke test for GET /health only
├── frontend/                     # React + Vite + TypeScript (sad.md §3)
│   ├── package.json              # name: customer-support-agent-frontend
│   ├── README.md                 # Pointer to this file
│   ├── .env.example              # VITE_API_BASE_URL
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig*.json
│   └── src/
│       ├── main.tsx              # BrowserRouter wrapper
│       ├── App.tsx               # Nav shell + <Routes> for /chat, /inbox, /ops
│       ├── index.css             # Minimal global reset (ui.visual_style: minimal)
│       └── routes/
│           ├── Chat.tsx          # "Coming soon" placeholder
│           ├── Inbox.tsx         # "Coming soon" placeholder
│           └── Ops.tsx           # "Coming soon" placeholder
├── project-context/
│   └── 2.build/
│       ├── setup.md              # This file
│       └── logs/                 # Runtime trace log destination (adapter-crewai.md Logging)
└── (.claude/, .cursor/, aamad.config.yml, README.md, AGENTS.md, CHECKLIST.md — pre-existing, untouched)
```

No route logic beyond `GET /health` was added to the backend; no UI beyond literal "coming soon" placeholder pages was added to the frontend; no CrewAI agent/task definitions were written (both YAML files are comment-only stubs).

### 2. Backend scaffold details

- **Packaging tool**: `pyproject.toml` (PEP 621, `hatchling` build backend) chosen over `requirements.txt`. Justification: single-file dependency + tool config (ruff, mypy, pytest all read `pyproject.toml`), works with both `pip install -e .` and `uv pip install -e .`, and is the convention `adapter-crewai.md`/CrewAI's own `crewai create crew` scaffolding uses (`src/<package>/config/{agents,tasks}.yaml` layout, which this scaffold mirrors under `backend/src/app/config/`).
- **Dependencies declared** (versions intentionally unpinned with `>=` at scaffold time — see Assumptions): `fastapi`, `uvicorn[standard]`, `pydantic`, `crewai`, `python-dotenv`, `jsonschema`. Dev extras (`[project.optional-dependencies].dev`): `pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy`.
- **Dependencies were declared but not installed in this action** — installing (`pip install -e ".[dev]"`/`uv pip install -e ".[dev]"`) is the `*install-dependencies` action, not `*setup-project`, and was not requested this run. Local install commands are documented in §4 below for whoever runs it next.
- **Linting**: `[tool.ruff]` in `pyproject.toml` (line-length 100, `E`/`F`/`I`/`UP`/`B` rule sets) — matches `delivery-workflow.md`'s CI mention of ruff.
- **Type checking**: `[tool.mypy]` in `pyproject.toml` — required by `aamad.config.yml` `coding_standards.type_checking: true`.
- **Testing**: `[tool.pytest.ini_options]` in `pyproject.toml`, `tests/unit/` and `tests/integration/` directories created (empty except one smoke test) — required by `aamad.config.yml` `testing.require_unit_tests`/`require_integration_tests: true`. `tests/integration/test_health.py` exercises only the scaffolded `GET /health` route (via `fastapi.testclient.TestClient`) — this is structural validation of the scaffold itself, not business-logic testing, so it stays in scope for `@project.mgr`.
- **`GET /health`**: implemented in `backend/src/app/main.py` per `sad.md` §5 ("Hosting: ... `/health` endpoint required"). No other routes exist yet; the full contract (`POST /chat`, `POST /email`, `POST /escalations/{id}/resolve`, `GET /review-queue`, `POST /review-queue/{id}/approve`, `POST /review-queue/{id}/reject`, `GET /interactions`) is `@backend.eng`'s (`sad.md` §4).
- **`config/agents.yaml` / `config/tasks.yaml`**: empty except header comments listing the 5 expected agents (from `sad.md` §2 table) and a reminder that `escalation_manager`/`interaction_logger` are deterministic Flow logic (ADR-002), not agents — so `@backend.eng` doesn't accidentally add them here.
- **`domain_config.json`**: skeleton with `domain: "hotel"`, empty `taxonomy: []`, `knowledge_base: []`, `prompts: {}`, and a `$schema` pointer — satisfies PRD's "JSON, schema-validated" domain-config requirement structurally. Placed at `backend/domain_config.json` (backend root, not inside `src/app/`) to visually separate the domain-config layer from the framework-config layer (`src/app/config/*.yaml`), per `sad.md` §2's explicit "two separate configuration layers" distinction.
- **`domain_config.schema.json`**: minimal structural JSON Schema envelope (top-level keys only: `domain`, `version`, `taxonomy`, `knowledge_base`, `prompts`). Sub-schemas for taxonomy/KB/prompt entry shapes are left as `items: {}` TODOs — designing those is a domain-modeling decision for `@backend.eng`, not scaffolding.
- **`flows/` and `agents/` directories**: created empty (each with a `README.md` explaining what belongs there) so `@backend.eng` has an obvious landing spot for `InquiryFlow`/`EscalationResolutionFlow` and the reasoning-Crew/`pii_guard` assembly, per `sad.md` §1 ADR-001 and §2.
- **`data/`**: empty directory (`.gitkeep`) for the local SQLite/file-based store (`sad.md` §4 Data Architecture). Root `.gitignore` updated to ignore `backend/data/*.db` / `*.sqlite3` while keeping the directory tracked via `.gitkeep`.
- **Validation performed this action**: `pyproject.toml` parsed successfully with `tomllib`; `domain_config.json` and `domain_config.schema.json` parsed successfully as JSON; `config/agents.yaml` and `config/tasks.yaml` parsed successfully as YAML (both empty/`None`, as expected for comment-only stubs). No dependency installation or `pytest`/`ruff`/`mypy` execution was performed (see "not installed" note above).

### 3. Frontend scaffold details

- Scaffolded with `npm create vite@latest frontend -- --template react-ts` (network available, verified via `npm ping` before use), then `npm install` (base deps) and `npm install react-router-dom@^7` (routing).
- Renamed `package.json` `name` to `customer-support-agent-frontend`; removed the default Vite demo (`App.css`, counter logic, `hero.png`/`react.svg` demo assets) and replaced `index.html` `<title>`.
- **Routing**: `react-router-dom` `BrowserRouter` in `main.tsx`, `<Routes>` in `App.tsx` with a top nav and three routes — `/chat`, `/inbox`, `/ops` — each rendering a literal "Coming soon" placeholder component under `src/routes/`. `/` redirects to `/chat`. No API client module was added (that belongs to `@frontend.eng`/`@integration.eng` per `sad.md` §3 "One API client module; no backend logic in this epic" — that line describes their scope, not setup's).
- **Styling**: minimal global CSS reset in `src/index.css` (no component library, no Tailwind) — matches `aamad.config.yml` `ui.visual_style: minimal`. Tailwind was considered (task explicitly offered it as an option) and rejected in favor of plain minimal CSS, since `aamad.config.yml` already names "minimal" and SAD §3 says "no heavy component library" — adding a Tailwind build step wasn't justified by either document. Recorded as an Assumption below.
- **Linting**: default Vite `oxlint` config (`.oxlintrc.json`) kept as-is (scaffold default); no additional ESLint setup added, since PRD/SAD are silent on a specific frontend linter and oxlint ships with the template.
- **Validation performed this action**: `npm run build` (`tsc -b && vite build`) succeeded — confirms the TypeScript + routing scaffold compiles cleanly. Build output (`dist/`) was deleted after validation (already gitignored via `frontend/.gitignore`).

### 4. Environment variables

Two `.env.example` files were created (no actual secret values, per `aamad-core.md` Security and Compliance and `aamad.config.yml` `security.forbid_committed_secrets: true`):

- `backend/.env.example`:
  - `ANTHROPIC_API_KEY` — required. LLM provider is Anthropic (`sad.md` §4, stakeholder-confirmed); per-agent model tiers (`claude-haiku-4-5`, `claude-sonnet-5`, ADR-004) are set in code/config, not env.
  - `DATABASE_URL` — optional, defaults documented (`sqlite:///./data/app.db`) for the local store (`sad.md` §4).
  - `PORT` — optional, defaults documented (`8000`) for the FastAPI/uvicorn bind port.
- `frontend/.env.example`:
  - `VITE_API_BASE_URL` — base URL of the FastAPI backend (defaults documented as `http://localhost:8000`), consumed by `@frontend.eng`/`@integration.eng` when wiring the API client.

Root `.gitignore` already covered `.env`/`.env.*` (with `!.env.example` exception) — no changes needed there.

### 5. How to install and run locally

**Backend** (uses a dedicated `backend/.venv` — Python 3.11.16 — **not** the root `.venv`, which runs Python 3.14.5 and cannot install `crewai` (`crewai` requires `<3.14`); see Open Questions/Audit below for how this was resolved during `*develop-be`):

```bash
cd backend
# create the venv once (uv-managed CPython 3.11; any 3.11.x interpreter works):
uv venv --python 3.11
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# Git Bash: source .venv/Scripts/activate
source .venv/Scripts/activate
pip install -e ".[dev]"
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000 --app-dir src
# Health check: curl http://localhost:8000/health -> {"status":"ok"}
```

**Manually exercising the API** (once the server above is running — a real `ANTHROPIC_API_KEY` in `backend/.env` is required for `/chat`, since it invokes the live 5-agent reasoning Crew; `/health` and an empty `/interactions` don't need one):

```bash
# Liveness check
curl http://localhost:8000/health
# -> {"status":"ok"}

# Send a chat inquiry (channel=chat, per sad.md SS4 POST /chat contract).
# Real LLM calls across 5 agents take ~15-20s — this is expected, not a hang.
# Try messages matching the 4 seeded scenario categories in domain_config.json:
# reservations_booking, checkin_checkout_billing, room_service_amenities, general_complaints.
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Can I get extra towels sent to my room?", "session_id": "manual-test-1"}'
# -> {"reply": "...", "escalated": false}   (or escalated: true if grounded==false /
#     confidence<=0.70 / sentiment_score>=0.75 / the 10s SAD SS7 ceiling was hit)

# Validation error case — omit a required field to confirm a clean 422, not a 500:
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "manual-test-1"}'
# -> 422 with a Pydantic field-error body

# View the interaction log (GET /interactions — deliberately pulled forward from
# SAD's Phase 3 sequencing into Phase 1 per operator decision; see backend.md SS12).
# Should show one record per /chat call above, most recent first.
curl http://localhost:8000/interactions

# --- Phase 2 (2026-08-21): email channel + escalation resolution ---

# Send an email inquiry (channel=email, per sad.md SS4 POST /email contract).
# Same InquiryFlow/reasoning-Crew pipeline as /chat, ~15-20s for a real response.
curl -X POST http://localhost:8000/email \
  -H "Content-Type: application/json" \
  -d '{"from": "guest@example.com", "subject": "Billing question", "body": "My folio shows an extra charge I do not recognize."}'
# -> {"reply_body": "...", "escalated": false}  (same escalation rules as /chat)

# To exercise the resolve path, first get an escalated interaction's id from
# GET /interactions (look for "outcome": "escalated"), then:
curl -X POST http://localhost:8000/escalations/<id>/resolve \
  -H "Content-Type: application/json" \
  -d '{"resolution_text": "Manually waived the duplicate charge and confirmed with the guest."}'
# -> {"status": "queued", "review_queue_id": "..."}
# Writes a candidate KB entry to the review_queue table (backend/data/app.db) —
# does NOT touch the live KB; that write path is Phase 3, not yet built.

# Unknown id -> clean 404, not a 500:
curl -X POST http://localhost:8000/escalations/does-not-exist/resolve \
  -H "Content-Type: application/json" \
  -d '{"resolution_text": "test"}'
# -> 404 {"error_code": "original_inquiry_not_found", "message": "..."}
```

FastAPI's interactive docs (Swagger UI) are also available at `http://localhost:8000/docs` while the server is running, if you'd rather test through a browser form than `curl`.

Run tests/lint/type-check once dependencies are installed (from `backend/`, with `.venv` activated, or via the venv's interpreter directly — `./.venv/Scripts/python.exe -m pytest` etc. — if not activated):

```bash
cd backend
pytest
ruff check .
mypy src
```

**Frontend** (from repo root):

```bash
cd frontend
npm install
cp .env.example .env.local   # adjust VITE_API_BASE_URL if backend runs elsewhere
npm run dev
# Vite dev server prints the local URL (default http://localhost:5173)
npm run build   # production build check
```

Both servers run independently for now — no proxy/integration wiring exists yet (that's `@integration.eng`'s `*integrate-api`, per `epics-index.md`).

## Sources

- `project-context/1.define/prd.md`
- `project-context/1.define/sad.md` (§1 Architecture Philosophy, §2 Multi-Agent System Specification incl. ADR-001–004, §3 Frontend Architecture, §4 Backend Architecture, §5 DevOps & Deployment, Implementation Guidance)
- `aamad.config.yml` (`runtime.target: crewai`, `ui.visual_style: minimal`, `coding_standards.type_checking: true`, `security.forbid_committed_secrets: true`, `testing.require_unit_tests`/`require_integration_tests: true`)
- `.claude/rules/aamad-core.md`, `.claude/rules/adapter-crewai.md`, `.claude/rules/delivery-workflow.md` (ruff CI mention), `.claude/rules/epics-index.md`
- `.claude/agents/project-mgr.md` (persona scope)
- Repo state at time of this action: `git status` clean on `define-stage` branch; no pre-existing `backend/`/`frontend/` directories (verified via `ls` before scaffolding — no conflict found)

## Assumptions

- **Packaging**: `pyproject.toml` (PEP 621 + hatchling) chosen over `requirements.txt` for the backend — PRD/SAD don't mandate either; justification in §2 above. Dependency versions are unpinned (`>=`) at scaffold time; `@backend.eng` should pin exact versions once real CrewAI Flow/Crew code depends on them, per `aamad-core.md`'s "Deterministic execution" principle.
- **Frontend routing library**: `react-router-dom` v7 chosen as the routing library — PRD/SAD name React+Vite+TS but don't name a router. Standard/lowest-friction default for a 3-route SPA.
- **Frontend styling**: plain minimal CSS chosen over Tailwind — both were explicitly offered as options; `aamad.config.yml ui.visual_style: minimal` plus `sad.md` §3 "no heavy component library" favored the simpler option with no added build tooling.
- **Domain config placement**: `domain_config.json`/`domain_config.schema.json` placed at `backend/` root (not `backend/src/app/`) to keep the domain-config layer visibly separate from the framework-config layer (`src/app/config/*.yaml`), per `sad.md` §2's "two separate configuration layers" language. This is a scaffold-time layout choice, not a SAD-mandated path.
- **Single Python environment (superseded)**: this action originally reused the pre-existing root `.venv` for the backend rather than creating a separate `backend/.venv`, since this is a single-developer 5-week project (PRD §8) with one Python dependency set. **Superseded during `*develop-be` (2026-08-19)**: the root `.venv` runs Python 3.14.5, which `crewai` cannot install against (`crewai` requires `<3.14`) — `@backend.eng` created a dedicated `backend/.venv` on Python 3.11.16 (via `uv`), already covered by the existing `.venv/` gitignore pattern. §5 above reflects the current, correct instructions.
- **No per-package READMEs beyond a short pointer**: the repo's existing convention (checked before scaffolding) is a single root `README.md` (framework-level) with no per-package READMEs. `backend/README.md` and `frontend/README.md` were kept minimal (pointer to this file) rather than duplicating install instructions, so `setup.md` remains the single source of truth per `aamad-core.md` "Reproducibility and provenance."
- Dependencies were **declared, not installed**, in this action (see §2) — `*install-dependencies` was not invoked this run.

## Open Questions

- Carried from `sad.md` (unresolved, not this persona's to resolve): actual project budget; which PII regulation (if any) must ultimately be complied with; MVP hosting/infrastructure target (`@devops.eng`, Phase 3).
- ~~Whether `@backend.eng` wants the backend `.venv` to remain the shared root `.venv` or split into its own once `crewai`'s dependency footprint is known~~ — **Resolved 2026-08-19**: split into `backend/.venv` (Python 3.11.16), forced by `crewai`'s `<3.14` requirement conflicting with the root `.venv`'s 3.14.5. See Assumptions and §5 above; also documented in `project-context/2.build/backend.md`.
- Exact FastAPI/uvicorn `--app-dir` / entrypoint convention (`app.main:app` under `src/`) is a scaffold-time default; `@backend.eng` may prefer a different `src`-layout invocation (e.g., via an installed console-script) once the app grows — not fixed by SAD.

## Audit

- **Timestamp**: 2026-08-13
- **Persona**: `project-mgr`
- **Action**: `setup-project`
- **Resolved runtime**: `crewai` (`AAMAD_TARGET_RUNTIME=crewai` from `.claude/settings.json`, consistent with `aamad.config.yml` `runtime.target: crewai` — no conflict to record)
- **Inputs used**: `project-context/1.define/prd.md`, `project-context/1.define/sad.md`, `aamad.config.yml`, `.claude/rules/aamad-core.md`, `.claude/rules/adapter-crewai.md`, `.claude/rules/delivery-workflow.md`, `.claude/rules/epics-index.md`, `.claude/agents/project-mgr.md`
- **Tools/versions used**: Python 3.14.5, pip 26.1.1, Node v24.16.0, npm 11.13.0, `npm create vite@latest` (`create-vite@9.1.2`, `react-ts` template), `react-router-dom@^7`. No LLM/model calls were made by this scaffolding action (deterministic file/tool operations only) — Prompt Trace omitted per `aamad-core.md` ("if omitted, the Audit must state why"): this action performed no generative/LLM-backed work, only file scaffolding and CLI tool invocations.
- **Prohibited actions confirmed avoided**: no CrewAI agent/task logic written (YAML stubs only), no FastAPI route logic beyond `GET /health`, no UI components beyond literal "coming soon" placeholders, no dependency installation performed (declared only).
- **Timestamp**: 2026-08-19
- **Persona**: `project-mgr`
- **Action**: `setup-project` (follow-up correction: §5 install/run instructions and the "Single Python environment" Assumption updated to reflect `@backend.eng`'s `*develop-be` resolution — `backend/.venv` on Python 3.11.16, not the root `.venv`, because `crewai` requires Python `<3.14` and the root `.venv` runs 3.14.5; Open Question resolved accordingly. Also added `.vscode/settings.json` to default the workspace Python interpreter to `backend/.venv` so local tooling picks up the correct environment without manual activation.)
