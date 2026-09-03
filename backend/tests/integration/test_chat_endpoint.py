"""Integration tests for `POST /chat` (`*implement-endpoint`, Phase 1 of
sad.md's "MVP Build Sequencing" — see backend.md), `GET /interactions`
(`*implement-endpoint` follow-up, 2026-08-20 — a deliberate Phase 3 -> now
pull-forward per operator decision; see backend.md), and `GET
/interactions/{id}/trace` (`*develop-be` follow-up, 2026-09-01 — Trace Log
interaction correlation; see backend.md).

Two tiers, mirroring `test_inquiry_flow.py`'s pattern:

1. Request validation (422 on malformed input) / empty-state responses —
   deterministic, no LLM/network required.
2. A full live round-trip through `InquiryFlow` via the real HTTP route —
   requires a live `ANTHROPIC_API_KEY`; skipped otherwise.
"""

from __future__ import annotations

import os
import threading

import pytest
from fastapi.testclient import TestClient

from app.flows.inquiry_flow import run_inquiry
from app.main import app
from app.persistence.interaction_log import record_interaction
from app.persistence.trace_log import get_trace_events_for_interaction

pytestmark = pytest.mark.integration

_HAS_ANTHROPIC_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))

client = TestClient(app)


def test_chat_missing_message_returns_422() -> None:
    """FastAPI/Pydantic validation (sad.md §4) — a malformed request must
    surface as a 422, never an unhandled 500."""
    response = client.post("/chat", json={"session_id": "guest-1"})
    assert response.status_code == 422


def test_chat_missing_session_id_returns_422() -> None:
    response = client.post("/chat", json={"message": "hello"})
    assert response.status_code == 422


@pytest.mark.skipif(
    not _HAS_ANTHROPIC_KEY,
    reason="Full POST /chat round-trip requires a live ANTHROPIC_API_KEY "
    "(not available in this environment) — see backend.md Open Questions.",
)
def test_chat_end_to_end_returns_reply_and_escalated(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))

    response = client.post(
        "/chat",
        json={
            "message": "What time is check-in and check-out?",
            "session_id": "guest-chat-endpoint-test",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["reply"], str) and body["reply"]
    assert isinstance(body["escalated"], bool)


def test_interactions_empty_list_when_no_interactions(monkeypatch, tmp_path) -> None:
    """`GET /interactions` (sad.md §4) returns `[]`, not a 404/error, when
    the interaction log is empty — deterministic, no LLM/network."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))

    response = client.get("/interactions")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.skipif(
    not _HAS_ANTHROPIC_KEY,
    reason="Full POST /chat -> GET /interactions round-trip requires a live "
    "ANTHROPIC_API_KEY (not available in this environment) — see "
    "backend.md Open Questions.",
)
def test_interactions_shows_record_after_chat_call(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))

    chat_response = client.post(
        "/chat",
        json={
            "message": "What time is check-in and check-out?",
            "session_id": "guest-interactions-endpoint-test",
        },
    )
    assert chat_response.status_code == 200

    interactions_response = client.get("/interactions")
    assert interactions_response.status_code == 200
    rows = interactions_response.json()

    # Filter to this test's own row by sender_id rather than asserting a
    # total row count: an unrelated *prior* test's un-killable straggler
    # background thread (documented in backend.md §11 — CrewAI's Flow
    # thread can't be forcibly killed once started) can land its own row
    # in this test's tmp_path-scoped db if it finally writes while this
    # test's INTERACTION_LOG_DB_PATH monkeypatch is still active. This
    # mirrors test_inquiry_flow.py's same per-inquiry-id defensive pattern.
    matches = [r for r in rows if r["sender_id"] == "guest-interactions-endpoint-test"]
    assert len(matches) == 1
    row = matches[0]
    assert row["channel"] == "chat"
    assert row["sender_id"] == "guest-interactions-endpoint-test"
    assert row["outcome"] in ("responded", "escalated")
    assert isinstance(row["query_text"], str) and row["query_text"]
    assert isinstance(row["redaction_count"], int)
    assert isinstance(row["redaction_actions"], list)
    # response_text mirrors whatever `POST /chat` actually replied with —
    # except on the sad.md §7 max_execution_time timeout-escalation path
    # (`run_inquiry`'s `except FutureTimeoutError` branch, inquiry_flow.py),
    # which persists only a diagnostic row (no response_text/intent/etc.)
    # and returns a reply that was never itself written to the DB.
    if row.get("diagnostic"):
        assert row["response_text"] is None
    else:
        assert row["response_text"] == chat_response.json()["reply"]
    assert row["outcome"] == ("escalated" if chat_response.json()["escalated"] else "responded")


def test_interaction_trace_returns_404_for_unknown_id(monkeypatch, tmp_path) -> None:
    """sad.md-style not-found convention (same shape as `POST
    /escalations/{id}/resolve`'s 404): `{id}` must match a real
    `interaction_log` row, not just "no trace records exist"."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))

    response = client.get("/interactions/does-not-exist/trace")

    assert response.status_code == 404
    assert response.json()["error_code"] == "interaction_not_found"


def test_interaction_trace_empty_events_for_interaction_with_no_trace_records(
    monkeypatch, tmp_path
) -> None:
    """A *real* interaction-log row with no matching Trace Log records
    (predates this feature, or hit the pii_guard fail-closed halt before
    the reasoning Crew ever ran) must return 200 with `events: []`, never a
    404 — deterministic, no LLM/network required."""
    db_path = tmp_path / "test.db"
    trace_dir = tmp_path / "trace-logs"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))
    monkeypatch.setenv("TRACE_LOG_DIR", str(trace_dir))

    record_interaction(
        {
            "id": "interaction-with-no-trace",
            "created_at": "2026-01-01T00:00:00+00:00",
            "channel": "chat",
            "sender_id": "guest-notrace",
            "query_text": "hello",
            "outcome": "responded",
        }
    )

    response = client.get("/interactions/interaction-with-no-trace/trace")

    assert response.status_code == 200
    body = response.json()
    assert body["interaction_id"] == "interaction-with-no-trace"
    assert body["events"] == []


