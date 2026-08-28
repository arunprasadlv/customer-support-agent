import { useEffect, useRef, useState } from "react";
import { HOTEL_NAME } from "../config/brand";
import { sendInquiry } from "../lib/mockInquiryClient";
import { getTaxonomy } from "../lib/taxonomyClient";
import type { ChatMessage } from "../types/chat";
import type { TaxonomyEntry } from "../types/taxonomy";
import ChatInput from "./ChatInput";
import EscalationNotice from "./EscalationNotice";
import LoadingIndicator from "./LoadingIndicator";
import MessageBubble from "./MessageBubble";
import QuickReplyOptions from "./QuickReplyOptions";

const WELCOME_MESSAGE: ChatMessage = {
  id: "welcome",
  role: "assistant",
  kind: "text",
  text:
    `Hi, I'm the ${HOTEL_NAME} support assistant. Ask me about a reservation, your bill, ` +
    "amenities, or anything else — I'll do my best to help, and I'll loop in a human if " +
    "something needs escalation.",
  timestamp: Date.now(),
};

function createId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/**
 * Guest chat widget — primary interaction surface (sad.md SS3, PRD
 * NFR-001). Owns all chat state locally (message list, loading state).
 * The only integration point with a future real backend for guest
 * queries is `sendInquiry` (lib/mockInquiryClient.ts) — `@integration.eng`
 * swaps that one function for a real `POST /chat` call without needing to
 * touch this component or its children. Quick-reply chips (frontend.md
 * §12) additionally call the real, already-live `GET /taxonomy` via
 * `lib/taxonomyClient.ts`'s `getTaxonomy` — that call is fail-open (a
 * failed fetch just skips the chips, logged via console.warn) so the
 * free-text path above is never affected by it.
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

  /**
   * Step 2 of the quick-reply flow (frontend.md §12): appends a new
   * assistant "options" message showing `entry`'s common questions as
   * chips. Pure local UI navigation — no guest message, no `sendInquiry`
   * call — matches the operator-confirmed spec that a category click
   * never itself counts as a query.
   */
  function handleCategorySelect(entry: TaxonomyEntry) {
    const questionsMessage: ChatMessage = {
      id: createId(),
      role: "assistant",
      kind: "options",
      text: `Common questions about "${entry.label}":`,
      optionsGroupLabel: "Choose a question",
      options: entry.common_queries.map((commonQuery) => ({
        id: commonQuery.kb_entry_id,
        label: commonQuery.query,
        // Step 3: clicking a common-question chip sends it exactly as if
        // the guest had typed and submitted it — same handleSend path,
        // same loading indicator, same escalation/normal-reply rendering.
        onSelect: () => {
          void handleSend(commonQuery.query);
        },
      })),
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, questionsMessage]);
  }

  useEffect(() => {
    // Step 1 of the quick-reply flow (frontend.md §12): fetch the domain
    // taxonomy once on mount and, on success, append a category-chips
    // message right after the static welcome message. Fail-open on
    // fetch failure — console.warn only, chips are simply skipped so the
    // free-text ChatInput path below remains fully usable regardless
    // (same posture as apiClient.ts's base-URL fallback).
    let cancelled = false;
    getTaxonomy()
      .then((entries) => {
        if (cancelled || entries.length === 0) return;
        const categoryMessage: ChatMessage = {
          id: createId(),
          role: "assistant",
          kind: "options",
          text: "Here are some things I can help with — pick a topic, or just type your question below.",
          optionsGroupLabel: "Choose a topic",
          options: entries.map((entry) => ({
            id: entry.intent,
            label: entry.label,
            onSelect: () => handleCategorySelect(entry),
          })),
          timestamp: Date.now(),
        };
        setMessages((prev) => [...prev, categoryMessage]);
      })
      .catch((error: unknown) => {
        console.warn(
          "Failed to load /taxonomy quick-reply chips — chat remains fully usable via free text.",
          error,
        );
      });
    return () => {
      cancelled = true;
    };
    // Mount-only fetch (empty deps deliberate): handleCategorySelect/
    // handleSend are stable enough for this one-time appended message —
    // each chip's onSelect closes over the `entries`/`commonQuery` it was
    // built from, not over any state that goes stale after mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="chat-window">
      <div
        className="chat-messages"
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        aria-label="Chat conversation"
      >
        {messages.map((message) => {
          if (message.kind === "escalation") {
            return <EscalationNotice key={message.id} message={message} />;
          }
          if (message.kind === "options") {
            return <QuickReplyOptions key={message.id} message={message} />;
          }
          return <MessageBubble key={message.id} message={message} />;
        })}
        {isLoading && <LoadingIndicator />}
        <div ref={scrollAnchorRef} />
      </div>
      <ChatInput onSend={handleSend} disabled={isLoading} />
    </div>
  );
}
