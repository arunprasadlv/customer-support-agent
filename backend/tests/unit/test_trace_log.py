"""Unit tests for app.persistence.trace_log (adapter-crewai.md Logging:
"Record lifecycle events ... in Trace Log ... redact secrets and persist
logs under project-context/2.build/logs"). Same pattern as
test_interaction_log.py: exercise the persistence function directly with
an explicit `log_dir`/`tmp_path` for isolation.

The `TraceLogListener._on_*` wiring tests below call the handler methods
DIRECTLY (`listener._on_task_completed(None, event)`) instead of going
through `crewai_event_bus.emit()`. This is deliberate, not a shortcut:
`crewai_event_bus` is process-global with no unsubscribe mechanism, so a
`TraceLogListener` constructed anywhere in a pytest session (including one
built just for this test file) stays registered on it for the rest of the
process. If these tests emitted through the real bus, a genuine `install_
trace_listener()` instance created earlier by a *live* integration test
elsewhere in the suite (e.g. test_inquiry_flow.py's real
`InquiryFlow.kickoff()`) would still be attached and would receive this
test's synthetic events too -- writing fabricated trace lines into the
real project-context/2.build/logs directory. Calling the handler methods
directly tests the exact same event -> record_trace_event mapping without
ever touching the shared bus.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from crewai.events.types.llm_events import (
    LLMCallCompletedEvent,
    LLMCallFailedEvent,
    LLMCallStartedEvent,
    LLMCallType,
)
from crewai.events.types.task_events import TaskCompletedEvent, TaskFailedEvent, TaskStartedEvent
from crewai.events.types.tool_usage_events import (
    ToolUsageErrorEvent,
    ToolUsageFinishedEvent,
    ToolUsageStartedEvent,
)
from crewai.tasks.task_output import TaskOutput

from app.persistence import trace_log
from app.persistence.trace_log import (
    TraceLogListener,
    bind_interaction_id,
    get_current_interaction_id,
    get_trace_events_for_interaction,
    install_trace_listener,
    record_trace_event,
    reset_interaction_id,
)


def _read_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _log_file(log_dir: Path, ts: datetime) -> Path:
    return log_dir / f"trace-{ts.strftime('%Y-%m-%d')}.jsonl"


def _bare_listener(log_dir: Path) -> TraceLogListener:
    """Build a TraceLogListener WITHOUT running `BaseEventListener.__init__`
    (which registers handlers on the process-global `crewai_event_bus` --
    see module docstring for why tests avoid that). Only `_log_dir` and the
    `_on_*` methods are needed to exercise the mapping logic directly."""
    listener = object.__new__(TraceLogListener)
    listener._log_dir = log_dir  # type: ignore[attr-defined]
    return listener


def test_record_trace_event_writes_jsonl_line(tmp_path: Path) -> None:
    ts = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
    record_trace_event(
        "task_completed",
        task_name="classify_task",
        agent_role="query_classifier",
        outcome="success",
        detail="intent=checkin_checkout_billing",
        timestamp=ts,
        log_dir=tmp_path,
    )

    rows = _read_lines(_log_file(tmp_path, ts))
    assert len(rows) == 1
    row = rows[0]
    assert row["event"] == "task_completed"
    assert row["task_name"] == "classify_task"
    assert row["agent_role"] == "query_classifier"
    assert row["outcome"] == "success"
    assert row["detail"] == "intent=checkin_checkout_billing"
    assert row["error"] is None
    assert row["timestamp"] == ts.isoformat()


def test_record_trace_event_appends_multiple_lines_same_day(tmp_path: Path) -> None:
    ts = datetime(2026, 8, 30, 9, 0, 0, tzinfo=UTC)
    record_trace_event("task_started", task_name="t1", timestamp=ts, log_dir=tmp_path)
    record_trace_event(
        "task_completed", task_name="t1", outcome="success", timestamp=ts, log_dir=tmp_path
    )

    rows = _read_lines(_log_file(tmp_path, ts))
    assert [r["event"] for r in rows] == ["task_started", "task_completed"]


def test_record_trace_event_redacts_pii_in_detail(tmp_path: Path) -> None:
    ts = datetime(2026, 8, 30, 10, 0, 0, tzinfo=UTC)
    record_trace_event(
        "tool_call_finished",
        task_name="redact_pii_task",
        agent_role="pii_guard",
        outcome="success",
        detail="tool=pii_detector args={'text': 'call me at 415-555-0100 or jane@example.com'}",
        timestamp=ts,
        log_dir=tmp_path,
    )

    row = _read_lines(_log_file(tmp_path, ts))[0]
    assert "415-555-0100" not in row["detail"]
    assert "jane@example.com" not in row["detail"]
    assert "[REDACTED_PHONE]" in row["detail"]
    assert "[REDACTED_EMAIL]" in row["detail"]


def test_record_trace_event_redacts_api_key_shaped_secrets(tmp_path: Path) -> None:
    ts = datetime(2026, 8, 30, 11, 0, 0, tzinfo=UTC)
    record_trace_event(
        "llm_call_failed",
        outcome="failure",
        error="anthropic.AuthenticationError: invalid api key sk-ant-api03-fakekeyfakekeyfakekey",
        timestamp=ts,
        log_dir=tmp_path,
    )

    row = _read_lines(_log_file(tmp_path, ts))[0]
    assert "sk-ant-api03-fakekeyfakekeyfakekey" not in row["error"]
    assert "[REDACTED_SECRET]" in row["error"]


def test_record_trace_event_truncates_long_detail(tmp_path: Path) -> None:
    ts = datetime(2026, 8, 30, 13, 0, 0, tzinfo=UTC)
    long_detail = "x" * 2000
    record_trace_event("llm_call_completed", detail=long_detail, timestamp=ts, log_dir=tmp_path)

    row = _read_lines(_log_file(tmp_path, ts))[0]
    assert len(row["detail"]) < len(long_detail)
    assert row["detail"].endswith("...[truncated]")


def test_record_trace_event_none_fields_stay_none(tmp_path: Path) -> None:
    ts = datetime(2026, 8, 30, 14, 0, 0, tzinfo=UTC)
    record_trace_event("task_started", task_name="t1", timestamp=ts, log_dir=tmp_path)

    row = _read_lines(_log_file(tmp_path, ts))[0]
    assert row["outcome"] is None
    assert row["detail"] is None
    assert row["error"] is None


# --- Per-step latency check: record_trace_event(duration_ms=, include_latency=) ---
# sad.md §7's NFR-002 thresholds reused verbatim: 5_000ms target, 10_000ms
# hard ceiling. Both boundaries are inclusive (`<=`), per spec.


def test_record_trace_event_latency_fields_absent_when_not_included(tmp_path: Path) -> None:
    """task_started/task_completed/etc. never pass include_latency=True --
    the three latency keys must be entirely absent from the record, not
    merely null."""
    ts = datetime(2026, 9, 1, 15, 0, 0, tzinfo=UTC)
    record_trace_event("task_started", task_name="t1", timestamp=ts, log_dir=tmp_path)

    row = _read_lines(_log_file(tmp_path, ts))[0]
    assert "duration_ms" not in row
    assert "latency_pass" not in row
    assert "meets_target" not in row


def test_record_trace_event_latency_null_when_duration_is_none(tmp_path: Path) -> None:
    ts = datetime(2026, 9, 1, 15, 1, 0, tzinfo=UTC)
    record_trace_event(
        "llm_call_completed",
        timestamp=ts,
        log_dir=tmp_path,
        duration_ms=None,
        include_latency=True,
    )

    row = _read_lines(_log_file(tmp_path, ts))[0]
    assert row["duration_ms"] is None
    assert row["latency_pass"] is None
    assert row["meets_target"] is None


def test_record_trace_event_latency_well_within_target(tmp_path: Path) -> None:
    ts = datetime(2026, 9, 1, 15, 2, 0, tzinfo=UTC)
    record_trace_event(
        "llm_call_completed",
        timestamp=ts,
        log_dir=tmp_path,
        duration_ms=1200,
        include_latency=True,
    )

    row = _read_lines(_log_file(tmp_path, ts))[0]
    assert row["duration_ms"] == 1200
    assert row["latency_pass"] is True
    assert row["meets_target"] is True


def test_record_trace_event_latency_boundary_exactly_5000ms_meets_target(tmp_path: Path) -> None:
    ts = datetime(2026, 9, 1, 15, 3, 0, tzinfo=UTC)
    record_trace_event(
        "tool_call_finished",
        timestamp=ts,
        log_dir=tmp_path,
        duration_ms=5000,
        include_latency=True,
    )

    row = _read_lines(_log_file(tmp_path, ts))[0]
    assert row["meets_target"] is True
    assert row["latency_pass"] is True


def test_record_trace_event_latency_boundary_5001ms_fails_target_passes_ceiling(
    tmp_path: Path,
) -> None:
    ts = datetime(2026, 9, 1, 15, 4, 0, tzinfo=UTC)
    record_trace_event(
        "tool_call_finished",
        timestamp=ts,
        log_dir=tmp_path,
        duration_ms=5001,
        include_latency=True,
    )

    row = _read_lines(_log_file(tmp_path, ts))[0]
    assert row["meets_target"] is False
    assert row["latency_pass"] is True


def test_record_trace_event_latency_boundary_exactly_10000ms_passes_ceiling(
    tmp_path: Path,
) -> None:
    ts = datetime(2026, 9, 1, 15, 5, 0, tzinfo=UTC)
    record_trace_event(
        "llm_call_failed",
        timestamp=ts,
        log_dir=tmp_path,
        duration_ms=10000,
        include_latency=True,
    )

    row = _read_lines(_log_file(tmp_path, ts))[0]
    assert row["latency_pass"] is True
    assert row["meets_target"] is False


def test_record_trace_event_latency_boundary_10001ms_fails_both(tmp_path: Path) -> None:
    ts = datetime(2026, 9, 1, 15, 6, 0, tzinfo=UTC)
    record_trace_event(
        "tool_call_error",
        timestamp=ts,
        log_dir=tmp_path,
        duration_ms=10001,
        include_latency=True,
    )

    row = _read_lines(_log_file(tmp_path, ts))[0]
    assert row["latency_pass"] is False
    assert row["meets_target"] is False


def test_install_trace_listener_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    # Uses real tmp_path dirs (not a fake relative string) because this is
    # the one test that must call the real `install_trace_listener()` --
    # and thus the real `TraceLogListener.__init__` -- which registers on
    # the process-global `crewai_event_bus` for the rest of the pytest
    # session (no unsubscribe exists). Pointing that stray registration at
    # a real, harmless tmp_path avoids ever creating stray directories
    # relative to the repo/cwd if a later live event happens to fire.
    monkeypatch.setattr(trace_log, "_listener", None)
    try:
        first_dir = tmp_path / "first"
        first = install_trace_listener(log_dir=first_dir)
        second = install_trace_listener(log_dir=tmp_path / "second")  # ignored: already installed
        assert first is second
        assert first._log_dir == first_dir
    finally:
        monkeypatch.setattr(trace_log, "_listener", None)


def test_listener_on_task_started_writes_record(tmp_path: Path) -> None:
    listener = _bare_listener(tmp_path)
    event = TaskStartedEvent(context=None, task_name="classify_task", agent_role="query_classifier")

    listener._on_task_started(None, event)

    row = _read_lines(_log_file(tmp_path, event.timestamp))[0]
    assert row["event"] == "task_started"
    assert row["outcome"] is None
    assert row["task_name"] == "classify_task"


def test_listener_on_task_completed_writes_success_record(tmp_path: Path) -> None:
    listener = _bare_listener(tmp_path)
    output = TaskOutput(
        description="classify the query", agent="query_classifier", raw="intent=billing"
    )
    event = TaskCompletedEvent(
        output=output, task_name="classify_task", agent_role="query_classifier"
    )

    listener._on_task_completed(None, event)

    row = _read_lines(_log_file(tmp_path, event.timestamp))[0]
    assert row["event"] == "task_completed"
    assert row["outcome"] == "success"
    assert row["task_name"] == "classify_task"
    assert row["agent_role"] == "query_classifier"
    assert row["detail"] == "intent=billing"


def test_listener_on_task_failed_writes_failure_record(tmp_path: Path) -> None:
    listener = _bare_listener(tmp_path)
    event = TaskFailedEvent(
        error="RuntimeError: boom",
        task_name="retrieve_knowledge_task",
        agent_role="knowledge_retriever",
    )

    listener._on_task_failed(None, event)

    row = _read_lines(_log_file(tmp_path, event.timestamp))[0]
    assert row["event"] == "task_failed"
    assert row["outcome"] == "failure"
    assert row["error"] == "RuntimeError: boom"


def test_listener_on_tool_usage_error_writes_failure_record(tmp_path: Path) -> None:
    listener = _bare_listener(tmp_path)
    event = ToolUsageErrorEvent(
        tool_name="kb_search",
        tool_args={"intent": "checkin_checkout_billing", "query_text": "when is checkout"},
        error="ValueError: something went wrong",
        task_name="retrieve_knowledge_task",
        agent_role="knowledge_retriever",
    )

    listener._on_tool_usage_error(None, event)

    row = _read_lines(_log_file(tmp_path, event.timestamp))[0]
    assert row["event"] == "tool_call_error"
    assert row["outcome"] == "failure"
    assert "kb_search" in row["error"]
    assert "ValueError" in row["error"]


def test_listener_on_tool_usage_finished_success_redacts_raw_pii_input(tmp_path: Path) -> None:
    listener = _bare_listener(tmp_path)
    now = datetime.now(UTC)
    event = ToolUsageFinishedEvent(
        tool_name="pii_detector",
        tool_args={"text": "email me at jane@example.com"},
        started_at=now,
        finished_at=now,
        output="clean_text='email me at [REDACTED_EMAIL]'",
        task_name="redact_pii_task",
        agent_role="pii_guard",
    )

    listener._on_tool_usage_finished(None, event)

    row = _read_lines(_log_file(tmp_path, event.timestamp))[0]
    assert row["event"] == "tool_call_finished"
    assert row["outcome"] == "success"
    # pii_detector's own raw tool_args legitimately carries real PII (that's
    # its job) -- the trace record must never contain it in the clear.
    assert "jane@example.com" not in json.dumps(row)
    assert "[REDACTED_EMAIL]" in row["detail"]


def test_listener_on_tool_usage_finished_reported_failure_writes_failure_record(
    tmp_path: Path,
) -> None:
    from crewai.tools.tool_failure import ToolFailure

    listener = _bare_listener(tmp_path)
    now = datetime.now(UTC)
    event = ToolUsageFinishedEvent(
        tool_name="kb_search",
        tool_args={"intent": "billing", "query_text": "x"},
        started_at=now,
        finished_at=now,
        output="no match",
        failure=ToolFailure(message="no matching KB entry"),
        task_name="retrieve_knowledge_task",
        agent_role="knowledge_retriever",
    )

    listener._on_tool_usage_finished(None, event)

    row = _read_lines(_log_file(tmp_path, event.timestamp))[0]
    assert row["outcome"] == "failure"
    assert row["detail"] is None
    assert "kb_search" in row["error"]


def test_listener_on_llm_call_completed_writes_success_record(tmp_path: Path) -> None:
    listener = _bare_listener(tmp_path)
    event = LLMCallCompletedEvent(
        call_id="call-1",
        response="Final Answer: intent=billing",
        call_type=LLMCallType.LLM_CALL,
        task_name="classify_task",
        agent_role="query_classifier",
    )

    listener._on_llm_call_completed(None, event)

    row = _read_lines(_log_file(tmp_path, event.timestamp))[0]
    assert row["event"] == "llm_call_completed"
    assert row["outcome"] == "success"
    assert row["detail"] == "Final Answer: intent=billing"


def test_listener_on_llm_call_failed_writes_failure_record(tmp_path: Path) -> None:
    listener = _bare_listener(tmp_path)
    event = LLMCallFailedEvent(
        call_id="call-2",
        error="anthropic.APIError: rate limited",
        task_name="analyze_sentiment_task",
        agent_role="sentiment_analyzer",
    )

    listener._on_llm_call_failed(None, event)

    row = _read_lines(_log_file(tmp_path, event.timestamp))[0]
    assert row["event"] == "llm_call_failed"
    assert row["outcome"] == "failure"
    assert "rate limited" in row["error"]


# --- Per-step latency pairing: *_started -> matching completion event ---


def test_listener_on_llm_call_started_writes_bare_marker_no_prompt_leak(tmp_path: Path) -> None:
    listener = _bare_listener(tmp_path)
    event = LLMCallStartedEvent(
        model="claude-haiku-4-5",
        messages=[{"role": "user", "content": "super secret prompt text"}],
        call_id="call-start-1",
        task_name="classify_task",
        agent_role="query_classifier",
    )

    listener._on_llm_call_started(None, event)

    row = _read_lines(_log_file(tmp_path, event.timestamp))[0]
    assert row["event"] == "llm_call_started"
    assert row["detail"] is None
    assert row["error"] is None
    assert row["outcome"] is None
    # The full prompt must never reach disk via this handler.
    assert "super secret prompt text" not in json.dumps(row)
    # *_started records carry no latency fields at all (not applicable yet).
    assert "duration_ms" not in row


def test_listener_on_tool_usage_started_writes_bare_marker_no_args_leak(tmp_path: Path) -> None:
    listener = _bare_listener(tmp_path)
    event = ToolUsageStartedEvent(
        tool_name="pii_detector",
        tool_args={"text": "email me at jane@example.com"},
        task_name="redact_pii_task",
        agent_role="pii_guard",
    )

    listener._on_tool_usage_started(None, event)

    row = _read_lines(_log_file(tmp_path, event.timestamp))[0]
    assert row["event"] == "tool_call_started"
    assert row["detail"] is None
    assert row["error"] is None
    assert "jane@example.com" not in json.dumps(row)
    assert "duration_ms" not in row


def test_listener_pairs_llm_started_and_completed_computes_duration_ms(tmp_path: Path) -> None:
    listener = _bare_listener(tmp_path)
    started = LLMCallStartedEvent(
        model="m",
        messages=[],
        call_id="call-2",
        task_name="classify_task",
        agent_role="query_classifier",
        timestamp=datetime(2026, 9, 1, 16, 0, 0, tzinfo=UTC),
    )
    completed = LLMCallCompletedEvent(
        call_id="call-2",
        response="ok",
        call_type=LLMCallType.LLM_CALL,
        task_name="classify_task",
        agent_role="query_classifier",
        timestamp=datetime(2026, 9, 1, 16, 0, 2, 500000, tzinfo=UTC),  # +2.5s
    )

    listener._on_llm_call_started(None, started)
    listener._on_llm_call_completed(None, completed)

    rows = _read_lines(_log_file(tmp_path, started.timestamp))
    completed_row = next(r for r in rows if r["event"] == "llm_call_completed")
    assert completed_row["duration_ms"] == 2500
    assert completed_row["latency_pass"] is True
    assert completed_row["meets_target"] is True


def test_listener_pairs_llm_started_and_failed_computes_duration_ms(tmp_path: Path) -> None:
    listener = _bare_listener(tmp_path)
    started = LLMCallStartedEvent(
        model="m",
        messages=[],
        call_id="call-3",
        task_name="analyze_sentiment_task",
        agent_role="sentiment_analyzer",
        timestamp=datetime(2026, 9, 1, 16, 5, 0, tzinfo=UTC),
    )
    failed = LLMCallFailedEvent(
        call_id="call-3",
        error="anthropic.APIError: rate limited",
        task_name="analyze_sentiment_task",
        agent_role="sentiment_analyzer",
        timestamp=datetime(2026, 9, 1, 16, 5, 11, tzinfo=UTC),  # +11s
    )

    listener._on_llm_call_started(None, started)
    listener._on_llm_call_failed(None, failed)

    rows = _read_lines(_log_file(tmp_path, started.timestamp))
    failed_row = next(r for r in rows if r["event"] == "llm_call_failed")
    assert failed_row["duration_ms"] == 11000
    assert failed_row["latency_pass"] is False
    assert failed_row["meets_target"] is False


def test_listener_pairs_tool_started_and_finished_computes_duration_ms(tmp_path: Path) -> None:
    listener = _bare_listener(tmp_path)
    start_ts = datetime(2026, 9, 1, 16, 8, 0, tzinfo=UTC)
    finished_ts = datetime(2026, 9, 1, 16, 8, 0, 750000, tzinfo=UTC)  # +750ms
    started = ToolUsageStartedEvent(
        tool_name="kb_search",
        tool_args={"intent": "billing"},
        task_name="retrieve_knowledge_task",
        agent_role="knowledge_retriever",
        timestamp=start_ts,
    )
    finished = ToolUsageFinishedEvent(
        tool_name="kb_search",
        tool_args={"intent": "billing"},
        started_at=start_ts,
        finished_at=finished_ts,
        output="matched",
        task_name="retrieve_knowledge_task",
        agent_role="knowledge_retriever",
        timestamp=finished_ts,
    )

    listener._on_tool_usage_started(None, started)
    listener._on_tool_usage_finished(None, finished)

    rows = _read_lines(_log_file(tmp_path, start_ts))
    finished_row = next(r for r in rows if r["event"] == "tool_call_finished")
    assert finished_row["duration_ms"] == 750
    assert finished_row["latency_pass"] is True
    assert finished_row["meets_target"] is True


def test_listener_pairs_tool_started_and_error_computes_duration_ms(tmp_path: Path) -> None:
    listener = _bare_listener(tmp_path)
    start_ts = datetime(2026, 9, 1, 16, 10, 0, tzinfo=UTC)
    error_ts = datetime(2026, 9, 1, 16, 10, 6, tzinfo=UTC)  # +6s
    started = ToolUsageStartedEvent(
        tool_name="kb_search",
        tool_args={"intent": "billing"},
        task_name="retrieve_knowledge_task",
        agent_role="knowledge_retriever",
        timestamp=start_ts,
    )
    error = ToolUsageErrorEvent(
        tool_name="kb_search",
        tool_args={"intent": "billing"},
        error="ValueError: boom",
        task_name="retrieve_knowledge_task",
        agent_role="knowledge_retriever",
        timestamp=error_ts,
    )

    listener._on_tool_usage_started(None, started)
    listener._on_tool_usage_error(None, error)

    rows = _read_lines(_log_file(tmp_path, start_ts))
    error_row = next(r for r in rows if r["event"] == "tool_call_error")
    assert error_row["duration_ms"] == 6000
    assert error_row["latency_pass"] is True
    assert error_row["meets_target"] is False


def test_listener_completion_with_no_prior_start_yields_null_duration(tmp_path: Path) -> None:
    """Unmatched completion edge case (module docstring "Pairing
    mechanism") -- no `_on_llm_call_started` was ever seen for this slot,
    so `duration_ms` must be null, never raise."""
    listener = _bare_listener(tmp_path)
    completed = LLMCallCompletedEvent(
        call_id="call-orphan",
        response="ok",
        call_type=LLMCallType.LLM_CALL,
        task_name="classify_task",
        agent_role="query_classifier",
        timestamp=datetime(2026, 9, 1, 16, 15, 0, tzinfo=UTC),
    )

    listener._on_llm_call_completed(None, completed)

    row = _read_lines(_log_file(tmp_path, completed.timestamp))[0]
    assert row["duration_ms"] is None
    assert row["latency_pass"] is None
    assert row["meets_target"] is None


def test_listener_task_events_have_no_latency_fields(tmp_path: Path) -> None:
    """This check is scoped to individual LLM/tool calls only -- task_*
    records must not gain the three latency keys at all."""
    listener = _bare_listener(tmp_path)
    ts = datetime(2026, 9, 1, 16, 20, 0, tzinfo=UTC)

    listener._on_task_started(
        None, TaskStartedEvent(context=None, task_name="t1", agent_role="r", timestamp=ts)
    )
    listener._on_task_completed(
        None,
        TaskCompletedEvent(
            output=TaskOutput(description="d", agent="r", raw="out"),
            task_name="t1",
            agent_role="r",
            timestamp=ts,
        ),
    )
    listener._on_task_failed(
        None, TaskFailedEvent(error="boom", task_name="t1", agent_role="r", timestamp=ts)
    )

    for row in _read_lines(_log_file(tmp_path, ts)):
        assert "duration_ms" not in row
        assert "latency_pass" not in row
        assert "meets_target" not in row


def test_concurrent_inquiries_get_correctly_separated_step_durations(tmp_path: Path) -> None:
    """Proves the pending-start pairing state (keyed by (interaction_id,
    category), guarded by `_PENDING_LOCK`) does not bleed one concurrent
    inquiry's LLM-call duration into another's -- mirrors
    `test_concurrent_inquiries_each_see_only_their_own_interaction_id`
    above, but for per-step latency instead of plain interaction_id
    correlation."""
    listener = _bare_listener(tmp_path)

    def _run_one(
        interaction_id: str, task_name: str, start_ts: datetime, completed_ts: datetime
    ) -> None:
        token = bind_interaction_id(interaction_id)
        try:
            started = LLMCallStartedEvent(
                model="m",
                messages=[],
                call_id=f"{interaction_id}-call",
                task_name=task_name,
                agent_role="r",
                timestamp=start_ts,
            )
            listener._on_llm_call_started(None, started)
            # Give the other thread a real chance to interleave its own
            # start/pop against the shared `_pending_step_starts` dict.
            time.sleep(0.05)
            completed = LLMCallCompletedEvent(
                call_id=f"{interaction_id}-call",
                response="ok",
                call_type=LLMCallType.LLM_CALL,
                task_name=task_name,
                agent_role="r",
                timestamp=completed_ts,
            )
            listener._on_llm_call_completed(None, completed)
        finally:
            reset_interaction_id(token)

    common_ts = datetime(2026, 9, 1, 17, 0, 0, tzinfo=UTC)
    fast_start, fast_end = common_ts, common_ts.replace(second=3)  # 3_000ms -> meets target
    slow_start, slow_end = common_ts, common_ts.replace(second=7)  # 7_000ms -> misses target

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_run_one, "inquiry-fast", "task-fast", fast_start, fast_end)
        f2 = pool.submit(_run_one, "inquiry-slow", "task-slow", slow_start, slow_end)
        f1.result(timeout=5)
        f2.result(timeout=5)

    rows = _read_lines(_log_file(tmp_path, common_ts))
    completed_by_task = {
        r["task_name"]: r for r in rows if r["event"] == "llm_call_completed"
    }
    assert completed_by_task["task-fast"]["duration_ms"] == 3000
    assert completed_by_task["task-fast"]["meets_target"] is True
    assert completed_by_task["task-slow"]["duration_ms"] == 7000
    assert completed_by_task["task-slow"]["meets_target"] is False
    assert completed_by_task["task-slow"]["latency_pass"] is True


# --- Interaction correlation (`bind_interaction_id`/`_current_interaction_id`) ---


def test_record_trace_event_interaction_id_null_when_unbound(tmp_path: Path) -> None:
    """No `bind_interaction_id` call has happened on this thread (or a
    prior test reset it) -- direct/stray usage must get `interaction_id:
    null`, never raise."""
    assert get_current_interaction_id() is None
    ts = datetime(2026, 9, 1, 8, 0, 0, tzinfo=UTC)
    record_trace_event("task_started", task_name="t1", timestamp=ts, log_dir=tmp_path)

    row = _read_lines(_log_file(tmp_path, ts))[0]
    assert row["interaction_id"] is None


def test_bind_interaction_id_correlates_subsequent_events_on_same_thread(tmp_path: Path) -> None:
    ts = datetime(2026, 9, 1, 8, 5, 0, tzinfo=UTC)
    token = bind_interaction_id("inquiry-abc")
    try:
        assert get_current_interaction_id() == "inquiry-abc"
        record_trace_event("task_started", task_name="t1", timestamp=ts, log_dir=tmp_path)
        record_trace_event(
            "task_completed", task_name="t1", outcome="success", timestamp=ts, log_dir=tmp_path
        )
    finally:
        reset_interaction_id(token)

    assert get_current_interaction_id() is None
    rows = _read_lines(_log_file(tmp_path, ts))
    assert [r["interaction_id"] for r in rows] == ["inquiry-abc", "inquiry-abc"]


def test_bind_interaction_id_correlates_listener_handlers_too(tmp_path: Path) -> None:
    """The `TraceLogListener._on_*` handlers don't accept/forward an
    interaction id explicitly -- they must pick it up the same ambient way
    `record_trace_event`'s direct callers do."""
    listener = _bare_listener(tmp_path)
    event = TaskStartedEvent(context=None, task_name="classify_task", agent_role="query_classifier")

    token = bind_interaction_id("inquiry-xyz")
    try:
        listener._on_task_started(None, event)
    finally:
        reset_interaction_id(token)

    row = _read_lines(_log_file(tmp_path, event.timestamp))[0]
    assert row["interaction_id"] == "inquiry-xyz"


def test_threadpoolexecutor_submit_does_not_propagate_contextvars() -> None:
    """Proves the documented reason `run_inquiry` cannot just call
    `bind_interaction_id(...)` on the calling thread before `pool.submit(
    InquiryFlow().kickoff, ...)`: a plain `ThreadPoolExecutor.submit()` runs
    the callable in a worker thread with its OWN default `contextvars.
    Context`, not a copy of the submitting thread's -- unlike `asyncio`,
    which does copy context into Tasks. If this test ever starts failing
    because a Python version changed this behavior, the `bind_interaction_id`
    call in `inquiry_flow._run_flow_with_trace_correlation` would no longer
    need to run inside the submitted callable -- but as of this repo's
    pinned Python (see pyproject.toml), it still does.
    """
    token = bind_interaction_id("should-not-be-seen-by-worker")
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(get_current_interaction_id)
            seen_in_worker = future.result(timeout=5)
    finally:
        reset_interaction_id(token)

    assert seen_in_worker is None


def test_wrapper_that_binds_inside_submitted_callable_does_propagate() -> None:
    """The actual mechanism `inquiry_flow._run_flow_with_trace_correlation`
    uses: bind the ContextVar as the first statement *of the submitted
    callable itself*, so it runs on the worker thread. This is the
    complement to the previous test -- confirms the chosen fix (a wrapper
    function, not a pre-submit bind) actually works under a real
    `ThreadPoolExecutor`, not just in-thread."""

    def _worker() -> str | None:
        bind_interaction_id("inquiry-in-worker")
        return get_current_interaction_id()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_worker)
        seen_in_worker = future.result(timeout=5)

    assert seen_in_worker == "inquiry-in-worker"
    # And the calling (test) thread's own context is unaffected.
    assert get_current_interaction_id() is None


