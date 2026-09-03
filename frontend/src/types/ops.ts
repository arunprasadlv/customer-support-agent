/**
 * Shared types for the /ops route (interaction log + KB review queue).
 *
 * @frontend.eng, *develop-fe /ops. Field shapes intentionally mirror the
 * future real backend contract (sad.md SS4):
 *   - `GET /interactions` -> InteractionLogEntry[]
 *   - `GET /review-queue` -> ReviewQueueEntry[]
 *   - `POST /review-queue/{id}/approve` / `.../reject` mutate a single
 *     ReviewQueueEntry's `status`.
 * so `@integration.eng` can swap `lib/mockOpsData.ts` for real fetch
 * calls without changing these types or any component that consumes
 * them.
 */

export type InteractionChannel = "chat" | "email";

export type InteractionOutcome = "resolved" | "escalated";

export type SentimentLabel = "Positive" | "Neutral" | "Negative";

export interface InteractionLogEntry {
  id: string;
  timestamp: number;
  channel: InteractionChannel;
  /** Original guest query text (already PII-redacted where applicable — see piiRedacted). */
  query: string;
  /** Classified intent/category from the domain taxonomy (FR-002). */
  classification: string;
  /** Raw sentiment score, -1 (very negative) to 1 (very positive). */
  sentimentScore: number;
  sentimentLabel: SentimentLabel;
  /** Whether pii_guard redacted content for this interaction (FR-011, NFR-006). */
  piiRedacted: boolean;
  outcome: InteractionOutcome;
}

export type ReviewQueueStatus = "pending" | "approved" | "rejected";

export interface ReviewQueueEntry {
  id: string;
  /** Links back to the interaction/escalation this candidate entry came from (FR-008). */
  sourceInteractionId: string;
  originalQuery: string;
  proposedTitle: string;
  proposedContent: string;
  /**
   * Retrieval keywords for the live KB entry this becomes on Approve.
   * `EscalationResolutionFlow` always writes this empty — `kb_search`
   * (ADR-005) skips any entry with zero keywords outright, so an
   * un-edited Approve produces a KB write that can never actually be
   * retrieved by a guest. Almost always `[]` on a pending entry; the
   * Edit UI is what lets a Reviewer fix that before approving.
   */
  keywords: string[];
  status: ReviewQueueStatus;
  /** Set once a decision (approve/reject) has been recorded. */
  decidedAt?: number;
}

/** Payload for an Approve action — edited content if the Reviewer used Edit first. */
export interface ReviewQueueDecisionInput {
  title: string;
  content: string;
  keywords: string[];
}

/**
 * One step in an interaction's end-to-end trace (`GET /interactions/{id}/trace`,
 * added this action — @frontend.eng, *develop-fe /ops trace panel).
 * Mirrors the backend's Crew/task/LLM/tool instrumentation events in
 * chronological order, as returned by the server (no client-side sort
 * needed). `outcome`/`detail`/`error` are nullable on the wire because
 * not every event type carries all three — e.g. a `task_started` event
 * has no outcome yet, and a successful event has no `error`.
 *
 * `llm_call_started`/`tool_call_started` (`*develop-fe` per-step-latency
 * follow-up, 2026-09-01, mirrors the backend's own `*develop-be` addition)
 * are bare timing markers only — no `outcome`/`detail`/`error`/latency
 * fields at all, since they mark a step's *start*, not its outcome.
 */
export type TraceEventType =
  | "task_started"
  | "task_completed"
  | "task_failed"
  | "llm_call_started"
  | "llm_call_completed"
  | "llm_call_failed"
  | "tool_call_started"
  | "tool_call_finished"
  | "tool_call_error";

export type TraceEventOutcome = "success" | "failure" | null;

export interface TraceEvent {
  timestamp: number;
  eventType: TraceEventType;
  taskName: string | null;
  agentRole: string | null;
  outcome: TraceEventOutcome;
  /** Present on a successful event; human-readable context (e.g. LLM call summary). */
  detail: string | null;
  /** Present on a failed event; the error text to surface to ops staff. */
  error: string | null;
  /**
   * Per-step latency check (sad.md §7 NFR-002), `*develop-fe` follow-up
   * 2026-09-01 — present (non-null) only on `llm_call_completed`/
   * `llm_call_failed`/`tool_call_finished`/`tool_call_error` events;
   * `null` on every other event type (including the two `*_started`
   * markers above, and on an unpaired completion the backend couldn't
   * time). Wall-clock time for this step, in milliseconds.
   */
  durationMs: number | null;
  /** `true` iff `durationMs <= 10_000` — sad.md §7's 10s hard ceiling. Same nullability as `durationMs`. */
  latencyPass: boolean | null;
  /** `true` iff `durationMs <= 5_000` — sad.md §7's 5s target. Same nullability as `durationMs`. */
  meetsTarget: boolean | null;
}
