"""Unit tests for app.flows.escalation_gate.evaluate_escalation — sad.md §9
"Unit: escalation-router threshold logic (ADR-002 makes this a pure
function - directly unit-testable, a deliberate benefit of that
decision)".

Thresholds under test (sad.md §2 step 4, pinned 2026-08-06):
    grounded == false OR confidence <= 0.70 OR sentiment_score >= 0.75
    -> escalate; else respond.
"""

from __future__ import annotations

import pytest

from app.flows.escalation_gate import evaluate_escalation


def test_respond_when_all_conditions_are_safe() -> None:
    assert evaluate_escalation(confidence=0.95, sentiment_score=0.10, grounded=True) == "respond"


def test_escalates_when_not_grounded_even_with_high_confidence_and_calm_sentiment() -> None:
    # AC-003: not tunable, always escalate when there's no KB match.
    assert evaluate_escalation(confidence=0.99, sentiment_score=0.0, grounded=False) == "escalate"


@pytest.mark.parametrize("confidence", [0.70, 0.5, 0.0])
def test_escalates_when_confidence_at_or_below_threshold(confidence: float) -> None:
    assert (
        evaluate_escalation(confidence=confidence, sentiment_score=0.10, grounded=True)
        == "escalate"
    )


def test_respond_when_confidence_just_above_threshold() -> None:
    assert (
        evaluate_escalation(confidence=0.71, sentiment_score=0.10, grounded=True) == "respond"
    )


@pytest.mark.parametrize("sentiment_score", [0.75, 0.9, 1.0])
def test_escalates_when_sentiment_at_or_above_threshold(sentiment_score: float) -> None:
    assert (
        evaluate_escalation(confidence=0.95, sentiment_score=sentiment_score, grounded=True)
        == "escalate"
    )


def test_respond_when_sentiment_just_below_threshold() -> None:
    assert (
        evaluate_escalation(confidence=0.95, sentiment_score=0.74, grounded=True) == "respond"
    )


def test_escalates_when_multiple_conditions_true() -> None:
    assert (
        evaluate_escalation(confidence=0.10, sentiment_score=0.90, grounded=False) == "escalate"
    )


def test_boundary_values_are_exact_not_approximate() -> None:
    # Exactly-at-threshold values must escalate (<=, >=), not just past it.
    assert evaluate_escalation(confidence=0.70, sentiment_score=0.0, grounded=True) == "escalate"
    assert evaluate_escalation(confidence=1.0, sentiment_score=0.75, grounded=True) == "escalate"
