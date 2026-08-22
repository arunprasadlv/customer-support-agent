import type { EmailThreadEntry } from "../types/email";

interface EmailEscalationNoticeProps {
  entry: EmailThreadEntry;
}

/**
 * Distinct visual treatment for a simulated escalation reply, mirroring
 * /chat's EscalationNotice (sad.md SS3, PRD AC-003): must be
 * unmistakable from a normal reply and must honestly state that a
 * human hand-off is being simulated — never a silently fabricated
 * resolution. Reuses the same verified-safe amber tokens as /chat's
 * EscalationNotice (#b45f18 border/accent on #fff4e5, #6b3d00 text) —
 * see frontend.md SS8/SS9 for the computed contrast ratios; nothing new
 * introduced here.
 */
export default function EmailEscalationNotice({ entry }: EmailEscalationNoticeProps) {
  return (
    <div className="email-item email-escalation" role="alert">
      <div className="email-escalation__header">
        <span aria-hidden="true">⚠️</span>
        <strong>Escalated — a human is being looped in (simulated)</strong>
      </div>
      <p className="email-item__subject">{entry.subject}</p>
      <p className="email-item__body">{entry.body}</p>
      <span className="email-item__meta">
        Support Team ·{" "}
        {new Date(entry.timestamp).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })}
      </span>
    </div>
  );
}
