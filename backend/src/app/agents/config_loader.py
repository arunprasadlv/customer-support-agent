"""Shared YAML config loader + Agent/Task factory helpers.

Reads the single shared `config/agents.yaml` / `config/tasks.yaml` files
(adapter-crewai.md's YAML-externalization rule) and builds `crewai.Agent`/
`crewai.Task` instances from them.

Why this project does NOT use CrewAI's `@CrewBase` decorator: `@CrewBase`
loads and maps *every* entry in the shared config files against the
methods defined on a single crew class (see
`crewai.project.crew_base.map_all_task_variables`), which raises a
`KeyError` the moment a task/agent belongs to a *different* crew than the
one being built (e.g. `redact_pii_task`'s `agent: pii_guard` reference
would fail to resolve inside `ReasoningCrew`, which only defines the 4
reasoning agents). Since sad.md/ADR-003 puts `pii_guard` in a separate,
standalone execution path from the 4-agent reasoning Crew, but this run's
task list asks for one shared `agents.yaml`/`tasks.yaml`, a small manual
loader (this module) that filters by name is used instead — config is
still fully externalized to YAML, just resolved by plain Python instead of
the decorator.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from crewai import LLM, Agent, Task
from crewai.tools import BaseTool

from app.schemas import task_outputs as _task_outputs_module

_CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
_AGENTS_YAML = _CONFIG_DIR / "agents.yaml"
_TASKS_YAML = _CONFIG_DIR / "tasks.yaml"

_DEFAULT_MAX_ITER = 12
_DEFAULT_MAX_RETRY_LIMIT = 2


def load_agents_config() -> dict[str, dict[str, Any]]:
    """Load and parse `config/agents.yaml` (all 5 agent definitions)."""
    with open(_AGENTS_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_tasks_config() -> dict[str, dict[str, Any]]:
    """Load and parse `config/tasks.yaml` (all 5 task definitions)."""
    with open(_TASKS_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_agent(
    agent_name: str,
    agents_config: dict[str, dict[str, Any]],
    tools: list[BaseTool] | None = None,
) -> Agent:
    """Build a `crewai.Agent` from an `agents.yaml` entry.

    adapter-crewai.md baselines applied when the YAML entry omits them:
    `max_iter<=12`, `max_retry_limit>=2`, `allow_delegation=false`.
    """
    cfg = agents_config[agent_name]
    llm: str | LLM = cfg["llm"]
    if "temperature" in cfg:
        llm = LLM(model=cfg["llm"], temperature=cfg["temperature"])
    return Agent(
        role=cfg["role"].strip(),
        goal=cfg["goal"].strip(),
        backstory=cfg["backstory"].strip(),
        llm=llm,
        allow_delegation=cfg.get("allow_delegation", False),
        max_iter=cfg.get("max_iter", _DEFAULT_MAX_ITER),
        max_retry_limit=cfg.get("max_retry_limit", _DEFAULT_MAX_RETRY_LIMIT),
        tools=tools or [],
    )


def _resolve_output_pydantic(name: str) -> type:
    """Resolve an `output_pydantic` string (e.g. "ClassificationResult")
    to the actual class in app.schemas.task_outputs — never redefine the
    typed contracts here (single source of truth per aamad-core.md)."""
    return getattr(_task_outputs_module, name)


def build_task(
    task_name: str,
    tasks_config: dict[str, dict[str, Any]],
    agent: Agent,
    context: list[Task] | None = None,
    tools: list[BaseTool] | None = None,
) -> Task:
    """Build a `crewai.Task` from a `tasks.yaml` entry.

    `context` (list of already-built upstream Task objects) must be passed
    in by the caller, resolved in dependency order — this module has no
    knowledge of cross-task ordering, that lives in the crew-assembly
    modules (`reasoning_crew.py`, `pii_guard.py`).
    """
    cfg = tasks_config[task_name]
    kwargs: dict[str, Any] = {
        "description": cfg["description"].strip(),
        "expected_output": cfg["expected_output"].strip(),
        "agent": agent,
    }
    if context is not None:
        kwargs["context"] = context
    if tools:
        kwargs["tools"] = tools
    if output_pydantic_name := cfg.get("output_pydantic"):
        kwargs["output_pydantic"] = _resolve_output_pydantic(output_pydantic_name)
    return Task(**kwargs)
