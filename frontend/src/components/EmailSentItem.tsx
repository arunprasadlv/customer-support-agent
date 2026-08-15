import type { EmailThreadEntry } from "../types/email";

interface EmailSentItemProps {
  entry: EmailThreadEntry;
}

/**
 * Renders a guest's outbound "sent" email in the thread. Right-aligned
 * to visually echo the guest side of /chat's bubble layout, but shaped
 * like an email (from/subject/body) rather than a chat bubble — an
 * inbox thread is a different content shape by design (see frontend.md
 * for the sad.md-driven rationale).
 */
export default function EmailSentItem({ entry }: EmailSentItemProps) {
  return (
    <div className="email-item email-item--sent">
      <div className="email-item__header">
        <span className="email-item__label">Sent</span>
        <span className="email-item__meta">
          {entry.from} ·{" "}
          {new Date(entry.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>
      <p className="email-item__subject">{entry.subject}</p>
      <p className="email-item__body">{entry.body}</p>
    </div>
  );
}
