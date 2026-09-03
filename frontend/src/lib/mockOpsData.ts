import { apiFetch } from "./apiClient";
import type {
  InteractionLogEntry,
  ReviewQueueDecisionInput,
  ReviewQueueEntry,
  TraceEvent,
  TraceEventType,
} from "../types/ops";

/**
 * `@integration.eng`'s `*integrate-api` swap: real ops-view backend calls
 * (sad.md §4):
 *   - `GET /interactions`                      -> getInteractions()
 *   - `GET /review-queue`                      -> getReviewQueue()
 *   - `POST /review-queue/{id}/approve`        -> approveReviewQueueEntry(id, edited?)
 *   - `POST /review-queue/{id}/reject`         -> rejectReviewQueueEntry(id)
 *   - `POST /escalations/{id}/resolve`         -> resolveEscalation(id, resolutionText)
 *       (`@frontend.eng`'s `*develop-fe` addition, frontend.md §11 --
 *       added directly against the real backend, following the pattern
 *       the other four functions already established; no mock-then-swap
 *       cycle for this one.)
 *   - `GET /interactions/{id}/trace`           -> getInteractionTrace(id)
 *       (`@frontend.eng`'s `*develop-fe` addition, frontend.md §13 --
 *       backend contract handed over already-verified; added directly
 *       against the real endpoint, same pattern as resolveEscalation.)
 *
 * Filename/exports kept as `mockOpsData.ts` — the exact swap point
 * `@frontend.eng` built `InteractionLog.tsx`/`ReviewQueue.tsx`/
 * `ReviewQueueItem.tsx` against. Function signatures and the
 * `InteractionLogEntry`/`ReviewQueueEntry` return shapes (frontend/src/
 * types/ops.ts) are UNCHANGED from the mock — no component edits needed —
 * but the real backend's field names/types don't match those frontend
 * types 1:1, so this module now does real mapping work the mock never
 * needed. Both mismatches are `@integration.eng` judgment calls, written
 * up in full in project-context/2.build/integration.md (mirroring
 * frontend.md's §9.5/§10.5 convention) — summarized inline below.
 */

// ---------------------------------------------------------------------
// GET /interactions -> InteractionLogEntry[]
// ---------------------------------------------------------------------

/** Raw shape of one `GET /interactions` row (main.py `InteractionRecord`). */
interface InteractionRecordDto {
  id: string;
  created_at: string;
  channel: string;
  sender_id: string;
  query_text: string;
  intent: string | null;
  confidence: number | null;
  sentiment_score: number | null;
  sentiment_label: string | null;
  match_found: boolean | null;
  grounded: boolean | null;
  response_text: string | null;
  outcome: "responded" | "escalated" | "diagnostic_halt";
  redaction_count: number;
  redaction_actions: Array<Record<string, unknown>>;
  diagnostic: string | null;
}

/**
 * Judgment call (integration.md): maps the backend's `InteractionRecord`
 * onto the frontend's pre-existing `InteractionLogEntry` shape.
 *   - `timestamp` <- `Date.parse(created_at)` (backend: ISO string, UI: epoch ms).
 *   - `query` <- `query_text`; `classification` <- `intent` (falls back to
 *     "Unclassified" — `intent` is nullable on diagnostic-halt rows).
 *   - `sentimentScore`/`sentimentLabel` <- `sentiment_score`/`sentiment_label`,
 *     falling back to `0`/`"Neutral"` when null (same diagnostic-halt case).
 *   - `piiRedacted` <- `redaction_count > 0` (frontend has no concept of a
 *     redaction *count*, only a boolean).
 *   - `outcome`: frontend only models `"resolved" | "escalated"`; backend
 *     has a third state, `"diagnostic_halt"` (a caught internal failure —
 *     see main.py's `ChatProcessingError`/diagnostic path). Mapped to
 *     `"escalated"`, not `"resolved"`, because a halted interaction is
 *     exactly the "needs a human to look at this" case the escalated
 *     column/UI already communicates — collapsing it into "resolved"
 *     would misrepresent a failure as a successful response.
 */
