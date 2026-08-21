"""`EscalationResolutionFlow` — sad.md §2's second, decoupled CrewAI
`Flow`. Phase 2 of sad.md's "MVP Build Sequencing" ("Add
EscalationResolutionFlow — now needed since Phase 1 produces real
escalations to resolve").

Triggered whenever a (simulated) human operator submits a resolution for
an escalated interaction — this does not keep `InquiryFlow` waiting;
escalation and its eventual human resolution are asynchronous by nature
(sad.md §2):

    1. Receive `{original_inquiry_id, resolution_text}`.
    2. Write a candidate KB entry to the review queue, linked to the
       original query (FR-008, AC-010).

Explicitly out of scope here — sad.md's "Third, fully separate write path"
(Phase 3, the *only* path that can modify the live KB, NFR-008): this flow
never reads or writes `domain_config.json` / a live `knowledge_base` table.
No approve/reject logic. It only ever writes to the `review_queue` table
(`app.persistence.review_queue`).

Unlike `InquiryFlow`, this flow has no LLM-backed steps at all — it is
plain deterministic orchestration over local persistence — so sad.md §7's
`max_execution_time` hard-ceiling wrapper (`run_inquiry`'s
`ThreadPoolExecutor`/timeout pattern) does not apply here; there is
nothing here that can hang on a slow model call. `run_escalation_
resolution()` below therefore calls `.kickoff()` directly, synchronously,
with no timeout wrapper — a deliberate, narrower design than
`run_inquiry()`, not an oversight (see backend.md Assumptions).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from crewai.flow.flow import Flow, listen, start

from app.persistence.interaction_log import get_interaction_by_id
from app.persistence.review_queue import record_review_queue_entry

logger = logging.getLogger(__name__)


class OriginalInquiryNotFound(RuntimeError):
    """Raised when `original_inquiry_id` does not correspond to any
    persisted interaction-log record. sad.md §2 requires the candidate
    entry be "linked to the original query" — a dangling link is not a
    valid resolution, so this fails closed (no review-queue row is
    written) rather than writing an orphaned candidate."""


class EscalationResolutionFlow(Flow):
    """One instance per resolution submission. State seeded via
    `kickoff(inputs={original_inquiry_id, resolution_text, ...})`."""

    @start()
    def receive_resolution(self) -> dict[str, Any]:
        """Step 1: receive `{original_inquiry_id, resolution_text}`."""
        resolution = {
            "original_inquiry_id": self.state.get("original_inquiry_id", ""),
            "resolution_text": self.state.get("resolution_text", ""),
        }
        self.state["resolution"] = resolution
        return resolution

    @listen(receive_resolution)
    def build_candidate_entry(self, resolution: dict[str, Any]) -> dict[str, Any]:
        """Step 2 (part of sad.md §2 step 2 "write a candidate KB entry"):
        look up the original interaction by its interaction_log `id` and
        shape a candidate KB entry from it plus the operator's
        `resolution_text`.

        Candidate shape mirrors ADR-005's `knowledge_base[]` entry fields
        (`intent`, `section`, `keywords`, `content`) so Phase 3's Reviewer
        approve/edit/reject step can map it onto a real KB entry with no
        reshaping — `candidate_intent` is inherited from the original
        interaction's classified intent when available (most escalations
        do have one; the `grounded == false` / timeout-diagnostic paths may
        not, hence `| None`). `candidate_keywords` starts empty — this
        phase does not attempt keyword extraction; that is left for the
        Reviewer to fill in at approval time (Phase 3), not invented here.
        """
        original = get_interaction_by_id(resolution["original_inquiry_id"])
        if original is None:
            raise OriginalInquiryNotFound(
                f"No interaction_log record found for id={resolution['original_inquiry_id']!r}"
            )

        candidate = {
            "original_query_text": original.get("query_text"),
            "candidate_intent": original.get("intent"),
            "candidate_section": "operator_resolution",
            "candidate_keywords": [],
            "candidate_content": resolution["resolution_text"],
        }
        self.state["candidate"] = candidate
        return candidate

    @listen(build_candidate_entry)
    def write_to_review_queue(self, candidate: dict[str, Any]) -> dict[str, Any]:
        """Step 3: persist the candidate entry to the review queue ONLY —
        never touches the live KB (Phase 3's job, NFR-008)."""
        review_queue_id = self.state.get("review_queue_id") or str(uuid.uuid4())
        record = {
            "id": review_queue_id,
            "created_at": datetime.now(UTC).isoformat(),
            "original_inquiry_id": self.state["resolution"]["original_inquiry_id"],
            "resolution_text": self.state["resolution"]["resolution_text"],
            **candidate,
        }
        record_review_queue_entry(record)
        self.state["review_queue_id"] = review_queue_id
        return {"review_queue_id": review_queue_id, **record}


def run_escalation_resolution(original_inquiry_id: str, resolution_text: str) -> dict[str, Any]:
    """Public entry point: run one `EscalationResolutionFlow` to
    completion. Synchronous, no timeout wrapper (see module docstring — no
    LLM calls on this path).

    Raises `OriginalInquiryNotFound` if `original_inquiry_id` doesn't match
    any persisted interaction-log record — callers (the `POST
    /escalations/{id}/resolve` route) should map that to a 404.

    Returns `{review_queue_id, original_inquiry_id, original_query_text,
    resolution_text, candidate_intent, candidate_section,
    candidate_keywords, candidate_content, status, created_at, id}` — the
    full persisted review-queue record plus the `review_queue_id` alias for
    convenience.
    """
    review_queue_id = str(uuid.uuid4())
    flow = EscalationResolutionFlow()
    result: dict[str, Any] = flow.kickoff(
        inputs={
            "original_inquiry_id": original_inquiry_id,
            "resolution_text": resolution_text,
            "review_queue_id": review_queue_id,
        }
    )
    return result
