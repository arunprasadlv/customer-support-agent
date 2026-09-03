"""Trace Log persistence — adapter-crewai.md Logging: "Record lifecycle
events (task start/stop, retries, guardrail outcomes) in Trace Log ... If
using step callbacks/event listeners, redact secrets and persist logs
under project-context/2.build/logs." sad.md echoes the same requirement
verbatim. As of this module's introduction, `project-context/2.build/logs/`
was empty despite this being architecturally mandated — this closes that
gap for the reasoning Crew (`agents/reasoning_crew.py`) and the standalone
`pii_guard` agent (`agents/pii_guard.py`, ADR-003).

Why an event-bus listener (`crewai.events.BaseEventListener`) instead of
`Crew(step_callback=..., task_callback=...)`: CrewAI's event bus
(`crewai.events.event_bus.crewai_event_bus`) is process-global, not
per-Crew. One listener, installed once via `install_trace_listener()`,
observes every `Crew.kickoff()` call in the process — `reasoning_crew.py`'s
4-agent Crew *and* `pii_guard.py`'s standalone single-agent Crew alike —
with no per-Crew wiring to forget and no need for pii_guard to define its
own separate hook. It also gives an authoritative success/failure signal
for tool and LLM calls (`ToolUsageFinishedEvent`/`ToolUsageErrorEvent`,
`LLMCallCompletedEvent`/`LLMCallFailedEvent`) instead of having to infer
success from a `step_callback`'s `AgentAction.result` string, which CrewAI
itself already collapses tool errors into (see
`crewai.utilities.tool_utils.execute_tool_and_check_finality`).

Events traced, one JSON line each, per adapter-crewai.md's three named
lifecycle categories:
    - task start/stop:  TaskStartedEvent, TaskCompletedEvent, TaskFailedEvent
    - LLM calls:         LLMCallStartedEvent (timing marker only),
                         LLMCallCompletedEvent, LLMCallFailedEvent
    - tool calls:        ToolUsageStartedEvent (timing marker only),
                         ToolUsageFinishedEvent, ToolUsageErrorEvent
`LLMCallStartedEvent`/`ToolUsageStartedEvent` carry the full outbound
prompt/messages (`messages`/`tool_args`), and this run's task instructions
are explicit that full prompts must not be logged in the clear. They ARE
now subscribed to (per-step latency check, see below), but their handlers
record ONLY a bare timing marker — timestamp, task_name, agent_role,
event name — and never populate `detail`/`error` from the event's own
fields, so none of that prompt/tool-arg content reaches disk. Retries and
guardrail outcomes: this crew configuration defines no `Task.guardrail`s
and CrewAI does not emit a distinct "retry" event separate from
`max_retry_limit`'s internal LLM-level retry loop, so there is nothing
further to trace under those two categories for this app today; if either
is added later, wire its event/outcome into `record_trace_event` the same
way.

Per-step latency check (`*develop-be` follow-up, 2026-09-01): sad.md §7
pins NFR-002 latency thresholds for whole-inquiry latency — "p95 ≤ 5s
target" and "10s hard ceiling (2x target)". This reuses those exact two
numbers (5_000ms / 10_000ms — see `_LATENCY_TARGET_MS`/
`_LATENCY_HARD_CEILING_MS` below), unchanged, as the pass/fail bar for
each *individual* LLM/tool call instead of the whole inquiry. This is an
operator-confirmed reuse of an existing threshold, not a new number chosen
here. Every `llm_call_completed`/`llm_call_failed`/`tool_call_finished`/
`tool_call_error` record gains three fields: `duration_ms` (the time since
the matching `*_started` event, or `null` if no matching start was seen),
`latency_pass` (`duration_ms <= 10_000`, or `null`), and `meets_target`
(`duration_ms <= 5_000`, or `null`). `task_started`/`task_completed`/
`task_failed` records and the two new `*_started` records themselves are
unchanged — this check is scoped to individual LLM/tool calls only.

Pairing mechanism: CrewAI's sequential process means one inquiry's LLM/tool
calls happen one at a time on that inquiry's dedicated worker thread (see
`inquiry_flow.py::_run_flow_with_trace_correlation`), so a single pending
"start timestamp" slot per `(interaction_id, category)` — category being
`"llm"` or `"tool"` — is enough to pair a `*_started` event with its
completion: `_on_*_started` sets the slot, the matching completion handler
pops it. Because the event bus is process-global and multiple *different*
inquiries run concurrently on different worker threads, the slot is keyed
by `get_current_interaction_id()` (not just category) and guarded by
`_PENDING_LOCK`, so two concurrent inquiries' timings cannot bleed into
each other (see `test_trace_log.py`'s concurrency test, mirroring the
existing interaction_id-correlation concurrency test). An unmatched
completion (no prior start recorded for that slot — e.g. a stray direct
`record_trace_event`/handler call in a test, or a process restart mid-call)
pops `None` and yields `duration_ms: null` rather than raising.

Layout: one append-only JSONL file per UTC calendar day,
`project-context/2.build/logs/trace-YYYY-MM-DD.jsonl` (directory and file
created on first write). Each line:
    {
        "timestamp": "<ISO-8601 UTC>",
        "event": "task_started" | "task_completed" | "task_failed"
                 | "llm_call_started" | "llm_call_completed" | "llm_call_failed"
                 | "tool_call_started" | "tool_call_finished" | "tool_call_error",
        "interaction_id": str | null,  # correlates every event in one
                                        # inquiry's trace — see "Interaction
                                        # correlation" below
        "task_name": str | null,
        "agent_role": str | null,
        "outcome": "success" | "failure" | null,   # null only for *_started
        "detail": str | null,   # short, redacted summary — present on
                                 # completion/success events
        "error": str | null,    # short, redacted error message — present
                                 # on failure events

        # Present ONLY on llm_call_completed/llm_call_failed/
        # tool_call_finished/tool_call_error records — see "Per-step latency
        # check" above. Absent (not even null) on task_* and *_started
        # records.
        "duration_ms": int | null,
        "latency_pass": bool | null,   # duration_ms <= 10_000 (sad.md §7)
        "meets_target": bool | null,   # duration_ms <= 5_000 (sad.md §7)
    }

Interaction correlation: `record_trace_event` reads `interaction_id` from
`_current_interaction_id`, a `contextvars.ContextVar`, rather than
accepting it as a caller-supplied argument — CrewAI's event bus calls
`TraceLogListener._on_*` with only the event object, and threading the id
through every `Crew.kickoff()`/`Task`/tool call in `reasoning_crew.py` and
`pii_guard.py` to reach those handlers is exactly the kind of invasive
per-call-site plumbing an ambient, thread-scoped context var avoids.

This depends on the specific thread model `inquiry_flow.py::run_inquiry`
uses: one *fresh* `ThreadPoolExecutor(max_workers=1)` per inquiry, whose
single worker thread runs `InquiryFlow().kickoff()` (which synchronously
also runs the `pii_guard` Crew) start-to-finish. `bind_interaction_id()`
must be called as the *first statement of the callable actually submitted*
to that pool — verified directly (see test_trace_log.py) that
`ThreadPoolExecutor.submit()` does **not** propagate the submitting
thread's contextvars into the worker thread the way `asyncio` propagates
context into Tasks; a plain `pool.submit(InquiryFlow().kickoff, ...)` after
setting the var on the calling thread would leave the var unset (back at
its default, `None`) inside the worker. `run_inquiry` instead submits a
small wrapper function that sets the var on the worker thread itself before
calling `kickoff()`. Because the var is thread-scoped (not
Task/coroutine-scoped) and the whole `kickoff()` call — including the
nested `pii_guard` Crew — runs synchronously on that one worker thread, one
`.set()` call correlates every event either Crew emits for that inquiry.
Records written with no interaction_id bound (e.g. a test that calls
`record_trace_event`/the `_on_*` handlers directly, or any stray direct
`InquiryFlow()` use outside `run_inquiry`) simply get `interaction_id:
null` — `_current_interaction_id.get()` returns its default, `None`, and
nothing here raises on that.

Redaction (adapter-crewai.md "redact secrets"): every `detail`/`error`
string is passed through `_redact()` before being written — it reuses
`app.tools.pii_detector.detect_pii` (the same deterministic patterns
pii_guard itself runs) plus a small API-key-shaped pattern. This matters
most for pii_guard's own events: its `pii_detector` tool call's raw
`tool_args`/output legitimately carries un-redacted PII (that is the whole
point of the tool), so pii_guard's own trace entries must never write that
raw text to disk. `_redact()` applies unconditionally to every event this
module writes, regardless of which crew emitted it, so this is not
something a caller must remember to do per-agent. Strings are also
length-capped (`_MAX_FIELD_LEN`) so a large LLM response can't blow up the
log file.
"""