function toInteractionLogEntry(row: InteractionRecordDto): InteractionLogEntry {
  return {
    id: row.id,
    timestamp: Date.parse(row.created_at),
    channel: row.channel === "email" ? "email" : "chat",
    query: row.query_text,
    classification: row.intent ?? "Unclassified",
    sentimentScore: row.sentiment_score ?? 0,
    sentimentLabel: (row.sentiment_label as InteractionLogEntry["sentimentLabel"]) ?? "Neutral",
    piiRedacted: row.redaction_count > 0,
    outcome: row.outcome === "responded" ? "resolved" : "escalated",
  };
}

/** Real `GET /interactions` call for the ops interaction log. */
export async function getInteractions(): Promise<InteractionLogEntry[]> {
  const rows = await apiFetch<InteractionRecordDto[]>("/interactions");
  return rows.map(toInteractionLogEntry);
}

// ---------------------------------------------------------------------
// GET /review-queue -> ReviewQueueEntry[]
// ---------------------------------------------------------------------

/** Raw shape of one `GET /review-queue` row (main.py `ReviewQueueItem`). */
interface ReviewQueueItemDto {
  id: string;
  created_at: string;
  original_inquiry_id: string;
  original_query_text: string | null;
  resolution_text: string;
  candidate_intent: string | null;
  candidate_section: string | null;
  candidate_keywords: string[];
  candidate_content: string;
  status: "pending" | "approved" | "rejected";
}

/**
 * Judgment call (integration.md, mirrors frontend.md §9.5/§10.5 style):
 * the frontend's `ReviewQueueEntry` has a `proposedTitle` field the
 * backend has no equivalent for at all (only `candidate_intent` — a
 * technical classification/retrieval key used to *filter* `kb_search`,
 * see `app/domain/loader.py`'s ADR-005 — and `candidate_section`, a
 * human-readable heading, e.g. domain_config.json's `"section":
 * "Cancellation policy"`). Resolved as:
 *   `proposedTitle = candidate_section || candidate_intent || "Untitled candidate KB entry"`
 * i.e. prefer the human-readable section heading (what a Reviewer
 * actually thinks of as a "title"); fall back to the intent slug only if
 * no section was ever set; a final literal fallback so the column is
 * never blank. `candidate_intent` is deliberately NOT the primary
 * choice — it's a machine-facing filter key, not a label, and mapping
 * `proposedTitle` there could tempt a Reviewer editing "the title" into
 * unknowingly editing something else (see `approveReviewQueueEntry`
 * below, where the same reasoning applies to the *write* direction).
 *
 * `decidedAt` (backend does not persist a real decision timestamp): for
 * non-pending rows, approximated as `Date.parse(created_at)` rather than
 * `Date.now()` at fetch time — `created_at` is a *stable* value across
 * repeated fetches, so the "Recently decided" sort in `ReviewQueue.tsx`
 * stays deterministic; `Date.now()` would reshuffle that list on every
 * refetch. This is a known imprecision (queue-creation time, not actual
 * decision time) — documented in integration.md, not silently assumed.
 */
function toReviewQueueEntry(row: ReviewQueueItemDto): ReviewQueueEntry {
  const proposedTitle = row.candidate_section || row.candidate_intent || "Untitled candidate KB entry";
  return {
    id: row.id,
    sourceInteractionId: row.original_inquiry_id,
    originalQuery: row.original_query_text ?? row.resolution_text,
    proposedTitle,
    proposedContent: row.candidate_content,
    keywords: row.candidate_keywords,
    status: row.status,
    decidedAt: row.status !== "pending" ? Date.parse(row.created_at) : undefined,
  };
}

/** Real `GET /review-queue` call for the KB review queue. */
export async function getReviewQueue(): Promise<ReviewQueueEntry[]> {
  const rows = await apiFetch<ReviewQueueItemDto[]>("/review-queue");
  return rows.map(toReviewQueueEntry);
}

// ---------------------------------------------------------------------
// POST /review-queue/{id}/approve, POST /review-queue/{id}/reject
// ---------------------------------------------------------------------

