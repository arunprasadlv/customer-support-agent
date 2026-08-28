"""`InquiryFlow` — top-level orchestrator for one inquiry (sad.md §1 ADR-001,
§2 Task/Turn Orchestration). CrewAI `Flow`, one instance per inquiry,
regardless of channel.

Scope for this run (Phase 1 of MVP Build Sequencing, `channel=chat` only):
    1. @start  intake_normalize
    2. @listen pii_redact          (fail-closed, FR-011, ADR-003)
    3. @listen run_reasoning_crew  (4-agent Crew, sad.md §2 step 3)
    4. @router escalation_gate     (pure function, ADR-002)
    5. @listen deliver_response    (data structure only — no channel
                                    adapter/HTTP wiring; that is
                                    *implement-endpoint's job)
    6. @listen log_interaction     (always runs, both branches)

`EscalationResolutionFlow` and the Reviewer KB-write path are explicitly
Phase 2/3 (sad.md "MVP Build Sequencing") — NOT built in this run.

Flow-level hard ceiling: sad.md §7 pins `max_execution_time = 10` (2x the
p95 target) at the Flow level. This installed CrewAI version's `Flow`
class has no native flow-level execution-time cap (only `Agent.
max_execution_time`, a different, per-agent-per-task control) — see
backend.md Assumptions. This module enforces the ceiling itself via
`run_inquiry()`, which bounds `InquiryFlow.kickoff()` with a hard timeout
and degrades automatically to the escalate branch on expiry, matching
sad.md §7's stated behavior ("a stuck or abnormally slow run degrades
automatically to the escalate branch rather than hanging indefinitely").

DEVIATION FROM SAD §7 (recorded, not silent — operator-directed, 2026-08-24):
live verification during integration (backend.md's own latency spike, plus
`*verify-messageflow`) measured real 5-agent sequential Crew runs at
11-19s, well past the SAD's pinned 10s ceiling — every inquiry was hitting
the timeout branch and losing its real `query_text`/response in the
interaction log (see `run_inquiry`'s except-branch below). The ceiling was
raised to 30s as a crude, immediate unblock so inquiries actually complete
instead of timing out near-universally. This does NOT resolve the
underlying latency problem (sad.md §7's p95 target is still unmet) — it
only stops the timeout path from masking almost every real result. Proper
fixes (parallelizing independent reasoning-Crew tasks, trimming prompts,
reconsidering per-agent model tiers) remain open, see backend.md.
"""

from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import UTC, datetime
from typing import Any

from crewai.flow.flow import Flow, listen, or_, router, start

from app.agents.pii_guard import kickoff_pii_guard
from app.agents.reasoning_crew import kickoff_reasoning_crew
from app.domain.loader import get_domain_config
from app.flows.escalation_gate import EscalationDecision, evaluate_escalation
from app.persistence.interaction_log import record_interaction
from app.schemas.task_outputs import (
    ClassificationResult,
    ComposedResponse,
    KBRetrievalResult,
    RedactionResult,
    SentimentResult,
)

logger = logging.getLogger(__name__)

# sad.md §7 pins 10s (2x the p95 target); raised to 30s as a documented
# deviation — see module docstring "DEVIATION FROM SAD §7" above.
MAX_EXECUTION_TIME_SECONDS = 30

ESCALATION_MESSAGE = (
    "Thanks for reaching out. I've flagged this for a team member to review "
    "personally, and someone will follow up with you shortly."
)
TIMEOUT_ESCALATION_MESSAGE = (
    "Thanks for your patience. This is taking longer than expected, so I've "
    "flagged it for a team member to review personally."
)


class PiiGuardFailure(RuntimeError):
    """Raised when pii_guard fails to execute. InquiryFlow treats this as a
    fail-closed halt (sad.md §2 Error handling) — no unredacted text may be
    passed forward (FR-011)."""