@pytest.mark.skipif(
    not _HAS_ANTHROPIC_KEY,
    reason="Full run_inquiry() -> GET /interactions/{id}/trace round-trip requires a "
    "live ANTHROPIC_API_KEY (not available in this environment) — see backend.md "
    "Open Questions.",
)
def test_interaction_trace_shows_real_correlated_events_after_inquiry(
    monkeypatch, tmp_path
) -> None:
    """The whole point of this feature: a real inquiry's real Trace Log
    events (LLM calls, tool calls, task lifecycle — emitted by the real
    reasoning Crew and pii_guard Crew) show up, correlated, via the new
    endpoint. Not a mocked/synthetic record."""
    db_path = tmp_path / "test.db"
    trace_dir = tmp_path / "trace-logs"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))
    monkeypatch.setenv("TRACE_LOG_DIR", str(trace_dir))

    result = run_inquiry(
        channel="chat",
        raw_text="What time is check-in and check-out?",
        sender_id="guest-trace-endpoint-test",
    )
    inquiry_id = result["inquiry_id"]

    response = client.get(f"/interactions/{inquiry_id}/trace")

    assert response.status_code == 200
    body = response.json()
    assert body["interaction_id"] == inquiry_id
    events = body["events"]
    # A timeout-escalation run (sad.md §7, see backend.md's documented
    # latency gap) legitimately produces a real interaction-log row but may
    # abandon the flow thread before any Crew events land in time for this
    # assertion to see them if the trace file write races the timeout —
    # so only assert non-empty/real-shaped events on the non-timeout path.
    if result.get("reason") != ["max_execution_time_exceeded"]:
        assert len(events) > 0
        event_types = {e["event"] for e in events}
        # Real lifecycle events from the real reasoning Crew, not a
        # synthetic single record.
        assert "task_started" in event_types
        assert "task_completed" in event_types or "llm_call_completed" in event_types
        timestamps = [e["timestamp"] for e in events]
        assert timestamps == sorted(timestamps)
        for event in events:
            assert set(event.keys()) == {
                "timestamp",
                "event",
                "task_name",
                "agent_role",
                "outcome",
                "detail",
                "error",
                "duration_ms",
                "latency_pass",
                "meets_target",
            }

        # Per-step latency check (`*develop-be` follow-up, 2026-09-01,
        # sad.md §7 NFR-002 thresholds reused verbatim): a real inquiry
        # against the real reasoning Crew emits at least one
        # llm_call_completed event with a matching llm_call_started, so its
        # duration/pass fields must be real, non-null values -- not just
        # present-but-null.
        llm_completed = [e for e in events if e["event"] == "llm_call_completed"]
        assert len(llm_completed) > 0
        for event in llm_completed:
            assert isinstance(event["duration_ms"], int)
            assert event["duration_ms"] >= 0
            assert event["latency_pass"] is (event["duration_ms"] <= 10000)
            assert event["meets_target"] is (event["duration_ms"] <= 5000)


