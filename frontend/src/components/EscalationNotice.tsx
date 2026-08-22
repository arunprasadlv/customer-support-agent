import type { ChatMessage } from "../types/chat";
import BotAvatar from "./BotAvatar";

interface EscalationNoticeProps {
  message: ChatMessage;
}

/**
 * Distinct visual treatment for a simulated escalation (sad.md SS3,
 * PRD AC-003): must be unmistakable from a normal answer and must
 * honestly state that a human hand-off is being simulated — never a
 * silently fabricated resolution.
 */
export default function EscalationNotice({ message }: EscalationNoticeProps) {
  return (
    <div className="chat-row chat-row--assistant">
      <BotAvatar />
      <div className="escalation-notice" role="alert">
        <div className="escalation-notice__header">
          <span aria-hidden="true">⚠️</span>
          <strong>Escalated — a human is being looped in (simulated)</strong>
        </div>
        <p>{message.text}</p>
        <span className="chat-bubble__meta">
          Support Assistant ·{" "}
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>
    </div>
  );
}
