import type { ChatMessage } from "../types/chat";
import BotAvatar from "./BotAvatar";

interface MessageBubbleProps {
  message: ChatMessage;
}

/**
 * Renders a single normal (non-escalation) chat message as a bubble.
 * Escalation messages are rendered by EscalationNotice instead — see
 * ChatWindow's render branch (sad.md SS3: escalation must be visually
 * distinct from a normal answer, PRD AC-003).
 */
export default function MessageBubble({ message }: MessageBubbleProps) {
  const isGuest = message.role === "guest";
  return (
    <div className={`chat-row ${isGuest ? "chat-row--guest" : "chat-row--assistant"}`}>
      {!isGuest && <BotAvatar />}
      <div className={`chat-bubble ${isGuest ? "chat-bubble--guest" : "chat-bubble--assistant"}`}>
        <p>{message.text}</p>
        <span className="chat-bubble__meta">
          {isGuest ? "You" : "Support Assistant"} ·{" "}
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>
    </div>
  );
}
