import { useEffect, useRef, useState } from "react";
import { sendInquiry } from "../lib/mockInquiryClient";
import type { ChatMessage } from "../types/chat";
import ChatInput from "./ChatInput";
import EscalationNotice from "./EscalationNotice";
import LoadingIndicator from "./LoadingIndicator";
import MessageBubble from "./MessageBubble";

const WELCOME_MESSAGE: ChatMessage = {
  id: "welcome",
  role: "assistant",
  kind: "text",
  text:
    "Hi, I'm the hotel support assistant. Ask me about a reservation, your bill, amenities, " +
    "or anything else — I'll do my best to help, and I'll loop in a human if something needs " +
    "escalation.",
  timestamp: Date.now(),
};

function createId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/**
 * Guest chat widget — primary interaction surface (sad.md SS3, PRD
 * NFR-001). Owns all chat state locally (message list, loading state).
 * The only integration point with a future real backend is
 * `sendInquiry` (lib/mockInquiryClient.ts) — `@integration.eng` swaps
 * that one function for a real `POST /chat` call without needing to
 * touch this component or its children.
 */
export default function ChatWindow() {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);
  const [isLoading, setIsLoading] = useState(false);
  const scrollAnchorRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // Operable: respect prefers-reduced-motion for auto-scroll.
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    scrollAnchorRef.current?.scrollIntoView({
      behavior: prefersReducedMotion ? "auto" : "smooth",
    });
  }, [messages, isLoading]);

  async function handleSend(text: string) {
    const guestMessage: ChatMessage = {
      id: createId(),
      role: "guest",
      kind: "text",
      text,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, guestMessage]);
    setIsLoading(true);

    try {
      const result = await sendInquiry(text);
      const assistantMessage: ChatMessage = {
        id: createId(),
        role: "assistant",
        kind: result.escalated ? "escalation" : "text",
        text: result.reply,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="chat-window">
      <div
        className="chat-messages"
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        aria-label="Chat conversation"
      >
        {messages.map((message) =>
          message.kind === "escalation" ? (
            <EscalationNotice key={message.id} message={message} />
          ) : (
            <MessageBubble key={message.id} message={message} />
          ),
        )}
        {isLoading && <LoadingIndicator />}
        <div ref={scrollAnchorRef} />
      </div>
      <ChatInput onSend={handleSend} disabled={isLoading} />
    </div>
  );
}