from __future__ import annotations

import contextvars
import json
import os
import re
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from crewai.events.base_event_listener import BaseEventListener
from crewai.events.event_bus import CrewAIEventsBus
from crewai.events.types.llm_events import (
    LLMCallCompletedEvent,
    LLMCallFailedEvent,
    LLMCallStartedEvent,
)
from crewai.events.types.task_events import (
    TaskCompletedEvent,
    TaskFailedEvent,
    TaskStartedEvent,
)
from crewai.events.types.tool_usage_events import (
    ToolUsageErrorEvent,
    ToolUsageFinishedEvent,
    ToolUsageStartedEvent,
)

from app.tools.pii_detector import detect_pii

# backend/src/app/persistence/trace_log.py -> customer-support-agent/ (repo root)
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_LOG_DIR = _REPO_ROOT / "project-context" / "2.build" / "logs"

_MAX_FIELD_LEN = 500

# Defense-in-depth alongside PII redaction: mask anything shaped like a
# provider API key (e.g. Anthropic's `sk-ant-...`) if it were ever to end
# up in an error message or LLM response.
_SECRET_RE = re.compile(r"\b(?:sk|pk)-[A-Za-z0-9_-]{10,}\b")

# Per-step latency check thresholds — sad.md §7's NFR-002 numbers, reused
# verbatim (operator-confirmed choice, not a new number picked here). See
# module docstring "Per-step latency check".
_LATENCY_TARGET_MS = 5_000  # sad.md §7: p95 <= 5s target
_LATENCY_HARD_CEILING_MS = 10_000  # sad.md §7: 10s hard ceiling (2x target)

