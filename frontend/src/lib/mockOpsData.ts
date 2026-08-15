import type {
  InteractionLogEntry,
  ReviewQueueDecisionInput,
  ReviewQueueEntry,
} from "../types/ops";

/**
 * MOCK ONLY — do not treat as production logic.
 *
 * Stands in for the future ops-view backend contract (sad.md SS4):
 *   - `GET /interactions`                      -> getInteractions()
 *   - `GET /review-queue`                      -> getReviewQueue()
 *   - `POST /review-queue/{id}/approve`        -> approveReviewQueueEntry(id, edited?)
 *   - `POST /review-queue/{id}/reject`         -> rejectReviewQueueEntry(id)
 *
 * `@integration.eng`'s `*integrate-api` is the intended swap point:
 * replace each function body with a real `fetch()` call against
 * `VITE_API_BASE_URL` (see frontend/.env.example) — signatures and
 * return shapes already match the real contract, so no component needs
 * to change when the swap happens.
 *
 * Per @frontend.eng's persona Workflow Notes, this file must NOT call a
 * real backend endpoint. Kept fully independent from
 * `mockInquiryClient.ts`/`mockEmailClient.ts` — no shared imports.
 *
 * Edit-endpoint ambiguity (see frontend.md SS10 for the full writeup):
 * sad.md's endpoint list only names approve/reject — no separate edit
 * endpoint. Resolved here as: editing is purely client-side state
 * (ReviewQueueItem's local title/content draft); "Edit then Approve"
 * calls this same `approveReviewQueueEntry`, passing the edited
 * title/content as `edited`, which overwrites the stored proposed entry
 * before marking it approved. No PATCH/edit endpoint is modeled.
 */

const MOCK_LATENCY_MS = 500;

const interactions: InteractionLogEntry[] = [
  {
    id: "int-001",
    timestamp: Date.parse("2026-08-12T09:14:00Z"),
    channel: "chat",
    query: "What time is check-in for my reservation under [REDACTED_NAME]?",
    classification: "Reservations & Booking",
    sentimentScore: 0.1,
    sentimentLabel: "Neutral",
    piiRedacted: true,
    outcome: "resolved",
  },
  {
    id: "int-002",
    timestamp: Date.parse("2026-08-12T10:02:00Z"),
    channel: "email",
    query: "Can I get a breakdown of the charges on my folio? Card ending [REDACTED_CARD].",
    classification: "Billing & Folio",
    sentimentScore: -0.2,
    sentimentLabel: "Neutral",
    piiRedacted: true,
    outcome: "resolved",
  },
  {
    id: "int-003",
    timestamp: Date.parse("2026-08-12T11:47:00Z"),
    channel: "chat",
    query: "This is the SECOND time housekeeping skipped our room. Totally unacceptable.",
    classification: "General Complaint",
    sentimentScore: -0.85,
    sentimentLabel: "Negative",
    piiRedacted: false,
    outcome: "escalated",
  },
  {
    id: "int-004",
    timestamp: Date.parse("2026-08-12T13:20:00Z"),
    channel: "email",
    query: "Is the spa open on Sundays? Would like to book a couples massage.",
    classification: "Room Service & Amenities",
    sentimentScore: 0.4,
    sentimentLabel: "Positive",
    piiRedacted: false,
    outcome: "resolved",
  },
  {
    id: "int-005",
    timestamp: Date.parse("2026-08-12T14:55:00Z"),
    channel: "chat",
    query:
      "I was double-charged for my stay and nobody will explain why. I want to speak to a manager.",
    classification: "Billing & Folio",
    sentimentScore: -0.7,
    sentimentLabel: "Negative",
    piiRedacted: false,
    outcome: "escalated",
  },
  {
    id: "int-006",
    timestamp: Date.parse("2026-08-12T16:10:00Z"),
    channel: "chat",
    query: "Do you have a late check-out option? Contact me at [REDACTED_EMAIL] if extra fees apply.",
    classification: "Reservations & Booking",
    sentimentScore: 0.05,
    sentimentLabel: "Neutral",
    piiRedacted: true,
    outcome: "resolved",
  },
];

let reviewQueue: ReviewQueueEntry[] = [
  {
    id: "rq-001",
    sourceInteractionId: "int-003",
    originalQuery: "This is the SECOND time housekeeping skipped our room. Totally unacceptable.",
    proposedTitle: "Repeated missed housekeeping — resolution steps",
    proposedContent:
      "When a guest reports housekeeping was missed more than once, apologize, offer same-day " +
      "priority service, and credit one complimentary amenity (e.g. late check-out or a drink " +
      "voucher) as goodwill. Escalate to the floor supervisor if it recurs a third time.",
    status: "pending",
  },
  {
    id: "rq-002",
    sourceInteractionId: "int-005",
    originalQuery:
      "I was double-charged for my stay and nobody will explain why. I want to speak to a manager.",
    proposedTitle: "Duplicate charge dispute — resolution steps",
    proposedContent:
      "Verify the folio against the payment processor log. If a duplicate authorization is " +
      "confirmed, issue an immediate reversal (not just a refund promise) and email the guest a " +
      "corrected folio within 24 hours. Duplicate charges are a billing-system reconciliation " +
      "issue, not guest error.",
    status: "pending",
  },
  {
    id: "rq-003",
    sourceInteractionId: "int-007",
    originalQuery: "Pool was closed for maintenance with no signage or notice — very frustrating.",
    proposedTitle: "Unannounced amenity closure — resolution steps",
    proposedContent:
      "Post signage at the amenity and the front desk at least 2 hours before any planned " +
      "closure. If a guest is affected by an unannounced closure, offer a comparable amenity " +
      "credit for the stay.",
    status: "pending",
  },
];

function delay<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), MOCK_LATENCY_MS));
}

/** Mirrors `GET /interactions` (sad.md SS4) for the ops interaction log. */
export function getInteractions(): Promise<InteractionLogEntry[]> {
  return delay([...interactions]);
}

/** Mirrors `GET /review-queue` (sad.md SS4) for the KB review queue. */
export function getReviewQueue(): Promise<ReviewQueueEntry[]> {
  return delay([...reviewQueue]);
}

/**
 * Mirrors `POST /review-queue/{id}/approve`. When `edited` is supplied
 * (Reviewer used Edit before Approve), the edited title/content
 * overwrite the stored proposed entry as part of the same commit — see
 * the edit-endpoint ambiguity note above.
 */
export function approveReviewQueueEntry(
  id: string,
  edited?: ReviewQueueDecisionInput,
): Promise<ReviewQueueEntry> {
  reviewQueue = reviewQueue.map((entry) =>
    entry.id === id
      ? {
          ...entry,
          proposedTitle: edited?.title ?? entry.proposedTitle,
          proposedContent: edited?.content ?? entry.proposedContent,
          status: "approved",
          decidedAt: Date.now(),
        }
      : entry,
  );
  const updated = reviewQueue.find((entry) => entry.id === id);
  if (!updated) {
    return Promise.reject(new Error(`Review queue entry not found: ${id}`));
  }
  return delay(updated);
}

/** Mirrors `POST /review-queue/{id}/reject`. Discards the candidate — live KB is unchanged. */
export function rejectReviewQueueEntry(id: string): Promise<ReviewQueueEntry> {
  reviewQueue = reviewQueue.map((entry) =>
    entry.id === id ? { ...entry, status: "rejected", decidedAt: Date.now() } : entry,
  );
  const updated = reviewQueue.find((entry) => entry.id === id);
  if (!updated) {
    return Promise.reject(new Error(`Review queue entry not found: ${id}`));
  }
  return delay(updated);
}
