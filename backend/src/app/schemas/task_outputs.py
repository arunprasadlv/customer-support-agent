"""Typed Pydantic contracts for every reasoning-Crew task and pii_guard's task.

Source of truth: project-context/1.define/sad.md §2 "Typed Task Outputs
(Pydantic contracts)". Every field here exists because escalation_gate
(InquiryFlow's @router step, ADR-002) reads exactly three typed fields
(`confidence`, `sentiment_score`, `grounded`) as a pure function — no task
in the reasoning Crew or pii_guard is allowed to return free-form prose to
a downstream step. Do not add fields not named in sad.md §2 without
updating the SAD first (aamad-core.md: outputs must trace to PRD/SAD/SFS).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RedactionAction(BaseModel):
    """One PII redaction/masking action taken by pii_guard (NFR-006 audit trail)."""

    entity_type: str = Field(
        ..., description="Detected PII category, e.g. 'email', 'phone', 'name', 'account_number'."
    )
    span_start: int = Field(..., ge=0, description="Start offset in the original raw_text.")
    span_end: int = Field(..., ge=0, description="End offset (exclusive) in the original raw_text.")
    method: Literal["mask", "remove"] = Field(
        ..., description="Whether the span was masked (e.g. '[REDACTED]') or removed entirely."
    )


class RedactionResult(BaseModel):
    """Output of redact_pii_task (pii_guard). Gates FR-011: no other component
    may see raw_text — only clean_text is passed forward."""

    clean_text: str = Field(..., description="raw_text with all detected PII masked/removed.")
    redaction_actions: list[RedactionAction] = Field(default_factory=list)


class ClassificationResult(BaseModel):
    """Output of classify_task (query_classifier). intent drives ADR-005's
    KB filter; confidence is escalation_gate input #1."""

    intent: str = Field(..., description="Matches a taxonomy[].intent value from domain_config.json.")
    confidence: float = Field(..., ge=0.0, le=1.0)


class KBSnippet(BaseModel):
    kb_entry_id: str
    content: str
    relevance_score: float = Field(..., ge=0.0, le=1.0)


class KBRetrievalResult(BaseModel):
    """Output of retrieve_knowledge_task (knowledge_retriever). match_found
    (via ADR-005's 0.20 floor) is what keeps AC-003's no-fabrication rule
    honest — an empty/low-relevance retrieval must not be papered over."""

    retrieved_snippets: list[KBSnippet] = Field(default_factory=list)
    match_found: bool


class SentimentResult(BaseModel):
    """Output of analyze_sentiment_task (sentiment_analyzer). sentiment_score
    is escalation_gate input #2 (>= 0.75 -> escalate, sad.md §2 step 4)."""

    sentiment_score: float = Field(..., ge=0.0, le=1.0)
    sentiment_label: Literal["neutral", "frustrated", "angry"]


class ComposedResponse(BaseModel):
    """Output of compose_response_task (response_composer). `grounded` is
    carried over from KBRetrievalResult.match_found by orchestration code,
    not self-reported by the LLM — this is escalation_gate input #3 and the
    structural enforcement of AC-003 ("never fabricate when the KB has no
    match")."""

    draft_response: str
    grounded: bool
