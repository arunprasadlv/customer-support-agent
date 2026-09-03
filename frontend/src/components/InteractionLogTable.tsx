import { Fragment, useState } from "react";
import type { InteractionLogEntry } from "../types/ops";
import InteractionTracePanel from "./InteractionTracePanel";

interface InteractionLogTableProps {
  entries: InteractionLogEntry[];
}

/**
 * Read-only interaction log (sad.md SS3 "per-interaction detail ...
 * supporting explainability", PRD NFR-003). Real `<table>` markup with
 * `<th scope="col">` headers — this is genuinely tabular data (one row
 * per processed inquiry), not a card/div grid, per the Robust/semantic
 * HTML bar already applied to /chat and /inbox.
 *
 * Outcome and PII-redaction columns use an icon + text label, never
 * color alone (mirrors /chat's EscalationNotice pattern).
 *
 * Trace column (frontend.md §13): a "View Trace" toggle per row, an
 * inline expand-in-place disclosure rather than a modal (`aamad.config
 * .yml ui.prefer_modals: false`). Expanding a row renders a second
 * `<tr>` directly below it (spanning every column) containing
 * `InteractionTracePanel`, which owns its own lazy fetch — only rows
 * currently expanded ever call `GET /interactions/{id}/trace`, never
 * all rows up front. `expandedIds` is a `Set` (not a single id) so more
 * than one row's trace can be open at once, same as this table having
 * no other single-selection constraint.
 */
export default function InteractionLogTable({ entries }: InteractionLogTableProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  function toggleExpanded(id: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  return (
    <div className="ops-table-wrapper">
      <table className="ops-table">
        <caption className="ops-table__caption">
          Interaction log — one row per processed guest inquiry, across chat and email, showing
          classification, sentiment, PII-redaction status, and outcome for traceability.
        </caption>
        <thead>
          <tr>
            <th scope="col">Time</th>
            <th scope="col">Channel</th>
            <th scope="col">Query</th>
            <th scope="col">Classification</th>
            <th scope="col">Sentiment</th>
            <th scope="col">PII Redacted</th>
            <th scope="col">Outcome</th>
            <th scope="col">Trace</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => {
            const isExpanded = expandedIds.has(entry.id);
            const queryLabel =
              entry.query.length > 60 ? `${entry.query.slice(0, 60)}…` : entry.query;
            const tracePanelId = `interaction-trace-${entry.id}`;
            return (
              <Fragment key={entry.id}>
                <tr>
                  <td>
                    {new Date(entry.timestamp).toLocaleString([], {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </td>
                  <td>{entry.channel === "chat" ? "Chat" : "Email"}</td>
                  <td>{entry.query}</td>
                  <td>{entry.classification}</td>
                  <td>
                    {entry.sentimentScore.toFixed(2)} ({entry.sentimentLabel})
                  </td>
                  <td>
                    {entry.piiRedacted ? (
                      <span className="ops-indicator">
                        <span aria-hidden="true">✓</span> Redacted
                      </span>
                    ) : (
                      <span className="ops-indicator">
                        <span aria-hidden="true">—</span> None detected
                      </span>
                    )}
                  </td>
                  <td>
                    {entry.outcome === "escalated" ? (
                      <span className="ops-indicator ops-indicator--escalated">
                        <span aria-hidden="true">⚠</span> Escalated
                      </span>
                    ) : (
                      <span className="ops-indicator">
                        <span aria-hidden="true">✓</span> Resolved
                      </span>
                    )}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="ops-table__trace-toggle"
                      aria-expanded={isExpanded}
                      aria-controls={tracePanelId}
                      onClick={() => toggleExpanded(entry.id)}
                    >
                      {isExpanded ? "Hide Trace" : "View Trace"}
                      <span className="sr-only"> for: {queryLabel}</span>
                    </button>
                  </td>
                </tr>
                {isExpanded && (
                  <tr className="ops-table__trace-row">
                    <td colSpan={8} id={tracePanelId}>
                      <InteractionTracePanel interactionId={entry.id} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