_WRITE_LOCK = threading.Lock()

# Thread-scoped (not asyncio-Task-scoped) correlation id — see the module
# docstring's "Interaction correlation" section for why this is a
# ContextVar rather than a `record_trace_event` parameter, and for exactly
# which thread must call `bind_interaction_id` for this to work under
# `inquiry_flow.py::run_inquiry`'s one-fresh-pool-per-inquiry thread model.
_current_interaction_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_current_interaction_id", default=None
)


def bind_interaction_id(interaction_id: str | None) -> contextvars.Token[str | None]:
    """Correlate every trace event recorded on the *current thread* from
    this call forward with `interaction_id`, until/unless
    `reset_interaction_id` is called with the returned token.

    Must be called as (effectively) the first statement of whatever
    callable is actually submitted to a `ThreadPoolExecutor` — setting this
    on the calling thread before `pool.submit(...)` does NOT propagate to
    the worker thread; `ThreadPoolExecutor` does not copy the submitting
    thread's `contextvars.Context` into the worker the way `asyncio` does
    for Tasks (verified directly, see test_trace_log.py). See
    `app.flows.inquiry_flow.run_inquiry` for the real call site.
    """
    return _current_interaction_id.set(interaction_id)


def reset_interaction_id(token: contextvars.Token[str | None]) -> None:
    """Undo a `bind_interaction_id` call. Not required for correctness in
    `run_inquiry`'s one-shot-worker-thread model (the thread never runs a
    second inquiry), but provided for callers/tests that reuse a thread
    across multiple bindings and need to avoid leaking one inquiry's id
    into another's trace events."""
    _current_interaction_id.reset(token)


def get_current_interaction_id() -> str | None:
    """The interaction id bound on the current thread via
    `bind_interaction_id`, or `None` if none is bound."""
    return _current_interaction_id.get()


# Per-step latency pairing state (see module docstring "Per-step latency
# check" / "Pairing mechanism"). Keyed by (interaction_id, category) —
# category is "llm" or "tool" — so two inquiries running concurrently on
# different worker threads never see each other's pending start timestamp.
# `_PENDING_LOCK` guards both the read-check-write on `_on_*_started` and
# the pop-if-present on the matching completion handler; the event bus is
# process-global, so without this lock two threads racing on the same key
# (which should not happen for one inquiry per the sequential-process
# design assumption, but could across unrelated concurrent inquiries
# sharing this one process-wide dict) could interleave unsafely.
_PENDING_LOCK = threading.Lock()
_pending_step_starts: dict[tuple[str | None, str], datetime] = {}