def test_concurrent_inquiries_each_see_only_their_own_interaction_id(tmp_path: Path) -> None:
    """Two 'inquiries' bound and traced concurrently on two different
    worker threads (mirroring two overlapping `run_inquiry()` calls, each
    with its own fresh `ThreadPoolExecutor`) must not cross-contaminate --
    this is the entire point of a thread-scoped ContextVar over, say, a
    module-level global."""

    def _run_one(interaction_id: str, task_name: str) -> None:
        bind_interaction_id(interaction_id)
        ts = datetime(2026, 9, 1, 9, 0, 0, tzinfo=UTC)
        record_trace_event("task_started", task_name=task_name, timestamp=ts, log_dir=tmp_path)
        record_trace_event(
            "task_completed",
            task_name=task_name,
            outcome="success",
            timestamp=ts,
            log_dir=tmp_path,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_run_one, "inquiry-1", "task-for-1")
        f2 = pool.submit(_run_one, "inquiry-2", "task-for-2")
        f1.result(timeout=5)
        f2.result(timeout=5)

    ts = datetime(2026, 9, 1, 9, 0, 0, tzinfo=UTC)
    rows = _read_lines(_log_file(tmp_path, ts))
    by_task = {r["task_name"]: r["interaction_id"] for r in rows}
    assert by_task["task-for-1"] == "inquiry-1"
    assert by_task["task-for-2"] == "inquiry-2"


