import { useEffect, useRef, useState } from "react";
import { sendEmail } from "../lib/mockEmailClient";
import type { EmailComposeInput, EmailThreadEntry } from "../types/email";
import EmailComposeForm from "./EmailComposeForm";
import EmailEscalationNotice from "./EmailEscalationNotice";
import EmailLoadingIndicator from "./EmailLoadingIndicator";
import EmailReplyItem from "./EmailReplyItem";
import EmailSentItem from "./EmailSentItem";

function createId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/**
 * Simulated email inbox — demonstrates the email channel through the
 * same underlying pipeline as chat (sad.md SS3 `/inbox`, PRD
 * FR-009/FR-010, AC-006). Owns all thread state locally (sent items +
 * replies, loading state). The only integration point with a future
 * real backend is `sendEmail` (lib/mockEmailClient.ts) —
 * `@integration.eng` swaps that one function for a real `POST /email`
 * call without needing to touch this component or its children.
 */
export default function EmailInbox() {
  const [thread, setThread] = useState<EmailThreadEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const scrollAnchorRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // Operable: respect prefers-reduced-motion for auto-scroll, same
    // pattern as /chat's ChatWindow.
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    scrollAnchorRef.current?.scrollIntoView({
      behavior: prefersReducedMotion ? "auto" : "smooth",
    });
  }, [thread, isLoading]);

  async function handleSend(input: EmailComposeInput) {
    const sentEntry: EmailThreadEntry = {
      id: createId(),
      kind: "sent",
      from: input.from,
      subject: input.subject,
      body: input.body,
      timestamp: Date.now(),
    };
    setThread((prev) => [...prev, sentEntry]);
    setIsLoading(true);

    try {
      const result = await sendEmail(input);
      const replyEntry: EmailThreadEntry = {
        id: createId(),
        kind: result.escalated ? "escalation" : "reply",
        subject: `Re: ${input.subject}`,
        body: result.reply_body,
        timestamp: Date.now(),
      };
      setThread((prev) => [...prev, replyEntry]);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="inbox-window">
      <div
        className="email-thread"
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        aria-label="Email thread"
      >
        {thread.length === 0 && !isLoading && (
          <p className="email-thread__empty">
            No messages yet — compose an email below to see it sent, and get a reply.
          </p>
        )}
        {thread.map((entry) => {
          if (entry.kind === "sent") {
            return <EmailSentItem key={entry.id} entry={entry} />;
          }
          if (entry.kind === "escalation") {
            return <EmailEscalationNotice key={entry.id} entry={entry} />;
          }
          return <EmailReplyItem key={entry.id} entry={entry} />;
        })}
        {isLoading && <EmailLoadingIndicator />}
        <div ref={scrollAnchorRef} />
      </div>
      <EmailComposeForm onSend={handleSend} disabled={isLoading} />
    </div>
  );
}
