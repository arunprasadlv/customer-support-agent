import { useState } from "react";
import type { FormEvent } from "react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled: boolean;
}

/**
 * Free-text message input + send control (sad.md SS3 "guest chat
 * widget"; PRD NFR-001 usable without instructions).
 */
export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  }

  return (
    <form className="chat-input" onSubmit={handleSubmit}>
      <label htmlFor="chat-message-input" className="sr-only">
        Type your message
      </label>
      <input
        id="chat-message-input"
        type="text"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Describe your reservation, billing, amenity, or other request…"
        disabled={disabled}
        autoComplete="off"
      />
      <button type="submit" disabled={disabled || !value.trim()}>
        Send
      </button>
    </form>
  );
}