/** Raw shape of `POST /review-queue/{id}/approve`'s response (main.py `KBEntryResponse`). */
interface KBEntryResponseDto {
  kb_entry_id: string;
  intent: string;
  section: string;
  keywords: string[];
  content: string;
}

/**
 * Real `POST /review-queue/{id}/approve`. Judgment call (integration.md):
 * the mock returned the full updated `ReviewQueueEntry` directly; the
 * real endpoint returns a `KBEntryResponse` (the newly written *KB*
 * entry — `kb_entry_id`/`intent`/`section`/`keywords`/`content` — not a
 * review-queue row, and it carries no `status`/`id`-matching-the-queue-
 * row shape at all). Rather than hand-synthesizing a `ReviewQueueEntry`
 * from the approve response (which would require guessing `status`
 * would be `"approved"` — true today, but coupling the client to that
 * assumption instead of the server's actual state), this function
 * re-fetches `GET /review-queue` after a successful approve and returns
 * the freshly mapped entry for `id`. One extra round trip, but it keeps
 * the client's post-action state always server-truth instead of
 * client-assumed — consistent with this MVP having no optimistic-update
 * requirement anywhere else.
 *
 * `edited` (title/content/keywords) maps onto the approve request body's
 * `{intent?, section?, keywords?, content?}` (all-optional overrides
 * over the stored candidate — see main.py `ApproveReviewQueueRequest`):
 *   - `edited.content` -> `content` (direct, unambiguous).
 *   - `edited.title` -> `section`, NOT `intent`. Same reasoning as
 *     `toReviewQueueEntry`'s read-direction mapping above: `intent` is
 *     the technical key `kb_search` filters candidate entries by before
 *     scoring (ADR-005) — silently overwriting it from a free-text
 *     "title" field a Reviewer edited could make the approved entry
 *     unretrievable for its original intent, or retrievable for the
 *     wrong one. `section` is the human-facing heading `intent`
 *     conceptually is not, so that's what "editing the title" should
 *     mean.
 *   - `edited.keywords` -> `keywords` (direct). Closes a real bug: every
 *     candidate is queued with `candidate_keywords: []`
 *     (`EscalationResolutionFlow` never fills this in), and `kb_search`
 *     skips any entry with zero keywords outright — an un-edited Approve
 *     writes a live KB row that can never actually be retrieved by a
 *     guest, even though the write itself succeeds. The Edit UI
 *     (`ReviewQueueItem.tsx`) now has a keywords field specifically so a
 *     Reviewer can fix this before approving.
 */
export async function approveReviewQueueEntry(
  id: string,
  edited?: ReviewQueueDecisionInput,
): Promise<ReviewQueueEntry> {
  await apiFetch<KBEntryResponseDto>(`/review-queue/${id}/approve`, {
    method: "POST",
    body: JSON.stringify(
      edited
        ? { section: edited.title, content: edited.content, keywords: edited.keywords }
        : {},
    ),
  });
  const refreshed = await getReviewQueue();
  const updated = refreshed.find((entry) => entry.id === id);
  if (!updated) {
    // Should not happen (we just approved it) — surfaced as a real error
    // rather than silently fabricating a fallback entry (AC-003).
    throw new Error(`Approved review queue entry ${id} but could not find it in the refreshed queue`);
  }
  return updated;
}

/**
 * Real `POST /review-queue/{id}/reject`. The response (`{id, status}`) is
 * enough to confirm the action but not a full `ReviewQueueEntry`, so —
 * same reasoning as approve above — this re-fetches `GET /review-queue`
 * and returns the freshly mapped entry rather than hand-assembling one.
 */
export async function rejectReviewQueueEntry(id: string): Promise<ReviewQueueEntry> {
  await apiFetch(`/review-queue/${id}/reject`, { method: "POST" });
  const refreshed = await getReviewQueue();
  const updated = refreshed.find((entry) => entry.id === id);
  if (!updated) {
    throw new Error(`Rejected review queue entry ${id} but could not find it in the refreshed queue`);
  }
  return updated;
}