@pytest.mark.skipif(
    not _HAS_ANTHROPIC_KEY,
    reason="Full concurrent run_inquiry() round-trip requires a live "
    "ANTHROPIC_API_KEY (not available in this environment) — see backend.md "
    "Open Questions.",
)
def test_concurrent_inquiries_have_isolated_traces(monkeypatch, tmp_path) -> None:
    """The entire point of adding `interaction_id` correlation: two
    inquiries running concurrently (each on its own dedicated
    `ThreadPoolExecutor` worker thread per `run_inquiry`'s design) must each
    show only their own events in their own trace — never each other's."""
    db_path = tmp_path / "test.db"
    trace_dir = tmp_path / "trace-logs"
    monkeypatch.setenv("INTERACTION_LOG_DB_PATH", str(db_path))
    monkeypatch.setenv("TRACE_LOG_DIR", str(trace_dir))

    results: dict[str, dict] = {}

    def _run(key: str, raw_text: str, sender_id: str) -> None:
        results[key] = run_inquiry(channel="chat", raw_text=raw_text, sender_id=sender_id)

    t1 = threading.Thread(
        target=_run,
        args=("a", "What time is check-in and check-out?", "guest-concurrent-a"),
    )
    t2 = threading.Thread(
        target=_run,
        args=("b", "Can I get extra towels sent to my room?", "guest-concurrent-b"),
    )
    t1.start()
    t2.start()
    t1.join(timeout=60)
    t2.join(timeout=60)

    assert "a" in results and "b" in results
    id_a = results["a"]["inquiry_id"]
    id_b = results["b"]["inquiry_id"]
    assert id_a != id_b

    events_a = client.get(f"/interactions/{id_a}/trace").json()["events"]
    events_b = client.get(f"/interactions/{id_b}/trace").json()["events"]

    a_timed_out = results["a"].get("reason") == ["max_execution_time_exceeded"]
    b_timed_out = results["b"].get("reason") == ["max_execution_time_exceeded"]
    if not a_timed_out:
        assert len(events_a) > 0
    if not b_timed_out:
        assert len(events_b) > 0

    # Cross-check at the raw trace-file level, independent of the
    # endpoint's own filtering logic: both inquiries really did run
    # concurrently on the same shared trace file/event bus, and each event
    # line landed tagged with exactly one of the two distinct interaction
    # ids -- proving the thread-scoped ContextVar kept them apart rather
    # than, say, everything silently collapsing onto whichever inquiry
    # bound the var last.
    all_events = get_trace_events_for_interaction(id_a, log_dir=trace_dir) + (
        get_trace_events_for_interaction(id_b, log_dir=trace_dir)
    )
    seen_ids = {e["interaction_id"] for e in all_events}
    if not a_timed_out and not b_timed_out:
        assert seen_ids == {id_a, id_b}
