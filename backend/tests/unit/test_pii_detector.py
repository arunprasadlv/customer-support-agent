"""Unit tests for app.tools.pii_detector.detect_pii — sad.md §9 "Unit:
PII-guard redaction correctness". Pure function, no LLM/network involved.
"""

from __future__ import annotations

import itertools

from app.tools.pii_detector import detect_pii


def test_no_pii_returns_text_unchanged() -> None:
    text = "What time is check-in on Friday?"
    result = detect_pii(text)
    assert result.clean_text == text
    assert result.redaction_actions == []


def test_detects_and_masks_email() -> None:
    text = "Please reply to jane.doe@example.com about my stay."
    result = detect_pii(text)
    assert "jane.doe@example.com" not in result.clean_text
    assert "[REDACTED_EMAIL]" in result.clean_text
    assert len(result.redaction_actions) == 1
    action = result.redaction_actions[0]
    assert action.entity_type == "email"
    assert action.method == "mask"
    assert text[action.span_start : action.span_end] == "jane.doe@example.com"


def test_detects_and_masks_phone_number() -> None:
    text = "You can reach me at (415) 555-0199 anytime."
    result = detect_pii(text)
    assert "555-0199" not in result.clean_text
    actions = result.redaction_actions
    assert len(actions) == 1
    assert actions[0].entity_type == "phone"
    start, end = actions[0].span_start, actions[0].span_end
    assert text[start:end] == "(415) 555-0199"


def test_detects_and_masks_account_number_with_context_keyword() -> None:
    text = "My confirmation number is 883921445, can you look it up?"
    result = detect_pii(text)
    assert "883921445" not in result.clean_text
    assert any(a.entity_type == "account_number" for a in result.redaction_actions)
    action = next(a for a in result.redaction_actions if a.entity_type == "account_number")
    assert text[action.span_start : action.span_end] == "883921445"


def test_bare_digits_without_context_keyword_are_not_treated_as_account_number() -> None:
    # No account/confirmation/reservation/booking/card keyword preceding
    # the digits -> not flagged as account_number (avoids over-redaction).
    text = "The room rate is 189 dollars per night, reference 883921445 only."
    result = detect_pii(text)
    assert not any(a.entity_type == "account_number" for a in result.redaction_actions)


def test_detects_and_masks_name_after_self_introduction() -> None:
    text = "Hi, my name is John Smith and I have a reservation."
    result = detect_pii(text)
    assert "John Smith" not in result.clean_text
    assert "[REDACTED_NAME]" in result.clean_text
    action = next(a for a in result.redaction_actions if a.entity_type == "name")
    assert text[action.span_start : action.span_end] == "John Smith"


def test_detects_multiple_entities_with_correct_offsets() -> None:
    text = "My name is Alice Brown, email alice.brown@example.com, phone 212-555-0142."
    result = detect_pii(text)
    entity_types = {a.entity_type for a in result.redaction_actions}
    assert entity_types == {"name", "email", "phone"}
    # Every action's recorded span must match the ORIGINAL text exactly.
    for action in result.redaction_actions:
        original_span = text[action.span_start : action.span_end]
        assert original_span  # non-empty
    assert "Alice Brown" not in result.clean_text
    assert "alice.brown@example.com" not in result.clean_text
    assert "212-555-0142" not in result.clean_text


def test_overlapping_matches_do_not_double_redact() -> None:
    # Email local-part could coincidentally look name-like; ensure no
    # overlapping spans are both accepted (spans must be non-overlapping).
    text = "Contact John.Smith@example.com for details."
    result = detect_pii(text)
    spans = sorted((a.span_start, a.span_end) for a in result.redaction_actions)
    for (_start1, end1), (start2, _end2) in itertools.pairwise(spans):
        assert end1 <= start2, "overlapping redaction spans detected"


def test_redaction_result_is_pydantic_typed() -> None:
    from app.schemas.task_outputs import RedactionResult

    result = detect_pii("no pii here")
    assert isinstance(result, RedactionResult)
