import { apiFetch } from "./apiClient";
import type {
  InteractionLogEntry,
  ReviewQueueDecisionInput,
  ReviewQueueEntry,
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
 * `edited` (title/content) maps onto the approve request body's
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
 *     mean. `keywords` is left unset (falls back to the stored
 *     `candidate_keywords`) — the Edit UI (`ReviewQueueItem.tsx`) has no
 *     keywords field to edit, so there's nothing to map; this does mean
 *     a Reviewer using Edit still can't fix the
 *     always-empty-`candidate_keywords` retrievability gap main.py's
 *     `ApproveReviewQueueRequest` docstring calls out — flagged as an
 *     Open Question in integration.md, not silently worked around by
 *     inventing a keywords UI (out of scope, no new UI this run).
 */
export async function approveReviewQueueEntry(
  id: string,
  edited?: ReviewQueueDecisionInput,
): Promise<ReviewQueueEntry> {
  await apiFetch<KBEntryResponseDto>(`/review-queue/${id}/approve`, {
    method: "POST",
    body: JSON.stringify(
      edited
        ? { section: edited.title, content: edited.content }
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
