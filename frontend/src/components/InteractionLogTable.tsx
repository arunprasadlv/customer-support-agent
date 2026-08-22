import type { InteractionLogEntry } from "../types/ops";

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
 */
export default function InteractionLogTable({ entries }: InteractionLogTableProps) {
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
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.id}>
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
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
