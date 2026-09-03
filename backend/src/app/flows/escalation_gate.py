"""Pure-function escalation decision — sad.md §2 step 4 / ADR-002, amended by
the ADR-002 Addendum (2026-09-02) "Dispute/Chargeback Escalation Signal".

Deliberately NOT an LLM agent (ADR-002): reads exactly the typed
fields already computed by the reasoning Crew (`confidence`,
`sentiment_score`, `grounded`) plus one deterministically-derived boolean
(`dispute_language_detected`) and evaluates fixed, pinned thresholds/phrase
matches. This is what makes `InquiryFlow`'s `@router` step a provably
deterministic function rather than opaque agent judgment — and, per sad.md
§9, "directly unit-testable, a deliberate benefit of that decision."

Thresholds pinned in sad.md §2 step 4 (2026-08-06, MVP starting values,
not final calibration — expected to move based on @qa-eng acceptance
results against AC-002/AC-003):
    - grounded == false               -> escalate (not tunable, AC-003)
    - confidence <= 0.70              -> escalate
    - sentiment_score >= 0.75         -> escalate
    - dispute_language_detected       -> escalate (ADR-002 Addendum, 2026-09-02)
    - otherwise                       -> respond

`contains_dispute_language()` is a separate pure function (ADR-002 Addendum
"Function signature recommendation", option 2): it computes the boolean
from redacted text at the call site (`InquiryFlow.escalation_gate()`, which
must pass `redaction.clean_text` — never raw text, per FR-011/ADR-003).
`evaluate_escalation()` itself stays a pure function over four scalars and
never touches text directly.
"""

from __future__ import annotations

import re
from typing import Literal

CONFIDENCE_ESCALATE_AT_OR_BELOW = 0.70
SENTIMENT_ESCALATE_AT_OR_ABOVE = 0.75

# ADR-002 Addendum (2026-09-02), pinned phrase list — case-insensitive
# substring/word-boundary match against `redaction.clean_text`. Bare
# "charge" is deliberately excluded (routinely appears in ordinary
# non-dispute billing questions, e.g. "what will I be charged"). Bare
# "dispute"/"chargeback" ARE included per the addendum's rationale: neither
# word has an unrelated common hotel-support usage, unlike "charge".
DISPUTE_LANGUAGE_PHRASES = (
    "dispute",
    "chargeback",
    "charge back",
    "dispute this charge",
    "dispute that charge",
    "dispute the charge",
    "contest this charge",
    "contest that charge",
    "contest the charge",
    "file a dispute",
    "file a chargeback",
    "dispute a charge",
    "disputing the charge",
    "disputing this charge",
)

# Word-boundary regex, case-insensitive, one alternative per pinned phrase.
# Phrases are `re.escape`d (defensive — none currently contain regex
# metacharacters) and joined with `\b...\b` boundaries on each side so e.g.
# "dispute" does not match inside an unrelated longer word, while still
# matching regardless of surrounding punctuation/whitespace.
_DISPUTE_LANGUAGE_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(phrase) for phrase in DISPUTE_LANGUAGE_PHRASES) + r")\b",
    re.IGNORECASE,
)

EscalationDecision = Literal["escalate", "respond"]


def contains_dispute_language(text: str) -> bool:
    """Deterministic, case-insensitive substring/word-boundary check for
    dispute/chargeback language (ADR-002 Addendum, 2026-09-02).

    Must be called with already-PII-redacted text (`redaction.clean_text`)
    — never raw text (FR-011/ADR-003). No LLM call, no fuzzy/semantic
    matching, no stemming beyond simple case-folding.

    Args:
        text: PII-redacted guest message text.

    Returns:
        True iff any pinned phrase in `DISPUTE_LANGUAGE_PHRASES` matches
        `text` as a case-insensitive word-boundary substring.
    """
    return bool(_DISPUTE_LANGUAGE_PATTERN.search(text))


def evaluate_escalation(
    confidence: float,
    sentiment_score: float,
    grounded: bool,
    dispute_language_detected: bool,
) -> EscalationDecision:
    """Evaluate the four OR'd escalation conditions from sad.md §2 step 4,
    as amended by the ADR-002 Addendum (2026-09-02).

    Args:
        confidence: ClassificationResult.confidence (0.0-1.0).
        sentiment_score: SentimentResult.sentiment_score (0.0-1.0).
        grounded: ComposedResponse.grounded (carried over from
            KBRetrievalResult.match_found).
        dispute_language_detected: precomputed result of
            `contains_dispute_language(redaction.clean_text)` — this
            function takes the bool, not raw text, so it stays a pure
            function over scalars (ADR-002 Addendum "Function signature
            recommendation", option 2).

    Returns:
        "escalate" if any condition is true, else "respond".
    """
    if (
        grounded is False
        or confidence <= CONFIDENCE_ESCALATE_AT_OR_BELOW
        or sentiment_score >= SENTIMENT_ESCALATE_AT_OR_ABOVE
        or dispute_language_detected is True
    ):
        return "escalate"
    return "respond"
