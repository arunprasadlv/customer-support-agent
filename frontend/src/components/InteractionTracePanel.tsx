import { useEffect, useState } from "react";
import { getInteractionTrace } from "../lib/mockOpsData";
import type { TraceEvent, TraceEventType } from "../types/ops";

interface InteractionTracePanelProps {
  interactionId: string;
}

/** Human-readable label for each raw backend event type (sad.md trace
 * contract) — never render the raw `snake_case` string in the UI. */
/** First line of `taskName`, capped at 80 chars — CrewAI's `task_name`
 * is the task's full (often multi-line, prompt-length) instruction
 * text, not a short label, so this keeps one trace-event row scannable
 * without truncating the underlying data anywhere else. */
function shortTaskName(taskName: string | null): string | null {
  if (!taskName) {
    return null;
  }
  const firstLine = taskName.split("\n")[0];
  return firstLine.length > 80 ? `${firstLine.slice(0, 80)}…` : firstLine;
}

/** Human-readable duration, e.g. "847ms" / "2.3s" — never raw milliseconds. */
function formatDuration(ms: number): string {
  if (ms < 1000) {
    return `${ms}ms`;
  }
  return `${(ms / 1000).toFixed(1)}s`;
}

const EVENT_TYPE_LABELS: Record<TraceEventType, string> = {
  task_started: "Task started",
  task_completed: "Task completed",
  task_failed: "Task failed",
  // Bare start-of-step timing markers (*develop-fe per-step-latency
  // follow-up, 2026-09-01) — no outcome/detail/error/latency fields at
  // all, rendered as a plain "step began" fact (see the render loop below).
  llm_call_started: "LLM call started",
  llm_call_completed: "LLM call",
  llm_call_failed: "LLM call",
  tool_call_started: "Tool call started",
  tool_call_finished: "Tool call",
  tool_call_error: "Tool call",
};

/** `llm_call_started`/`tool_call_started` carry no outcome/latency data —
 * only a timestamp/task_name/agent_role — so they render as a bare
 * timeline entry with no badge section, per the backend's own docstring
 * ("mark a step's start, not its outcome"). */
function isStartMarker(eventType: TraceEventType): boolean {
  return eventType === "llm_call_started" || eventType === "tool_call_started";
}

/**
 * Lazily-fetched end-to-end trace for one interaction (frontend.md §13),
 * rendered inline below its row in `InteractionLogTable.tsx` (an
 * expand-in-place disclosure, not a modal — `aamad.config.yml
 * ui.prefer_modals: false`). Mounted only while its row is expanded, so
 * the fetch effect below doubles as the "only fetch what's currently
 * expanded" behavior — collapsing the row unmounts this component, and
 * re-expanding remounts (and refetches) it.
 *
 * Three distinct states, per the backend contract: loading, a real fetch
 * error (network failure or the interaction id not existing at all --
 * 404 `interaction_not_found`), and a valid empty trace (200, `events:
 * []` -- e.g. the interaction failed before the reasoning Crew ever ran).
 * The empty case is rendered as an informational message, not an error.
 *
 * Per-step latency (`*develop-fe` follow-up, 2026-09-01, sad.md §7
 * NFR-002): `llm_call_completed`/`llm_call_failed`/`tool_call_finished`/
 * `tool_call_error` events now carry `durationMs`/`latencyPass`/
 * `meetsTarget`. Latency is a *separate* signal from the outcome badge
 * already shown — a step can succeed but blow the latency ceiling, or
 * fail fast well under it — so each gets its own explicitly-labeled
 * badge ("Outcome: Success" / "Latency: Pass") rather than one merged
 * indicator. The single step with the highest `durationMs` across the
 * whole trace (computed client-side, no backend call) gets a distinct
 * "Slowest step in this trace" marker — a relative-ranking signal, not a
 * pass/fail one, so it never reuses the amber fail styling.
 */