def _mark_step_started(category: str, timestamp: datetime) -> None:
    """Record `timestamp` as the pending start for the current interaction's
    `category` ("llm" or "tool") slot, to be consumed by the matching
    completion event via `_pop_step_duration_ms`."""
    key = (_current_interaction_id.get(), category)
    with _PENDING_LOCK:
        _pending_step_starts[key] = timestamp


def _pop_step_duration_ms(category: str, timestamp: datetime) -> int | None:
    """Consume the pending start for the current interaction's `category`
    slot and return the elapsed milliseconds to `timestamp`, or `None` if no
    matching start was recorded (e.g. a stray completion event with no
    prior start — handled gracefully, never raises)."""
    key = (_current_interaction_id.get(), category)
    with _PENDING_LOCK:
        start = _pending_step_starts.pop(key, None)
    if start is None:
        return None
    return round((timestamp - start).total_seconds() * 1000)


def _latency_fields(duration_ms: int | None) -> dict[str, Any]:
    """The three per-step latency fields for one llm/tool call completion
    record, reusing sad.md §7's NFR-002 thresholds verbatim (see
    `_LATENCY_TARGET_MS`/`_LATENCY_HARD_CEILING_MS`). `<=` (not `<`) at both
    boundaries, per spec: exactly 5000ms meets target, exactly 10000ms
    passes the hard ceiling."""
    if duration_ms is None:
        return {"duration_ms": None, "latency_pass": None, "meets_target": None}
    return {
        "duration_ms": duration_ms,
        "latency_pass": duration_ms <= _LATENCY_HARD_CEILING_MS,
        "meets_target": duration_ms <= _LATENCY_TARGET_MS,
    }


def _resolve_log_dir(log_dir: str | os.PathLike[str] | None = None) -> Path:
    if log_dir is not None:
        return Path(log_dir)
    env_dir = os.environ.get("TRACE_LOG_DIR")
    return Path(env_dir) if env_dir else _DEFAULT_LOG_DIR


def _redact(text: str) -> str:
    """Mask secrets/PII in `text` before it is ever written to disk.
    Deterministic, same style as app.tools.pii_detector.detect_pii — no
    LLM call, no guessing."""
    masked = _SECRET_RE.sub("[REDACTED_SECRET]", text)
    return detect_pii(masked).clean_text


def _redact_and_truncate(value: Any) -> str | None:
    if value is None:
        return None
    text = _redact(str(value))
    if len(text) > _MAX_FIELD_LEN:
        text = text[:_MAX_FIELD_LEN] + "...[truncated]"
    return text


def record_trace_event(
    event_name: str,
    *,
    task_name: str | None = None,
    agent_role: str | None = None,
    outcome: str | None = None,
    detail: Any = None,
    error: Any = None,
    timestamp: datetime | None = None,
    log_dir: str | os.PathLike[str] | None = None,
    duration_ms: int | None = None,
    include_latency: bool = False,
) -> None:
    """Append one redacted, length-capped trace record as a JSON line.

    Pure(-ish) I/O function, deliberately decoupled from CrewAI's event
    types so it can be unit-tested directly (same pattern as
    `interaction_log.record_interaction` / `review_queue.record_review_
    queue_entry`) without needing to construct real CrewAI events.

    `interaction_id` is deliberately NOT a parameter here — it is read from
    `_current_interaction_id` (see `bind_interaction_id`/module docstring
    "Interaction correlation"), so every call site (this function's direct
    callers and every `TraceLogListener._on_*` handler alike) gets
    correlation for free with no argument to remember to thread through.

    `include_latency`/`duration_ms`: per-step latency check (module
    docstring "Per-step latency check"). Only `llm_call_completed`/
    `llm_call_failed`/`tool_call_finished`/`tool_call_error` callers pass
    `include_latency=True` — this adds `duration_ms`/`latency_pass`/
    `meets_target` to the record. Every other event (task_* and the two
    `*_started` events) omits these keys entirely rather than writing them
    as null, since they are not applicable there.
    """
    ts = timestamp or datetime.now(UTC)
    record: dict[str, Any] = {
        "timestamp": ts.isoformat(),
        "event": event_name,
        "interaction_id": _current_interaction_id.get(),
        "task_name": task_name,
        "agent_role": agent_role,
        "outcome": outcome,
        "detail": _redact_and_truncate(detail),
        "error": _redact_and_truncate(error),
    }
    if include_latency:
        record.update(_latency_fields(duration_ms))

    directory = _resolve_log_dir(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    day = ts.strftime("%Y-%m-%d")
    path = directory / f"trace-{day}.jsonl"
    line = json.dumps(record, ensure_ascii=False)
    with _WRITE_LOCK:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def get_trace_events_for_interaction(
    interaction_id: str,
    log_dir: str | os.PathLike[str] | None = None,
) -> list[dict[str, Any]]:
    """Return every trace record correlated to `interaction_id`, in
    chronological order (by `timestamp`). Empty list if none exist — this
    is a normal, expected result (e.g. the interaction hit the pii_guard
    fail-closed halt before the reasoning Crew ever ran, or predates this
    correlation feature), not an error condition; the caller (`GET
    /interactions/{id}/trace` in `app.main`) is responsible for 404-ing on
    an *unknown interaction id*, which this function has no way to detect
    on its own — it only knows about trace files, not `interaction_log`.

    Scans every `trace-*.jsonl` file present in the log directory rather
    than narrowing to one calendar day via `interaction_log.
    get_interaction_by_id(...)["created_at"]`. This app's MVP log volume is
    tiny (per setup.md Assumptions: four hotel scenario categories, no real
    traffic), so a full scan costs nothing in practice, and it sidesteps
    both an unnecessary new dependency from `trace_log` onto
    `interaction_log` and a day-boundary edge case (a run that starts
    before and finishes after UTC midnight would otherwise split its trace
    across two files that a single-day lookup could miss part of).
    """
    directory = _resolve_log_dir(log_dir)
    if not directory.is_dir():
        return []

    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob("trace-*.jsonl")):
        with open(path, encoding="utf-8") as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                record = json.loads(raw_line)
                if record.get("interaction_id") == interaction_id:
                    records.append(record)

    records.sort(key=lambda r: r["timestamp"])
    return records