// ---------------------------------------------------------------------
// POST /escalations/{id}/resolve
// ---------------------------------------------------------------------

/** Raw shape of `POST /escalations/{id}/resolve`'s response (main.py `ResolveEscalationResponse`). */
interface ResolveEscalationResponseDto {
  status: string;
  review_queue_id: string;
}

/**
 * Real `POST /escalations/{id}/resolve` (main.py). `{id}` is an
 * `interaction_log` row id -- the same `id` field returned by
 * `getInteractions()` for an entry with `outcome === "escalated"` (see
 * `EscalationResolutionQueue.tsx`, which is the only caller). Writes a
 * candidate KB entry to `review_queue` with `status: "pending"`, linked
 * back to this interaction (`original_inquiry_id`); does NOT touch the
 * live KB -- that stays exclusively the Reviewer's Approve action in
 * `ReviewQueue.tsx`.
 *
 * The response only confirms `{status: "queued", review_queue_id}` -- not
 * a full `ReviewQueueEntry` -- so unlike `approveReviewQueueEntry`/
 * `rejectReviewQueueEntry` there is nothing to re-fetch-and-return here;
 * the caller re-fetches `getReviewQueue()`/`getInteractions()` itself
 * (via the `refreshToken` mechanism in `Ops.tsx`) to pick up the new
 * pending entry.
 */
export async function resolveEscalation(
  interactionId: string,
  resolutionText: string,
): Promise<{ reviewQueueId: string }> {
  const result = await apiFetch<ResolveEscalationResponseDto>(
    `/escalations/${interactionId}/resolve`,
    { method: "POST", body: JSON.stringify({ resolution_text: resolutionText }) },
  );
  return { reviewQueueId: result.review_queue_id };
}

// ---------------------------------------------------------------------
// GET /interactions/{id}/trace -> TraceEvent[]
// ---------------------------------------------------------------------

/**
 * Raw shape of one event in `GET /interactions/{id}/trace`'s `events`
 * array. `duration_ms`/`latency_pass`/`meets_target` (`*develop-fe`
 * per-step-latency follow-up, 2026-09-01, sad.md §7 NFR-002) are present
 * (non-null) only on `llm_call_completed`/`llm_call_failed`/
 * `tool_call_finished`/`tool_call_error` records — `null` on every other
 * event type, per `backend/src/app/main.py`'s `TraceEvent` model.
 */
interface TraceEventDto {
  timestamp: string;
  event: TraceEventType;
  task_name: string | null;
  agent_role: string | null;
  outcome: "success" | "failure" | null;
  detail: string | null;
  error: string | null;
  duration_ms: number | null;
  latency_pass: boolean | null;
  meets_target: boolean | null;
}

/** Raw shape of `GET /interactions/{id}/trace`'s response body. */
interface InteractionTraceDto {
  interaction_id: string;
  events: TraceEventDto[];
}

function toTraceEvent(row: TraceEventDto): TraceEvent {
  return {
    timestamp: Date.parse(row.timestamp),
    eventType: row.event,
    taskName: row.task_name,
    agentRole: row.agent_role,
    outcome: row.outcome,
    detail: row.detail,
    error: row.error,
    durationMs: row.duration_ms,
    latencyPass: row.latency_pass,
    meetsTarget: row.meets_target,
  };
}

/**
 * Real `GET /interactions/{id}/trace` call for the ops trace panel
 * (frontend.md §13). Events already arrive in chronological order from
 * the server — no client-side sort applied. A 404 (`error_code:
 * "interaction_not_found"`) surfaces as a thrown `ApiError` via
 * `apiFetch`, same as every other call in this module; the caller
 * (`InteractionTracePanel.tsx`) is what distinguishes that from the
 * valid "200 with an empty `events` array" case (an interaction that
 * failed before the reasoning Crew ever ran) — this function does not
 * collapse the two.
 */
export async function getInteractionTrace(interactionId: string): Promise<TraceEvent[]> {
  const body = await apiFetch<InteractionTraceDto>(`/interactions/${interactionId}/trace`);
  return body.events.map(toTraceEvent);
}