export default function InteractionTracePanel({ interactionId }: InteractionTracePanelProps) {
  const [events, setEvents] = useState<TraceEvent[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setLoadError(null);
    setEvents(null);
    getInteractionTrace(interactionId)
      .then((data) => {
        if (!cancelled) {
          setEvents(data);
          setIsLoading(false);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          console.error("getInteractionTrace failed", error);
          setLoadError(error instanceof Error ? error.message : "Could not load the trace.");
          setIsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [interactionId]);

  if (isLoading) {
    return <p className="trace-panel__status">Loading trace…</p>;
  }

  if (loadError) {
    return (
      <p className="trace-panel__status trace-panel__status--error" role="alert">
        Could not load the trace: {loadError}
      </p>
    );
  }

  if (!events || events.length === 0) {
    return <p className="trace-panel__status">No trace recorded for this interaction.</p>;
  }

  // Slowest step in this trace (requirement 3): the single event with the
  // highest `durationMs`, computed client-side — no backend call. Strict
  // `>` keeps this to one index even if multiple events tie for the max.
  // Stays -1 (nothing highlighted, no error) when every event's
  // `durationMs` is null — e.g. an all-task-level or empty trace.
  let slowestIndex = -1;
  let slowestDurationMs = -1;
  events.forEach((event, index) => {
    if (event.durationMs != null && event.durationMs > slowestDurationMs) {
      slowestDurationMs = event.durationMs;
      slowestIndex = index;
    }
  });

  return (
    <ol className="trace-panel__list">
      {events.map((event, index) => {
        const isFailure = event.outcome === "failure";
        const isSuccess = event.outcome === "success";
        const isStart = isStartMarker(event.eventType);
        const isSlowest = index === slowestIndex;
        const className = [
          "trace-panel__event",
          isFailure ? "trace-panel__event--failure" : "",
          event.latencyPass === false ? "trace-panel__event--latency-fail" : "",
          isSlowest ? "trace-panel__event--slowest" : "",
        ]
          .filter(Boolean)
          .join(" ");
        return (
          <li key={`${event.timestamp}-${index}`} className={className}>
            <span className="trace-panel__event-time">
              <span className="sr-only">Time: </span>
              {new Date(event.timestamp).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}
            </span>
            <span className="trace-panel__event-agent">
              <span className="sr-only">Agent: </span>
              {event.agentRole ?? "—"}
            </span>
            <span className="trace-panel__event-type">
              <span className="sr-only">Step: </span>
              {EVENT_TYPE_LABELS[event.eventType]}
              {event.taskName ? ` — ${shortTaskName(event.taskName)}` : ""}
            </span>
            {/* `llm_call_started`/`tool_call_started` mark a step's start,
                not its outcome — no outcome/latency badge section for
                them at all, just the timeline entry above. */}
            {!isStart && (
              <>
                {isFailure ? (
                  <span className="ops-indicator ops-indicator--escalated">
                    <span aria-hidden="true">⚠</span> Outcome: Failure
                  </span>
                ) : isSuccess ? (
                  <span className="ops-indicator">
                    <span aria-hidden="true">✓</span> Outcome: Success
                  </span>
                ) : (
                  <span className="ops-indicator ops-indicator--muted">
                    <span aria-hidden="true">…</span> Outcome: In progress
                  </span>
                )}
                {event.durationMs != null && (
                  <span className="trace-panel__duration">
                    <span className="sr-only">Duration: </span>
                    {formatDuration(event.durationMs)}
                  </span>
                )}
                {event.latencyPass === false ? (
                  <span className="ops-indicator ops-indicator--escalated">
                    <span aria-hidden="true">⚠</span> Latency: Fail (over 10s ceiling)
                  </span>
                ) : event.latencyPass === true && event.meetsTarget === false ? (
                  <span className="ops-indicator trace-panel__latency-badge--slow">
                    <span aria-hidden="true">⏱</span> Latency: Slow (over 5s target)
                  </span>
                ) : event.latencyPass === true && event.meetsTarget === true ? (
                  <span className="ops-indicator">
                    <span aria-hidden="true">✓</span> Latency: Pass
                  </span>
                ) : null}
              </>
            )}
            {isSlowest && (
              <span className="trace-panel__slowest-badge">
                <span aria-hidden="true">🐢</span> Slowest step in this trace
              </span>
            )}
            {isFailure && event.error && (
              <p className="trace-panel__event-message trace-panel__event-message--error">
                {event.error}
              </p>
            )}
            {isSuccess && event.detail && (
              <p className="trace-panel__event-message">{event.detail}</p>
            )}
          </li>
        );
      })}
    </ol>
  );
}
