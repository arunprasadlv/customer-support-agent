# Backend Test Report

**Run date**: 2026-08-21
**Scope**: Phase 1 + Phase 2 + Phase 3 (SAD "MVP Build Sequencing" — all three phases complete)
**Suite**: `pytest` via `backend/.venv` (Python 3.11.16)
**Duration**: 89.6s
**Result**: **75 / 75 passed**, 0 failed, 0 skipped

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
| pytest | 75 passed, 0 failed, 0 skipped |
| ruff | 1 pre-existing nit, 0 new (see Known Issues) |
| mypy | clean — 19 source files, 0 issues |

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

### `test_review_queue_endpoints.py` (11 passed)
- `test_get_review_queue_empty_list_when_no_entries`
- `test_get_review_queue_lists_entries_most_recent_first`
- `test_approve_writes_live_kb_entry_and_marks_status_approved`
- `test_approve_optional_edit_overrides_all_fields`
- `test_approve_unknown_id_returns_404`
- `test_reapprove_already_approved_entry_returns_409`
- `test_approve_missing_intent_with_no_override_returns_422`
- `test_reject_marks_status_rejected_with_no_kb_write`
- `test_reject_unknown_id_returns_404`
- `test_rereject_already_rejected_entry_returns_409`
- `test_get_review_queue_shows_mixed_statuses`

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

### `test_knowledge_base.py` (8 passed)
- `test_init_db_creates_file`
- `test_count_entries_zero_on_fresh_db`
- `test_seed_from_domain_config_populates_table`
- `test_seed_from_domain_config_is_idempotent`
- `test_insert_kb_entry_adds_a_new_row`
- `test_list_kb_entries_filters_by_intent`
- `test_kb_search_finds_a_manually_inserted_live_entry`
- `test_kb_search_still_finds_seeded_entries_when_table_is_fresh`

## Known issues / notes

1. **One pre-existing ruff line-length nit, not a regression.** `src/app/schemas/task_outputs.py:44` exceeds the 100-char limit by 2 characters. Present since the original `*develop-be` run. (The other previously-flagged nit, `domain/loader.py:97`, was resolved as a side effect of Phase 3's edits to that file.)

2. **Exit-time traceback noise after the summary line — not a test failure.** A straggler background thread from an earlier timed-out inquiry occasionally finishes its real Anthropic call after pytest's own process teardown, producing `cannot schedule new futures after shutdown` tracebacks *after* `75 passed` is already reported. This is a documented consequence of Python's inability to forcibly kill a running thread (see `backend.md`) — harmless, but alarming if you don't know to expect it. On rare occasions this same mechanism has caused one cross-test flake in `test_run_inquiry_degrades_to_escalate_on_timeout` (passes in isolation) — not observed in this run (75/75 clean).

3. **Live reasoning-Crew latency still exceeds the SAD §7 ceiling (open).** Real end-to-end runs against the Anthropic API take ~15-16s, above the `sad.md` §7 10-second hard ceiling. Phases 2 and 3 were both built without first running the mandatory latency-spike/fallback-ladder gate (operator decision, 2026-08-21) — escalate-on-timeout remains the common case for live traffic across `/chat` and `/email`, not the exception. Still an open decision.

4. **`POST /escalations/{id}/resolve` doesn't validate prior escalation (open).** It accepts any valid interaction `id`, including ones whose `outcome` was `"responded"`, not `"escalated"` — no check enforces that the target interaction was actually escalated before a resolution can be queued. Deliberately left unenforced; see `backend.md` Open Questions.

5. **Re-approving/re-rejecting an already-actioned review-queue entry returns 409.** A deliberate design choice, not a bug — `approve` has a one-shot live-KB write side effect, so silently succeeding on a repeat call could double-write or mask a stale client state. Confirmed via `test_reapprove_already_approved_entry_returns_409` / `test_rereject_already_rejected_entry_returns_409`.

## Environment

- `pytest` 9.1.1
- `crewai` 1.15.17
- `fastapi` + `pydantic` 2.12.5
- `ruff` / `mypy`
- Runtime: `crewai` (`AAMAD_TARGET_RUNTIME`)
- Interpreter: `backend/.venv`, Python 3.11.16 (not the root `.venv`, which is 3.14.5 and cannot install `crewai`)

## Sources

- `project-context/1.define/sad.md` (acceptance criteria, MVP Build Sequencing — all 3 phases now complete)
- `project-context/2.build/backend.md` (full build history, design decisions, Audit trail)
- Live `pytest`/`ruff`/`mypy` run, 2026-08-21, on branch `backend`
