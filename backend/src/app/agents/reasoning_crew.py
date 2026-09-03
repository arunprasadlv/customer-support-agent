"""4-agent reasoning Crew: query_classifier -> knowledge_retriever ->
sentiment_analyzer -> response_composer.

sad.md §2 step 3: "reasoning_crew.kickoff(clean_text, domain_config) —
sequential process, task-context chaining passes intent -> retrieved_snippets
-> sentiment_score -> draft_response through the four agents in order, each
field typed per the Pydantic contracts". `Process.sequential` per
adapter-crewai.md's reproducible-MVP-build preference (§2 Runtime-Conditional
Configuration). `knowledge_retriever`'s task is bound to the `kb_search`
tool (ADR-005) via app.tools.crewai_tools.kb_search_tool.

pii_guard is intentionally NOT part of this Crew (ADR-003: standalone
agent, runs before the reasoning Crew is invoked at all) — see
app/agents/pii_guard.py.
"""

from __future__ import annotations

from crewai import Crew, Process, Task

from app.agents.config_loader import build_agent, build_task, load_agents_config, load_tasks_config
from app.domain.loader import DomainConfig
from app.persistence.trace_log import install_trace_listener
from app.tools.crewai_tools import kb_search_tool

_REASONING_TASK_ORDER = (
    "classify_task",
    "retrieve_knowledge_task",
    "analyze_sentiment_task",
    "compose_response_task",
)


def _taxonomy_summary(domain_config: DomainConfig) -> str:
    """Render domain_config.taxonomy as a plain-text list for
    classify_task's `{taxonomy_summary}` template placeholder. No
    hotel-specific strings here (AC-009) — content comes entirely from the
    loaded domain_config."""
    lines = [
        f"- {entry.intent}: {entry.label} (keywords: {', '.join(entry.keywords)})"
        for entry in domain_config.taxonomy
    ]
    return "\n".join(lines)


def build_reasoning_crew(domain_config: DomainConfig) -> tuple[Crew, dict[str, Task]]:
    """Build the 4-agent reasoning Crew and return it along with a
    name->Task map (used by the Flow to pull each task's typed
    `output_pydantic` result out of the CrewOutput after kickoff)."""
    # adapter-crewai.md Logging: install the Trace Log event listener before
    # kickoff so every task/LLM/tool lifecycle event this Crew emits is
    # captured — idempotent, safe to call on every build (see trace_log.py).
    install_trace_listener()

    agents_config = load_agents_config()
    tasks_config = load_tasks_config()

    query_classifier = build_agent("query_classifier", agents_config)
    knowledge_retriever = build_agent(
        "knowledge_retriever", agents_config, tools=[kb_search_tool]
    )
    sentiment_analyzer = build_agent("sentiment_analyzer", agents_config)
    response_composer = build_agent("response_composer", agents_config)

    agents_by_task = {
        "classify_task": query_classifier,
        "retrieve_knowledge_task": knowledge_retriever,
        "analyze_sentiment_task": sentiment_analyzer,
        "compose_response_task": response_composer,
    }

    tasks: dict[str, Task] = {}
    for task_name in _REASONING_TASK_ORDER:
        context_names = tasks_config[task_name].get("context") or []
        context_tasks = [tasks[name] for name in context_names]
        tasks[task_name] = build_task(
            task_name,
            tasks_config,
            agent=agents_by_task[task_name],
            context=context_tasks,
        )

    crew = Crew(
        agents=[query_classifier, knowledge_retriever, sentiment_analyzer, response_composer],
        tasks=[tasks[name] for name in _REASONING_TASK_ORDER],
        process=Process.sequential,
        verbose=False,
    )
    return crew, tasks


def kickoff_reasoning_crew(clean_text: str, domain_config: DomainConfig) -> dict[str, Task]:
    """Run the reasoning Crew once on `clean_text`.

    Returns the same name->Task map as `build_reasoning_crew`; after
    kickoff, each Task's `.output.pydantic` holds its typed result
    (ClassificationResult / KBRetrievalResult / SentimentResult /
    ComposedResponse per sad.md §2's Typed Task Outputs table).
    """
    crew, tasks = build_reasoning_crew(domain_config)
    crew.kickoff(
        inputs={
            "clean_text": clean_text,
            "taxonomy_summary": _taxonomy_summary(domain_config),
        }
    )
    return tasks