# --- get_trace_events_for_interaction ---


def test_get_trace_events_for_interaction_filters_and_orders_chronologically(
    tmp_path: Path,
) -> None:
    day1 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=UTC)
    day2 = datetime(2026, 9, 2, 9, 0, 0, tzinfo=UTC)

    token = bind_interaction_id("target-inquiry")
    try:
        # Written out of chronological order and split across two days'
        # files, to prove both the cross-file scan and the timestamp sort.
        record_trace_event(
            "task_completed", task_name="second", timestamp=day2, log_dir=tmp_path
        )
        record_trace_event(
            "task_started", task_name="first", timestamp=day1, log_dir=tmp_path
        )
    finally:
        reset_interaction_id(token)

    other_token = bind_interaction_id("other-inquiry")
    try:
        record_trace_event(
            "task_started", task_name="unrelated", timestamp=day1, log_dir=tmp_path
        )
    finally:
        reset_interaction_id(other_token)

    # An unbound (interaction_id: null) event must never match either id.
    record_trace_event("task_started", task_name="stray", timestamp=day1, log_dir=tmp_path)

    events = get_trace_events_for_interaction("target-inquiry", log_dir=tmp_path)

    assert [e["task_name"] for e in events] == ["first", "second"]
    assert all(e["interaction_id"] == "target-inquiry" for e in events)


def test_get_trace_events_for_interaction_returns_empty_list_for_unknown_id(
    tmp_path: Path,
) -> None:
    ts = datetime(2026, 9, 1, 10, 0, 0, tzinfo=UTC)
    token = bind_interaction_id("some-other-inquiry")
    try:
        record_trace_event("task_started", task_name="t1", timestamp=ts, log_dir=tmp_path)
    finally:
        reset_interaction_id(token)

    assert get_trace_events_for_interaction("nonexistent-inquiry", log_dir=tmp_path) == []


def test_get_trace_events_for_interaction_returns_empty_list_when_log_dir_missing(
    tmp_path: Path,
) -> None:
    missing_dir = tmp_path / "does-not-exist"
    assert get_trace_events_for_interaction("anything", log_dir=missing_dir) == []
