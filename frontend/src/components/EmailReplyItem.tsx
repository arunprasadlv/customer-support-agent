import type { EmailThreadEntry } from "../types/email";

interface EmailReplyItemProps {
  entry: EmailThreadEntry;
}

/**
 * Renders a normal (non-escalation) reply in the email thread.
 * Escalated replies are rendered by EmailEscalationNotice instead — see
 * EmailInbox's render branch (sad.md SS3: escalation must be visually
 * distinct from a normal answer, PRD AC-003, same bar as /chat).
 */
export default function EmailReplyItem({ entry }: EmailReplyItemProps) {
  return (
    <div className="email-item email-item--reply">
      <div className="email-item__header">
        <span className="email-item__label">Reply</span>
        <span className="email-item__meta">
          Support Team ·{" "}
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
