# Backend Test Report

**Run date**: 2026-08-21
**Scope**: Phase 1 + Phase 2 (SAD "MVP Build Sequencing")
**Suite**: `pytest` via `backend/.venv` (Python 3.11.16)
**Duration**: 88.6s
**Result**: **56 / 56 passed**, 0 failed, 0 skipped

Regenerate with:

```bash
cd backend
./.venv/Scripts/python.exe -m pytest -v --tb=short
./.venv/Scripts/python.exe -m ruff check .
./.venv/Scripts/python.exe -m mypy src
```

## Summary

| Check | Result |
|---|---|
| pytest | 56 passed, 0 failed, 0 skipped |
| ruff | 2 pre-existing nits, 0 new (see Known Issues) |
| mypy | clean — 18 source files, 0 issues |

## Integration tests — `tests/integration/`

### `test_chat_endpoint.py` (5 passed)
- `test_chat_missing_message_returns_422`
- `test_chat_missing_session_id_returns_422`
- `test_chat_end_to_end_returns_reply_and_escalated`
- `test_interactions_empty_list_when_no_interactions`
- `test_interactions_shows_record_after_chat_call`

### `test_email_endpoint.py` (5 passed)
- `test_email_missing_from_returns_422`
- `test_email_missing_subject_returns_422`
- `test_email_missing_body_returns_422`
- `test_email_end_to_end_returns_reply_body_and_escalated`
- `test_email_logs_interaction_with_channel_email`

### `test_health.py` (1 passed)
- `test_health_ok`

### `test_inquiry_flow.py` (6 passed)
- `test_pii_redact_is_fail_closed_on_pii_guard_failure`
- `test_run_inquiry_degrades_to_escalate_on_timeout`
- `test_inquiry_flow_end_to_end_per_scenario_category[reservations_booking]`
- `test_inquiry_flow_end_to_end_per_scenario_category[checkin_checkout_billing]`
- `test_inquiry_flow_end_to_end_per_scenario_category[room_service_amenities]`
- `test_inquiry_flow_end_to_end_per_scenario_category[general_complaints]`

### `test_escalation_resolution_flow.py` (4 passed)
- `test_run_escalation_resolution_writes_candidate_to_review_queue`
- `test_run_escalation_resolution_does_not_touch_live_kb`
- `test_run_escalation_resolution_raises_on_unknown_inquiry_id`
- `test_flow_steps_directly`

### `test_escalation_resolve_endpoint.py` (3 passed)
- `test_resolve_escalation_returns_queued_status_and_review_queue_id`
- `test_resolve_escalation_missing_resolution_text_returns_422`
- `test_resolve_escalation_unknown_id_returns_404_error_envelope`

## Unit tests — `tests/unit/`

### `test_escalation_gate.py` (12 passed)
- `test_respond_when_all_conditions_are_safe`
- `test_escalates_when_not_grounded_even_with_high_confidence_and_calm_sentiment`
- `test_escalates_when_confidence_at_or_below_threshold[0.7]`
- `test_escalates_when_confidence_at_or_below_threshold[0.5]`
- `test_escalates_when_confidence_at_or_below_threshold[0.0]`
- `test_respond_when_confidence_just_above_threshold`
- `test_escalates_when_sentiment_at_or_above_threshold[0.75]`
- `test_escalates_when_sentiment_at_or_above_threshold[0.9]`
- `test_escalates_when_sentiment_at_or_above_threshold[1.0]`
- `test_respond_when_sentiment_just_below_threshold`
- `test_escalates_when_multiple_conditions_true`
- `test_boundary_values_are_exact_not_approximate`

### `test_interaction_log.py` (6 passed)
- `test_init_db_creates_file`
- `test_record_and_list_interaction`
- `test_record_diagnostic_halt_without_optional_fields`
- `test_get_interaction_by_id_found`
- `test_get_interaction_by_id_not_found`
- `test_multiple_records_ordered_most_recent_first`

### `test_pii_detector.py` (9 passed)
- `test_no_pii_returns_text_unchanged`
- `test_detects_and_masks_email`
- `test_detects_and_masks_phone_number`
- `test_detects_and_masks_account_number_with_context_keyword`
- `test_bare_digits_without_context_keyword_are_not_treated_as_account_number`
- `test_detects_and_masks_name_after_self_introduction`
- `test_detects_multiple_entities_with_correct_offsets`
- `test_overlapping_matches_do_not_double_redact`
- `test_redaction_result_is_pydantic_typed`

### `test_review_queue.py` (5 passed)
- `test_init_db_creates_file`
- `test_record_and_list_review_queue_entry`
- `test_record_without_optional_fields`
- `test_duplicate_id_is_ignored_not_duplicated`
- `test_multiple_records_ordered_most_recent_first`

## Known issues / notes

1. **Two pre-existing ruff line-length nits, not regressions.** `src/app/domain/loader.py:97` and `src/app/schemas/task_outputs.py:44` exceed the 100-char limit by 1-2 characters. Present since the original `*develop-be` run; untouched by any follow-up fix.

2. **Exit-time traceback noise after the summary line — not a test failure.** A straggler background thread from an earlier timed-out inquiry occasionally finishes its real Anthropic call after pytest's own process teardown, producing `cannot schedule new futures after shutdown` tracebacks *after* `56 passed` is already reported. This is a documented consequence of Python's inability to forcibly kill a running thread (see `backend.md`) — harmless, but alarming if you don't know to expect it.

3. **Live reasoning-Crew latency still exceeds the SAD §7 ceiling (open).** Real end-to-end runs against the Anthropic API take ~15-16s, above the `sad.md` §7 10-second hard ceiling. Phase 2 was deliberately built without first running the mandatory latency-spike/fallback-ladder gate (operator decision, 2026-08-21) — escalate-on-timeout remains the common case for live traffic on both `/chat` and `/email`, not the exception. Still an open decision.

4. **`POST /escalations/{id}/resolve` doesn't validate prior escalation (open).** It accepts any valid interaction `id`, including ones whose `outcome` was `"responded"`, not `"escalated"` — no check enforces that the target interaction was actually escalated before a resolution can be queued. Deliberately left unenforced this round; see `backend.md` Open Questions.

## Environment

- `pytest` 9.1.1
- `crewai` 1.15.17
- `fastapi` + `pydantic` 2.12.5
- `ruff` / `mypy`
- Runtime: `crewai` (`AAMAD_TARGET_RUNTIME`)
- Interpreter: `backend/.venv`, Python 3.11.16 (not the root `.venv`, which is 3.14.5 and cannot install `crewai`)

## Sources

- `project-context/1.define/sad.md` (acceptance criteria, MVP Build Sequencing)
- `project-context/2.build/backend.md` (full build history, design decisions, Audit trail)
- Live `pytest`/`ruff`/`mypy` run, 2026-08-21, on branch `backend`
