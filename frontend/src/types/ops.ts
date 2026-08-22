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
  status: ReviewQueueStatus;
  /** Set once a decision (approve/reject) has been recorded. */
  decidedAt?: number;
}

/** Payload for an Approve action — edited content if the Reviewer used Edit first. */
export interface ReviewQueueDecisionInput {
  title: string;
  content: string;
}
