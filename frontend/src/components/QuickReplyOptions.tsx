import type { ChatMessage } from "../types/chat";
import BotAvatar from "./BotAvatar";

interface QuickReplyOptionsProps {
  message: ChatMessage;
}

/**
 * Renders an assistant message that offers clickable pill/chip quick
 * replies instead of (or alongside) plain text — reuses the same
 * `chat-row`/`BotAvatar` shell as `MessageBubble` so it reads as "the
 * assistant sent you some options," with `message.text` as a short intro
 * line plus a labeled button group in place of a lone `<p>`.
 *
 * Deliberately generic: every option already carries its own `onSelect`
 * closure (baked in by `ChatWindow` — see `types/chat.ts`), so this
 * component has no knowledge of "category" vs. "common question"
 * semantics and needs no branching to serve both steps of the
 * taxonomy -> common-questions quick-reply flow (frontend.md §12).
 */
export default function QuickReplyOptions({ message }: QuickReplyOptionsProps) {
  const options = message.options ?? [];
  return (
    <div className="chat-row chat-row--assistant">
      <BotAvatar />
      <div className="chat-bubble chat-bubble--assistant chat-bubble--options">
        <p>{message.text}</p>
        <div
          className="quick-reply-group"
          role="group"
          aria-label={message.optionsGroupLabel ?? "Options"}
        >
          {options.map((option) => (
            <button
              key={option.id}
              type="button"
              className="quick-reply-chip"
              onClick={option.onSelect}
            >
              {option.label}
            </button>
          ))}
        </div>
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
