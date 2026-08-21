"""Pure-function escalation decision — sad.md §2 step 4 / ADR-002.

Deliberately NOT an LLM agent (ADR-002): reads exactly the three typed
fields already computed by the reasoning Crew (`confidence`,
`sentiment_score`, `grounded`) and evaluates fixed, pinned thresholds. This
is what makes `InquiryFlow`'s `@router` step a provably deterministic
function rather than opaque agent judgment — and, per sad.md §9, "directly
unit-testable, a deliberate benefit of that decision."

Thresholds pinned in sad.md §2 step 4 (2026-08-06, MVP starting values,
not final calibration — expected to move based on @qa-eng acceptance
results against AC-002/AC-003):
    - grounded == false            -> escalate (not tunable, AC-003)
    - confidence <= 0.70           -> escalate
    - sentiment_score >= 0.75      -> escalate
    - otherwise                    -> respond
"""

from __future__ import annotations

from typing import Literal

CONFIDENCE_ESCALATE_AT_OR_BELOW = 0.70
SENTIMENT_ESCALATE_AT_OR_ABOVE = 0.75

EscalationDecision = Literal["escalate", "respond"]


def evaluate_escalation(
    confidence: float, sentiment_score: float, grounded: bool
) -> EscalationDecision:
    """Evaluate the three OR'd escalation conditions from sad.md §2 step 4.

    Args:
        confidence: ClassificationResult.confidence (0.0-1.0).
        sentiment_score: SentimentResult.sentiment_score (0.0-1.0).
        grounded: ComposedResponse.grounded (carried over from
            KBRetrievalResult.match_found).

    Returns:
        "escalate" if any condition is true, else "respond".
    """
    if (
        grounded is False
        or confidence <= CONFIDENCE_ESCALATE_AT_OR_BELOW
        or sentiment_score >= SENTIMENT_ESCALATE_AT_OR_ABOVE
    ):
        return "escalate"
    return "respond"
