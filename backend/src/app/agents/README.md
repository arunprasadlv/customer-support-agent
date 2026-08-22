# agents/

CrewAI agent/task/crew assembly (`*develop-be`, Phase 1). Reads role/goal/
task definitions from `../config/agents.yaml` and `../config/tasks.yaml`
per `project-context/1.define/sad.md` §2.

- `config_loader.py` — shared YAML loader + `Agent`/`Task` factory helpers
  (manual, not `@CrewBase` — see its module docstring for why).
- `reasoning_crew.py` — the 4-agent reasoning Crew (`query_classifier`,
  `knowledge_retriever`, `sentiment_analyzer`, `response_composer`),
  `Process.sequential`, context-chained classify -> retrieve -> sentiment
  -> compose (sad.md §2 step 3).
- `pii_guard.py` — the standalone 1-agent `pii_guard` Crew (ADR-003), bound
  to the deterministic `pii_detector` tool
  (`../tools/pii_detector.py` / `../tools/crewai_tools.py`).

Consumed by `../flows/inquiry_flow.py`.