class TraceLogListener(BaseEventListener):
    """Subscribes to crewai's process-global event bus and forwards each
    lifecycle event to `record_trace_event`. See module docstring for which
    events are traced and why.

    Handlers are bound instance methods (`_on_*`), not anonymous closures,
    specifically so tests can call the event -> `record_trace_event`
    mapping logic directly (`listener._on_task_completed(None, event)`)
    without ever touching `crewai_event_bus`. That matters because the bus
    is process-global with no unsubscribe mechanism: a test that calls
    `crewai_event_bus.emit()` risks a *real*, still-registered production
    listener (from an earlier `install_trace_listener()` call made by a
    live integration test elsewhere in the same pytest session) receiving
    the test's synthetic event and writing it into the real
    project-context/2.build/logs directory. Testing the handler methods
    directly sidesteps the bus entirely.
    """

    def __init__(self, log_dir: str | os.PathLike[str] | None = None) -> None:
        self._log_dir = log_dir
        super().__init__()

    def setup_listeners(self, crewai_event_bus: CrewAIEventsBus) -> None:
        crewai_event_bus.on(TaskStartedEvent)(self._on_task_started)
        crewai_event_bus.on(TaskCompletedEvent)(self._on_task_completed)
        crewai_event_bus.on(TaskFailedEvent)(self._on_task_failed)
        crewai_event_bus.on(LLMCallStartedEvent)(self._on_llm_call_started)
        crewai_event_bus.on(LLMCallCompletedEvent)(self._on_llm_call_completed)
        crewai_event_bus.on(LLMCallFailedEvent)(self._on_llm_call_failed)
        crewai_event_bus.on(ToolUsageStartedEvent)(self._on_tool_usage_started)
        crewai_event_bus.on(ToolUsageFinishedEvent)(self._on_tool_usage_finished)
        crewai_event_bus.on(ToolUsageErrorEvent)(self._on_tool_usage_error)

    def _on_task_started(self, source: Any, event: TaskStartedEvent) -> None:
        record_trace_event(
            "task_started",
            task_name=event.task_name,
            agent_role=event.agent_role,
            timestamp=event.timestamp,
            log_dir=self._log_dir,
        )

    def _on_task_completed(self, source: Any, event: TaskCompletedEvent) -> None:
        output = event.output
        detail = (output.raw if output and output.raw else str(output)) if output else None
        record_trace_event(
            "task_completed",
            task_name=event.task_name,
            agent_role=event.agent_role,
            outcome="success",
            detail=detail,
            timestamp=event.timestamp,
            log_dir=self._log_dir,
        )

    def _on_task_failed(self, source: Any, event: TaskFailedEvent) -> None:
        record_trace_event(
            "task_failed",
            task_name=event.task_name,
            agent_role=event.agent_role,
            outcome="failure",
            error=event.error,
            timestamp=event.timestamp,
            log_dir=self._log_dir,
        )

    def _on_llm_call_started(self, source: Any, event: LLMCallStartedEvent) -> None:
        """Bare timing marker only — `LLMCallStartedEvent` carries the full
        outbound `messages` (prompt); never pass any event field other than
        `task_name`/`agent_role`/`timestamp` into `record_trace_event`."""
        _mark_step_started("llm", event.timestamp)
        record_trace_event(
            "llm_call_started",
            task_name=event.task_name,
            agent_role=event.agent_role,
            timestamp=event.timestamp,
            log_dir=self._log_dir,
        )

    def _on_llm_call_completed(self, source: Any, event: LLMCallCompletedEvent) -> None:
        duration_ms = _pop_step_duration_ms("llm", event.timestamp)
        record_trace_event(
            "llm_call_completed",
            task_name=event.task_name,
            agent_role=event.agent_role,
            outcome="success",
            detail=event.response,
            timestamp=event.timestamp,
            log_dir=self._log_dir,
            duration_ms=duration_ms,
            include_latency=True,
        )

    def _on_llm_call_failed(self, source: Any, event: LLMCallFailedEvent) -> None:
        duration_ms = _pop_step_duration_ms("llm", event.timestamp)
        record_trace_event(
            "llm_call_failed",
            task_name=event.task_name,
            agent_role=event.agent_role,
            outcome="failure",
            error=event.error,
            timestamp=event.timestamp,
            log_dir=self._log_dir,
            duration_ms=duration_ms,
            include_latency=True,
        )

    def _on_tool_usage_started(self, source: Any, event: ToolUsageStartedEvent) -> None:
        """Bare timing marker only — `ToolUsageStartedEvent` carries the raw
        `tool_args` (which, e.g. for pii_guard's own tool call, legitimately
        contains real PII); never pass any event field other than
        `task_name`/`agent_role`/`timestamp` into `record_trace_event`."""
        _mark_step_started("tool", event.timestamp)
        record_trace_event(
            "tool_call_started",
            task_name=event.task_name,
            agent_role=event.agent_role,
            timestamp=event.timestamp,
            log_dir=self._log_dir,
        )

    def _on_tool_usage_finished(self, source: Any, event: ToolUsageFinishedEvent) -> None:
        duration_ms = _pop_step_duration_ms("tool", event.timestamp)
        failed = event.failure is not None
        detail = f"tool={event.tool_name} args={event.tool_args} output={event.output!r}"
        record_trace_event(
            "tool_call_finished",
            task_name=event.task_name,
            agent_role=event.agent_role,
            outcome="failure" if failed else "success",
            detail=None if failed else detail,
            error=detail if failed else None,
            timestamp=event.timestamp,
            log_dir=self._log_dir,
            duration_ms=duration_ms,
            include_latency=True,
        )

    def _on_tool_usage_error(self, source: Any, event: ToolUsageErrorEvent) -> None:
        duration_ms = _pop_step_duration_ms("tool", event.timestamp)
        record_trace_event(
            "tool_call_error",
            task_name=event.task_name,
            agent_role=event.agent_role,
            outcome="failure",
            error=f"tool={event.tool_name} args={event.tool_args} error={event.error}",
            timestamp=event.timestamp,
            log_dir=self._log_dir,
            duration_ms=duration_ms,
            include_latency=True,
        )


_listener: TraceLogListener | None = None
_install_lock = threading.Lock()


def install_trace_listener(
    log_dir: str | os.PathLike[str] | None = None,
) -> TraceLogListener:
    """Idempotently install the process-global Trace Log listener.

    Safe and cheap to call from both `reasoning_crew.build_reasoning_crew`
    and `pii_guard.build_pii_guard_crew` at Crew-build time — CrewAI's
    event bus is a singleton, so a second (or hundredth) call is a no-op
    that returns the already-installed instance rather than double-
    registering handlers (which would otherwise double-write every trace
    line).
    """
    global _listener
    with _install_lock:
        if _listener is None:
            _listener = TraceLogListener(log_dir=log_dir)
        return _listener