class InquiryFlow(Flow):
    """One instance per inquiry. State is a plain dict (CrewAI's default
    state type); `kickoff(inputs={...})` seeds it with the raw inquiry
    (channel, raw_text, sender_id)."""

    @start()
    def intake_normalize(self) -> dict[str, Any]:
        """Step 1: normalize the raw inquiry to
        {channel, raw_text, sender_id, timestamp}."""
        intake = {
            "channel": self.state.get("channel", "chat"),
            "raw_text": self.state.get("raw_text", ""),
            "sender_id": self.state.get("sender_id", "anonymous"),
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self.state["intake"] = intake
        return intake

    @listen(intake_normalize)
    def pii_redact(self, intake: dict[str, Any]) -> RedactionResult:
        """Step 2: pii_guard redacts/masks PII in raw_text before anything
        else touches it (FR-011, ADR-003). Fail-closed: on any pii_guard
        execution failure, halt rather than pass unredacted text forward.
        """
        try:
            task = kickoff_pii_guard(intake["raw_text"])
            result = task.output.pydantic if task.output is not None else None
            if not isinstance(result, RedactionResult):
                raise PiiGuardFailure(
                    "pii_guard did not return a valid RedactionResult "
                    f"(got {type(result).__name__ if result is not None else None})"
                )
        except Exception as exc:  # noqa: BLE001 - fail-closed catch-all by design
            self.state["diagnostic"] = f"pii_guard failure: {exc}"
            self._log_diagnostic_halt(intake, str(exc))
            raise PiiGuardFailure(str(exc)) from exc

        self.state["redaction"] = result
        return result

    @listen(pii_redact)
    def run_reasoning_crew(self, redaction: RedactionResult) -> dict[str, Any]:
        """Step 3: kick off the 4-agent reasoning Crew on clean_text +
        domain config (sad.md §2 step 3)."""
        domain_config = get_domain_config()
        tasks = kickoff_reasoning_crew(redaction.clean_text, domain_config)

        for task_name, task in tasks.items():
            if task.output is None:
                raise TypeError(f"{task_name} produced no output")

        classification = tasks["classify_task"].output.pydantic  # type: ignore[union-attr]
        retrieval = tasks["retrieve_knowledge_task"].output.pydantic  # type: ignore[union-attr]
        sentiment = tasks["analyze_sentiment_task"].output.pydantic  # type: ignore[union-attr]
        composed = tasks["compose_response_task"].output.pydantic  # type: ignore[union-attr]

        if not isinstance(classification, ClassificationResult):
            raise TypeError("classify_task did not return a ClassificationResult")
        if not isinstance(retrieval, KBRetrievalResult):
            raise TypeError("retrieve_knowledge_task did not return a KBRetrievalResult")
        if not isinstance(sentiment, SentimentResult):
            raise TypeError("analyze_sentiment_task did not return a SentimentResult")
        if not isinstance(composed, ComposedResponse):
            raise TypeError("compose_response_task did not return a ComposedResponse")

        outcome = {
            "classification": classification,
            "retrieval": retrieval,
            "sentiment": sentiment,
            "composed": composed,
        }
        self.state["outcome"] = outcome
        return outcome

    @router(run_reasoning_crew)
    def escalation_gate(self, outcome: dict[str, Any]) -> EscalationDecision:
        """Step 4: pure-function router (ADR-002) — reads exactly
        `confidence`, `sentiment_score`, `grounded`."""
        decision = evaluate_escalation(
            confidence=outcome["classification"].confidence,
            sentiment_score=outcome["sentiment"].sentiment_score,
            grounded=outcome["composed"].grounded,
        )
        self.state["escalation_decision"] = decision
        return decision

    @listen(or_("escalate", "respond"))
    def deliver_response(self, decision: EscalationDecision) -> dict[str, Any]:
        """Step 5: produce the reply payload (escalation notice or
        draft_response) — a plain data structure only. No HTTP/channel
        adapter wiring here; that is *implement-endpoint's responsibility.
        """
        outcome = self.state["outcome"]
        composed: ComposedResponse = outcome["composed"]

        if decision == "escalate":
            payload = {
                "escalated": True,
                "reply": ESCALATION_MESSAGE,
                "reason": self._escalation_reason(outcome),
            }
        else:
            payload = {"escalated": False, "reply": composed.draft_response, "reason": None}

        self.state["response_payload"] = payload
        return payload

    @listen(deliver_response)
    def log_interaction(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Step 6: always runs (both branches) — persists one
        interaction-log record (sad.md §2 step 6 / §6).

        Uses `self.state["inquiry_id"]` when present — `run_inquiry()` seeds
        this via `kickoff(inputs={...})` so the timeout path (which may log
        its own escalation record for the same inquiry while this flow
        keeps running in the background — see `run_inquiry()`) and this
        step share one id. `record_interaction`'s `INSERT OR IGNORE` then
        makes whichever write lands second a no-op instead of a duplicate
        row (backend.md §"double-log fix"). Falls back to a fresh id for
        direct `InquiryFlow().kickoff()` callers (e.g. tests) that don't
        seed `inquiry_id`.
        """
        intake = self.state["intake"]
        redaction: RedactionResult = self.state["redaction"]
        outcome = self.state["outcome"]

        record_interaction(
            {
                "id": self.state.get("inquiry_id") or str(uuid.uuid4()),
                "created_at": intake["timestamp"],
                "channel": intake["channel"],
                "sender_id": intake["sender_id"],
                "query_text": redaction.clean_text,
                "intent": outcome["classification"].intent,
                "confidence": outcome["classification"].confidence,
                "sentiment_score": outcome["sentiment"].sentiment_score,
                "sentiment_label": outcome["sentiment"].sentiment_label,
                "match_found": outcome["retrieval"].match_found,
                "grounded": outcome["composed"].grounded,
                "response_text": payload["reply"],
                "outcome": "escalated" if payload["escalated"] else "responded",
                "redaction_actions": [a.model_dump() for a in redaction.redaction_actions],
            }
        )
        return payload

    @staticmethod
    def _escalation_reason(outcome: dict[str, Any]) -> list[str]:
        reasons = []
        if outcome["composed"].grounded is False:
            reasons.append("not_grounded")
        if outcome["classification"].confidence <= 0.70:
            reasons.append("low_confidence")
        if outcome["sentiment"].sentiment_score >= 0.75:
            reasons.append("high_frustration")
        return reasons

    def _log_diagnostic_halt(self, intake: dict[str, Any], diagnostic: str) -> None:
        """Persist a Diagnostic record on pii_guard failure (sad.md §2
        Error handling). Never persists raw_text — the failure means we
        cannot trust it's been redacted, so only a placeholder is stored.
        """
        try:
            record_interaction(
                {
                    "id": str(uuid.uuid4()),
                    "created_at": intake["timestamp"],
                    "channel": intake["channel"],
                    "sender_id": intake["sender_id"],
                    "query_text": "[UNAVAILABLE - PII GUARD FAILURE, RAW TEXT NOT PERSISTED]",
                    "outcome": "diagnostic_halt",
                    "diagnostic": diagnostic,
                }
            )
        except Exception:  # noqa: BLE001 - logging must never mask the original failure
            logger.exception("Failed to persist diagnostic_halt record")


def run_inquiry(
    channel: str,
    raw_text: str,
    sender_id: str,
    timeout_seconds: int = MAX_EXECUTION_TIME_SECONDS,
) -> dict[str, Any]:
    """Public entry point: run one InquiryFlow to completion, bounded by
    the sad.md §7 hard ceiling (`max_execution_time = 10`).

    This is the only supported way to invoke InquiryFlow from Python/pytest
    for this run (per this run's scope boundary — no FastAPI route wiring
    here; see *implement-endpoint).

    On timeout, degrades automatically to the escalate branch and logs an
    interaction record rather than hanging or raising (sad.md §7: "a stuck
    or abnormally slow run degrades automatically to the escalate branch").
    Note: the underlying flow thread cannot be forcibly killed once
    started (a stdlib/Python limitation, not a sad.md gap) — see
    backend.md Assumptions.

    Two related fixes (backend.md §"double-log fix", 2026-08-20): (1) the
    pool is created and shut down manually (`shutdown(wait=False)`) instead
    of via a `with` block, so this function actually returns at
    ~`timeout_seconds` instead of blocking until the abandoned background
    flow thread finishes on its own; (2) a shared `inquiry_id` is generated
    here and passed into `kickoff(inputs=...)` so that if the abandoned
    thread later reaches its own `log_interaction` step, it writes the
    *same* row id as this function's own timeout-path write — combined
    with `record_interaction`'s `INSERT OR IGNORE`, only the first of the
    two writes to land is persisted (first-writer-wins, order-independent),
    guaranteeing exactly one interaction-log record per inquiry.

    The returned dict always carries `inquiry_id` (the same id used for the
    interaction-log row) alongside `escalated`/`reply`/`reason` — existing
    callers (`POST /chat` builds `ChatResponse` from only `reply`/
    `escalated`, ignoring extra keys) are unaffected; it exists so tests
    and any future caller can look up this exact inquiry's log row
    deterministically instead of guessing from db row counts, which is
    unsafe once an abandoned post-timeout background thread is in play
    (see tests/integration/test_inquiry_flow.py).
    """
    inquiry_id = str(uuid.uuid4())
    inputs = {
        "channel": channel,
        "raw_text": raw_text,
        "sender_id": sender_id,
        "inquiry_id": inquiry_id,
    }

    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(InquiryFlow().kickoff, inputs=inputs)
    try:
        result = future.result(timeout=timeout_seconds)
        result["inquiry_id"] = inquiry_id
        return result
    except FutureTimeoutError:
        timestamp = datetime.now(UTC).isoformat()
        record_interaction(
            {
                "id": inquiry_id,
                "created_at": timestamp,
                "channel": channel,
                "sender_id": sender_id,
                "query_text": "[UNAVAILABLE - FLOW EXCEEDED MAX_EXECUTION_TIME]",
                "outcome": "escalated",
                "diagnostic": (
                    f"InquiryFlow exceeded max_execution_time={timeout_seconds}s "
                    "hard ceiling (sad.md §7)"
                ),
            }
        )
        return {
            "escalated": True,
            "reply": TIMEOUT_ESCALATION_MESSAGE,
            "reason": ["max_execution_time_exceeded"],
            "inquiry_id": inquiry_id,
        }
    finally:
        # Do NOT use `with ThreadPoolExecutor(...) as pool:` here — its
        # `__exit__` calls `shutdown(wait=True)` unconditionally, which
        # blocks the caller until the background flow thread actually
        # finishes (defeating the whole point of the timeout above).
        # `wait=False` releases the executor's bookkeeping without waiting;
        # the submitted thread (if still running past the timeout) keeps
        # running to completion in the background regardless of this flag
        # — Python cannot forcibly kill it — but this function itself no
        # longer blocks on that.
        pool.shutdown(wait=False)
