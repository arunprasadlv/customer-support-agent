# Deploy

## Diagnostic — Halt and Report

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
