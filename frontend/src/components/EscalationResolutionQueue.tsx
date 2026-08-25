import { useEffect, useState } from "react";
import { getInteractions, getReviewQueue, resolveEscalation } from "../lib/mockOpsData";
import type { InteractionLogEntry } from "../types/ops";

interface EscalationResolutionQueueProps {
  /** Bumped by `Ops.tsx` whenever another section's action should trigger
   * a refetch here too (e.g. an approve/reject elsewhere doesn't change
   * the needs-resolution set, but a resolve submitted from *this*
   * component's own `onResolved` callback does change the KB Review
   * Queue's set — see the module doc comment below). */
  refreshToken: number;
  /** Called after a resolution is successfully submitted, so `Ops.tsx`
   * can bump its own `refreshToken` and cause `ReviewQueue.tsx` (and this
   * component) to refetch and pick up the newly-queued candidate. */
  onResolved: () => void;
}

interface DraftState {
  text: string;
  submitting: boolean;
  error: string | null;
}

/**
 * "Escalated — Needs Resolution" queue (frontend.md §11). Closes the gap
 * between an escalated `interaction_log` row and the KB Review Queue: a
 * human writes a resolution here, which calls the real
 * `POST /escalations/{id}/resolve` and queues a candidate KB entry for
 * `ReviewQueue.tsx` to Approve/Edit/Reject.
 *
 * "Needs resolution" is computed client-side (§11 judgment call): an
 * interaction qualifies iff `outcome === "escalated"` AND no
 * review-queue entry exists with `sourceInteractionId` equal to that
 * interaction's `id` (regardless of that entry's status -- pending,
 * approved, or rejected all count as "already handled," since a
 * resolution was already submitted for it once). This is why both
 * `getInteractions()` and `getReviewQueue()` are fetched here rather
 * than adding a new backend query.
 */
export default function EscalationResolutionQueue({
  refreshToken,
  onResolved,
}: EscalationResolutionQueueProps) {
  const [needsResolution, setNeedsResolution] = useState<InteractionLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, DraftState>>({});
  const [confirmedMessage, setConfirmedMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setLoadError(null);
    Promise.all([getInteractions(), getReviewQueue()])
      .then(([interactions, reviewQueue]) => {
        if (cancelled) return;
        const resolvedInteractionIds = new Set(reviewQueue.map((entry) => entry.sourceInteractionId));
        const escalatedUnresolved = interactions.filter(
          (entry) => entry.outcome === "escalated" && !resolvedInteractionIds.has(entry.id),
        );
        setNeedsResolution(escalatedUnresolved);
        setIsLoading(false);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        console.error("EscalationResolutionQueue load failed", error);
        setLoadError(
          error instanceof Error
            ? error.message
            : "Could not load escalated interactions awaiting resolution.",
        );
        setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshToken]);

  function getDraft(id: string): DraftState {
    return drafts[id] ?? { text: "", submitting: false, error: null };
  }

  function setDraftText(id: string, text: string) {
    setDrafts((prev) => ({ ...prev, [id]: { ...getDraft(id), text } }));
  }

  async function handleSubmit(entry: InteractionLogEntry) {
    const draft = getDraft(entry.id);
    const trimmed = draft.text.trim();
    if (!trimmed) return;

    setDrafts((prev) => ({ ...prev, [entry.id]: { ...draft, submitting: true, error: null } }));
    try {
      await resolveEscalation(entry.id, trimmed);
      setConfirmedMessage(
        `Resolution submitted for "${excerpt(entry.query)}" — now awaiting Reviewer decision in the KB Review Queue.`,
      );
      setNeedsResolution((prev) => prev.filter((item) => item.id !== entry.id));
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[entry.id];
        return next;
      });
      onResolved();
    } catch (error: unknown) {
      console.error("resolveEscalation failed", error);
      setDrafts((prev) => ({
        ...prev,
        [entry.id]: {
          ...getDraft(entry.id),
          submitting: false,
          error: error instanceof Error ? error.message : "Could not submit this resolution.",
        },
      }));
    }
  }

  if (isLoading) {
    return <p>Loading escalated interactions…</p>;
  }

  if (loadError) {
    return (
      <p role="alert">Could not load escalated interactions awaiting resolution: {loadError}</p>
    );
  }

  return (
    <div className="escalation-queue">
      {/* SC 4.1.3 Status Messages -- present from first render, same
          role="status" aria-live="polite" pattern as ReviewQueue.tsx's
          confirmation paragraph. */}
      <p role="status" aria-live="polite" className="escalation-queue__status">
        {confirmedMessage}
      </p>

      {needsResolution.length === 0 && (
        <p className="escalation-queue__empty">No escalated interactions awaiting resolution.</p>
      )}

      {needsResolution.length > 0 && (
        <ul className="escalation-queue__list">
          {needsResolution.map((entry) => {
            const draft = getDraft(entry.id);
            const label = excerpt(entry.query);
            const textareaId = `escalation-resolution-${entry.id}`;
            return (
              <li key={entry.id} className="escalation-item">
                <h3 className="escalation-item__column-heading">Original query</h3>
                <p className="escalation-item__original-query">{entry.query}</p>

                <fieldset className="escalation-item__actions" disabled={draft.submitting}>
                  <legend>Resolution</legend>
                  <div className="escalation-item__field">
                    <label htmlFor={textareaId}>Resolution text</label>
                    <textarea
                      id={textareaId}
                      value={draft.text}
                      onChange={(event) => setDraftText(entry.id, event.target.value)}
                      rows={4}
                      placeholder="Describe how this inquiry was resolved…"
                    />
                  </div>
                  <button
                    type="button"
                    className="escalation-item__submit-btn"
                    onClick={() => handleSubmit(entry)}
                    disabled={!draft.text.trim()}
                    aria-label={`Submit resolution for: ${label}`}
                  >
                    Submit Resolution
                  </button>
                </fieldset>

                {draft.error && (
                  <p role="alert" className="escalation-item__error">
                    Could not submit this resolution: {draft.error}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

/** Short, human-readable excerpt used to disambiguate this item's Submit
 * button from every other item's identically-worded button (screen-reader
 * users navigate the button list, not the visual layout) -- same
 * disambiguation pattern as ReviewQueueItem.tsx's `itemLabel`. */
function excerpt(text: string): string {
  return text.length > 60 ? `${text.slice(0, 60)}…` : text;
}
