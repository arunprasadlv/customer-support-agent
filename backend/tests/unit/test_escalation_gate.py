"""Unit tests for app.flows.escalation_gate.evaluate_escalation and
app.flows.escalation_gate.contains_dispute_language — sad.md §9 "Unit:
escalation-router threshold logic (ADR-002 makes this a pure function -
directly unit-testable, a deliberate benefit of that decision)", extended
by the ADR-002 Addendum (2026-09-02) "Dispute/Chargeback Escalation
Signal".

Conditions under test (sad.md §2 step 4, pinned 2026-08-06, amended
2026-09-02):
    grounded == false OR confidence <= 0.70 OR sentiment_score >= 0.75
    OR dispute_language_detected == true
    -> escalate; else respond.

All `evaluate_escalation` calls below pass `dispute_language_detected`
explicitly (default `False` unless the test is specifically about that
condition) so each pre-existing boundary test continues to isolate exactly
one condition, per ADR-002's "independent OR'd conditions, no interaction"
design.
"""

from __future__ import annotations

import pytest

from app.flows.escalation_gate import contains_dispute_language, evaluate_escalation


def test_respond_when_all_conditions_are_safe() -> None:
    assert (
        evaluate_escalation(
            confidence=0.95,
            sentiment_score=0.10,
            grounded=True,
            dispute_language_detected=False,
        )
        == "respond"
    )


def test_escalates_when_not_grounded_even_with_high_confidence_and_calm_sentiment() -> None:
    # AC-003: not tunable, always escalate when there's no KB match.
    assert (
        evaluate_escalation(
            confidence=0.99,
            sentiment_score=0.0,
            grounded=False,
            dispute_language_detected=False,
        )
        == "escalate"
    )


@pytest.mark.parametrize("confidence", [0.70, 0.5, 0.0])
def test_escalates_when_confidence_at_or_below_threshold(confidence: float) -> None:
    assert (
        evaluate_escalation(
            confidence=confidence,
            sentiment_score=0.10,
            grounded=True,
            dispute_language_detected=False,
        )
        == "escalate"
    )


def test_respond_when_confidence_just_above_threshold() -> None:
    assert (
        evaluate_escalation(
            confidence=0.71,
            sentiment_score=0.10,
            grounded=True,
            dispute_language_detected=False,
        )
        == "respond"
    )


@pytest.mark.parametrize("sentiment_score", [0.75, 0.9, 1.0])
def test_escalates_when_sentiment_at_or_above_threshold(sentiment_score: float) -> None:
    assert (
        evaluate_escalation(
            confidence=0.95,
            sentiment_score=sentiment_score,
            grounded=True,
            dispute_language_detected=False,
        )
        == "escalate"
    )


def test_respond_when_sentiment_just_below_threshold() -> None:
    assert (
        evaluate_escalation(
            confidence=0.95,
            sentiment_score=0.74,
            grounded=True,
            dispute_language_detected=False,
        )
        == "respond"
    )


def test_escalates_when_multiple_conditions_true() -> None:
    assert (
        evaluate_escalation(
            confidence=0.10,
            sentiment_score=0.90,
            grounded=False,
            dispute_language_detected=False,
        )
        == "escalate"
    )


def test_boundary_values_are_exact_not_approximate() -> None:
    # Exactly-at-threshold values must escalate (<=, >=), not just past it.
    assert (
        evaluate_escalation(
            confidence=0.70,
            sentiment_score=0.0,
            grounded=True,
            dispute_language_detected=False,
        )
        == "escalate"
    )
    assert (
        evaluate_escalation(
            confidence=1.0,
            sentiment_score=0.75,
            grounded=True,
            dispute_language_detected=False,
        )
        == "escalate"
    )


# --- ADR-002 Addendum (2026-09-02): 4th condition, dispute_language_detected ---


def test_escalates_when_dispute_language_detected_even_with_all_other_signals_safe() -> None:
    # This is exactly the 2026-09-02 false-negative shape: high confidence,
    # calm-ish sentiment (below 0.75), grounded=True — only the dedicated
    # signal catches it.
    assert (
        evaluate_escalation(
            confidence=0.92,
            sentiment_score=0.70,
            grounded=True,
            dispute_language_detected=True,
        )
        == "escalate"
    )


def test_respond_when_dispute_language_not_detected_and_all_other_signals_safe() -> None:
    assert (
        evaluate_escalation(
            confidence=0.95,
            sentiment_score=0.10,
            grounded=True,
            dispute_language_detected=False,
        )
        == "respond"
    )


def test_dispute_language_detected_is_independent_of_other_conditions() -> None:
    # ADR-002 Addendum: "no reweighting, no compound scoring, no
    # interaction between conditions" — dispute_language_detected=True
    # escalates regardless of how safe every other input is, and =False
    # never escalates on its own.
    assert (
        evaluate_escalation(
            confidence=1.0,
            sentiment_score=0.0,
            grounded=True,
            dispute_language_detected=True,
        )
        == "escalate"
    )


# --- contains_dispute_language() ---


@pytest.mark.parametrize(
    "text",
    [
        "I want to dispute this",
        "This is going to a chargeback",
        "I'm doing a charge back on this",
        "I will dispute this charge",
        "I will dispute that charge",
        "Please dispute the charge",
        "I plan to contest this charge",
        "I will contest that charge",
        "I need to contest the charge",
        "I'm going to file a dispute with my bank",
        "I will file a chargeback",
        "I want to dispute a charge on my statement",
        "I am disputing the charge right now",
        "I am disputing this charge with my bank",
        # Case-insensitivity:
        "I WILL DISPUTE THAT CHARGE",
        "ChargeBack incoming",
        # The real 2026-09-02 false-negative message (redacted-text shape):
        "I am not looking to reschedule. As I wasnt given cancellation "
        "policy I would not want me to be charged like I said - I will "
        "dispute that charge",
    ],
)
def test_contains_dispute_language_true_positives(text: str) -> None:
    assert contains_dispute_language(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "I was double-charged for room service",
        "What will I be charged for late checkout?",
        "Can you explain the room service charge on my bill?",
        "What is the daily resort charge?",
        "I'd like to check availability for a room next weekend.",
        "The room was dirty when I checked in and I'm very unhappy.",
        "Can I get extra towels sent to my room?",
        "",
    ],
)
def test_contains_dispute_language_true_negatives_bare_charge_excluded(text: str) -> None:
    assert contains_dispute_language(text) is False


def test_contains_dispute_language_word_boundary_does_not_false_positive_on_substring() -> None:
    # "disputed"/"undisputed" contain "dispute" as a raw substring but are
    # different words — word-boundary matching must not fire on these.
    assert contains_dispute_language("The charge was already disputed last month") is False
    assert contains_dispute_language("This is an undisputed fact about the invoice") is False


def test_contains_dispute_language_matches_dispute_as_a_whole_word() -> None:
    # Bare "dispute" (not part of a longer phrase/word) must still match —
    # addendum's rationale: low false-positive risk in hotel-support context.
    assert contains_dispute_language("I have a dispute about this") is True
