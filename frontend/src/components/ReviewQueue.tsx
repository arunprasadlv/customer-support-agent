import { useEffect, useState } from "react";
import {
  approveReviewQueueEntry,
  getReviewQueue,
  rejectReviewQueueEntry,
} from "../lib/mockOpsData";
import type { ReviewQueueDecisionInput, ReviewQueueEntry } from "../types/ops";
import ReviewQueueItem from "./ReviewQueueItem";

interface ReviewQueueProps {
  /** Bumped by `Ops.tsx` whenever an escalation resolution is submitted
   * from `EscalationResolutionQueue` (frontend.md §11), so this component
   * refetches and picks up the newly-queued candidate entry without a
   * manual page reload. Optional so this component's own default/
   * first-mount behavior is unchanged if a caller doesn't pass it. */
  refreshToken?: number;
}

/**
 * KB review queue (sad.md SS3 line ~144, PRD FR-014/NFR-008, AC-010/
 * AC-011) — the sole path that can mutate the live knowledge base.
 * Owns all queue state locally; the only integration points with a
 * future real backend are `getReviewQueue`/`approveReviewQueueEntry`/
 * `rejectReviewQueueEntry` (lib/mockOpsData.ts) — `@integration.eng`
 * swaps those for real `GET`/`POST` calls without touching this
 * component or ReviewQueueItem.
 */
export default function ReviewQueue({ refreshToken }: ReviewQueueProps) {
  const [entries, setEntries] = useState<ReviewQueueEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    getReviewQueue()
      .then((data) => {
        if (!cancelled) {
          setEntries(data);
          setIsLoading(false);
        }
      })
      .catch((error: unknown) => {
        // `@integration.eng`'s `*integrate-api`/`*verify-messageflow`
        // addition: `getReviewQueue` now hits a real backend and can
        // reject. Reuses the existing `role="status" aria-live="polite"`
        // paragraph below (previously only used for approve/reject
        // confirmations) rather than a new error component — same
        // "surface it, don't build new error UI" approach as
        // InteractionLog.tsx.
        if (!cancelled) {
          console.error("getReviewQueue failed", error);
          setStatusMessage(
            `Could not load the review queue: ${
              error instanceof Error ? error.message : "unknown error"
            }`,
          );
          setIsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [refreshToken]);

  const pending = entries.filter((entry) => entry.status === "pending");
  const decided = entries
    .filter((entry) => entry.status !== "pending")
    .sort((a, b) => (b.decidedAt ?? 0) - (a.decidedAt ?? 0))
    .slice(0, 5);

  async function handleApprove(id: string, edited?: ReviewQueueDecisionInput) {
    setBusyId(id);
    try {
      const updated = await approveReviewQueueEntry(id, edited);
      setEntries((prev) => prev.map((entry) => (entry.id === id ? updated : entry)));
      setStatusMessage(
        `Approved: "${updated.proposedTitle}" added to the knowledge base${
          edited ? " with your edits" : ""
        }.`,
      );
    } catch (error: unknown) {
      // Real backend can 404/409/422 here (already-actioned entry,
      // missing intent/content, etc. — see main.py). Surfaced via the
      // same status paragraph used for success confirmations above,
      // rather than a new error UI, so the failure is visible instead of
      // an unhandled rejection.
      console.error("approveReviewQueueEntry failed", error);
      setStatusMessage(
        `Could not approve this entry: ${error instanceof Error ? error.message : "unknown error"}`,
      );
    } finally {
      setBusyId(null);
    }
  }

  async function handleReject(id: string) {
    setBusyId(id);
    try {
      const updated = await rejectReviewQueueEntry(id);
      setEntries((prev) => prev.map((entry) => (entry.id === id ? updated : entry)));
      setStatusMessage(`Rejected: "${updated.proposedTitle}" discarded — knowledge base unchanged.`);
    } catch (error: unknown) {
      console.error("rejectReviewQueueEntry failed", error);
      setStatusMessage(
        `Could not reject this entry: ${error instanceof Error ? error.message : "unknown error"}`,
      );
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="review-queue">
      <p className="review-queue__role-note">
        The actions below are restricted to the <strong>Reviewer</strong> role. The MVP has no
        real authentication (PRD — Out of Scope); this is a labeled role framing, not an
        enforced access gate.
      </p>

      {/* SC 4.1.3 Status Messages — polite confirmation of an action's
          outcome, present in the DOM from first render so assistive
          tech picks up later text changes. */}
      <p role="status" aria-live="polite" className="review-queue__status">
        {statusMessage}
      </p>

      {isLoading && <p>Loading review queue…</p>}

      {!isLoading && pending.length === 0 && (
        <p className="review-queue__empty">No candidate KB entries awaiting review.</p>
      )}

      {pending.length > 0 && (
        <ul className="review-queue__list">
          {pending.map((entry) => (
            <ReviewQueueItem
              key={entry.id}
              entry={entry}
              busy={busyId === entry.id}
              onApprove={handleApprove}
              onReject={handleReject}
            />
          ))}
        </ul>
      )}

      {decided.length > 0 && (
        <div className="review-queue__decided">
          <h3>Recently decided</h3>
          <ul>
            {decided.map((entry) => (
              <li key={entry.id}>
                <span aria-hidden="true">{entry.status === "approved" ? "✓" : "✕"}</span>{" "}
                {entry.status === "approved" ? "Approved" : "Rejected"}: {entry.proposedTitle}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
