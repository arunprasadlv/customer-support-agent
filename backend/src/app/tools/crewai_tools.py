"""CrewAI `Tool` wrappers around the project's pure-function domain tools.

These wrap `app.domain.loader.kb_search` (ADR-005) and
`app.tools.pii_detector.detect_pii` (this run's PII-detection design
decision) so agents (`knowledge_retriever`, `pii_guard`) can call them via
CrewAI's standard tool-calling mechanism. The wrappers add no logic of
their own — they only adapt the pure functions' signatures to what
`crewai.tools.tool` expects (keyword args in, a Pydantic model out).
"""

from __future__ import annotations

from crewai.tools import tool

from app.domain.loader import kb_search as _kb_search
from app.schemas.task_outputs import KBRetrievalResult, RedactionResult
from app.tools.pii_detector import detect_pii as _detect_pii


@tool("kb_search")
def kb_search_tool(intent: str, query_text: str) -> KBRetrievalResult:
    """Search the active domain's knowledge base for entries matching the
    given classified `intent`, scored by keyword overlap against
    `query_text` (ADR-005: keyword/section-scored retrieval, floor 0.20,
    top 3 — no vector store). Returns `retrieved_snippets` and
    `match_found`; `match_found=false` means nothing cleared the relevance
    floor and no answer should be fabricated.
    """
    return _kb_search(intent=intent, query_text=query_text)


@tool("pii_detector")
def pii_detector_tool(text: str) -> RedactionResult:
    """Detect and mask personally identifiable information (email, phone,
    account/confirmation numbers, names) in `text` using deterministic
    pattern matching — no guessing. Returns `clean_text` (PII masked) and
    `redaction_actions` (one explainable span per detected entity). Return
    this output exactly as given; do not alter `clean_text` or
    `redaction_actions`.
    """
    return _detect_pii(text)
