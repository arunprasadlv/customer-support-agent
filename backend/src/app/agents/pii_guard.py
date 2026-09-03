"""Standalone `pii_guard` agent (ADR-003) — not a member of the reasoning
Crew, runs as its own single-agent, single-task Crew immediately after
intake normalization and before the reasoning Crew is invoked at all
(FR-011). Bound to the deterministic `pii_detector` tool
(app.tools.crewai_tools.pii_detector_tool) so its actual redaction
decisions are pattern-based, not LLM-guessed (this run's PII-detection
design decision, recorded in backend.md Assumptions) — the agent's job is
to invoke the tool and relay its output.
"""

from __future__ import annotations

from crewai import Crew, Process, Task

from app.agents.config_loader import build_agent, build_task, load_agents_config, load_tasks_config
from app.persistence.trace_log import install_trace_listener
from app.tools.crewai_tools import pii_detector_tool


def build_pii_guard_crew() -> tuple[Crew, Task]:
    """Build the standalone 1-agent pii_guard Crew.

    adapter-crewai.md Logging: install the Trace Log event listener before
    kickoff (idempotent — see trace_log.py). pii_guard runs its own
    standalone Crew, not a member of reasoning_crew.py's Crew, but CrewAI's
    event bus is process-global, so this one call covers pii_guard's own
    task/LLM/tool lifecycle events the same way reasoning_crew.py's call
    covers its four agents — no separate per-agent hook mechanism is
    needed. Trace entries for this agent's `pii_detector` tool call are
    still redacted like every other trace entry (trace_log.py's `_redact`)
    even though the tool's raw input legitimately carries un-redacted PII.
    """
    install_trace_listener()

    agents_config = load_agents_config()
    tasks_config = load_tasks_config()

    pii_guard_agent = build_agent("pii_guard", agents_config, tools=[pii_detector_tool])
    redact_task = build_task("redact_pii_task", tasks_config, agent=pii_guard_agent, context=[])

    crew = Crew(
        agents=[pii_guard_agent],
        tasks=[redact_task],
        process=Process.sequential,
        verbose=False,
    )
    return crew, redact_task


def kickoff_pii_guard(raw_text: str) -> Task:
    """Run pii_guard once on `raw_text`. Returns the Task; after kickoff,
    `.output.pydantic` holds a `RedactionResult` (sad.md §2 Typed Task
    Outputs). Raises on any execution failure — callers (InquiryFlow) must
    treat that as fail-closed per sad.md §2 Error handling: halt rather
    than pass unredacted text forward.
    """
    crew, redact_task = build_pii_guard_crew()
    crew.kickoff(inputs={"raw_text": raw_text})
    return redact_task
