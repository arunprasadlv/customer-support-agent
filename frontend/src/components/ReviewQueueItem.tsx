import { useState } from "react";
import type { ReviewQueueDecisionInput, ReviewQueueEntry } from "../types/ops";

interface ReviewQueueItemProps {
  entry: ReviewQueueEntry;
  busy: boolean;
  onApprove: (id: string, edited?: ReviewQueueDecisionInput) => void;
  onReject: (id: string) => void;
}

/**
 * One candidate KB entry: original query + proposed KB entry shown side
 * by side (sad.md SS3 line ~144), with Approve / Edit / Reject actions.
 *
 * Edit-endpoint ambiguity (see frontend.md SS10): there is no separate
 * edit API — Edit only toggles local editable fields; Approve submits
 * whatever the current draft is (edited or not) through the same
 * approve action. This mirrors `mockOpsData.ts`'s
 * `approveReviewQueueEntry(id, edited?)`.
 *
 * "Reviewer actions" is a labeled role framing only, not an
 * authentication gate — PRD confirms no real auth exists in MVP.
 */
export default function ReviewQueueItem({
  entry,
  busy,
  onApprove,
  onReject,
}: ReviewQueueItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState(entry.proposedTitle);
  const [draftContent, setDraftContent] = useState(entry.proposedContent);
  // Comma-separated text, not a tag-input widget — simplest control that
  // still lets a Reviewer supply a real string[] on submit. Almost always
  // starts empty (EscalationResolutionFlow never fills candidate_keywords
  // in), which is exactly the retrievability gap this field exists to fix.
  const [draftKeywords, setDraftKeywords] = useState(entry.keywords.join(", "));

  // Short, human-readable label used to disambiguate this item's
  // buttons from every other item's identically-worded Approve/Edit/
  // Reject buttons (screen-reader users navigate the button list, not
  // the visual layout).
  const itemLabel =
    entry.proposedTitle.length > 60
      ? `${entry.proposedTitle.slice(0, 60)}…`
      : entry.proposedTitle;

  function handleEditToggle() {
    if (isEditing) {
      // Cancel: discard the in-progress draft, revert to the stored values.
      setDraftTitle(entry.proposedTitle);
      setDraftContent(entry.proposedContent);
      setDraftKeywords(entry.keywords.join(", "));
    }
    setIsEditing((prev) => !prev);
  }

  function parseDraftKeywords(): string[] {
    return draftKeywords
      .split(",")
      .map((keyword) => keyword.trim())
      .filter((keyword) => keyword.length > 0);
  }

  function handleApprove() {
    onApprove(
      entry.id,
      isEditing
        ? { title: draftTitle.trim(), content: draftContent.trim(), keywords: parseDraftKeywords() }
        : undefined,
    );
  }

  return (
    <li className="review-item">
      <div className="review-item__columns">
        <div className="review-item__column">
          <h3 className="review-item__column-heading">Original query</h3>
          <p className="review-item__original-query">{entry.originalQuery}</p>
        </div>

        <div className="review-item__column">
          <h3 className="review-item__column-heading">Proposed KB entry</h3>
          {isEditing ? (
            <div className="review-item__edit-fields">
              <div className="review-item__field">
                <label htmlFor={`rq-title-${entry.id}`}>Entry title</label>
                <input
                  id={`rq-title-${entry.id}`}
                  type="text"
                  value={draftTitle}
                  onChange={(event) => setDraftTitle(event.target.value)}
                  disabled={busy}
                />
              </div>
              <div className="review-item__field">
                <label htmlFor={`rq-content-${entry.id}`}>Entry content</label>
                <textarea
                  id={`rq-content-${entry.id}`}
                  value={draftContent}
                  onChange={(event) => setDraftContent(event.target.value)}
                  rows={4}
                  disabled={busy}
                />
              </div>
              <div className="review-item__field">
                <label htmlFor={`rq-keywords-${entry.id}`}>Keywords (comma-separated)</label>
                <input
                  id={`rq-keywords-${entry.id}`}
                  type="text"
                  value={draftKeywords}
                  onChange={(event) => setDraftKeywords(event.target.value)}
                  placeholder="e.g. towels, housekeeping, minibar"
                  disabled={busy}
                />
                <p className="review-item__field-hint">
                  This entry can only be found later if at least one keyword here matches a
                  guest's wording — entries approved with no keywords can never be retrieved.
                </p>
              </div>
            </div>
          ) : (
            <>
              <p className="review-item__proposed-title">{entry.proposedTitle}</p>
              <p className="review-item__proposed-content">{entry.proposedContent}</p>
              {entry.keywords.length === 0 ? (
                <p className="review-item__no-keywords-warning">
                  No keywords set — this entry will not be retrievable if approved as-is. Use
                  Edit to add some first.
                </p>
              ) : (
                <p className="review-item__keywords">Keywords: {entry.keywords.join(", ")}</p>
              )}
            </>
          )}
        </div>
      </div>

      <fieldset className="review-item__actions" disabled={busy}>
        <legend>Reviewer actions</legend>
        <button
          type="button"
          className="review-item__edit-btn"
          onClick={handleEditToggle}
          aria-label={`${isEditing ? "Cancel edit of" : "Edit"} candidate KB entry: ${itemLabel}`}
        >
          {isEditing ? "Cancel Edit" : "Edit"}
        </button>
        <button
          type="button"
          className="review-item__approve-btn"
          onClick={handleApprove}
          aria-label={
            isEditing
              ? `Approve edited candidate KB entry: ${itemLabel}`
              : `Approve candidate KB entry: ${itemLabel}`
          }
        >
          Approve
        </button>
        <button
          type="button"
          className="review-item__reject-btn"
          onClick={() => onReject(entry.id)}
          aria-label={`Reject candidate KB entry: ${itemLabel}`}
        >
          Reject
        </button>
      </fieldset>
    </li>
  );
}
