import { useEffect } from "react";
import ChatWindow from "../components/ChatWindow";
import { HOTEL_NAME } from "../config/brand";
import "../styles/chat.css";

/**
 * /chat route — guest chat widget (sad.md SS3, PRD NFR-001).
 *
 * Real UI built by @frontend.eng (*develop-fe). Backend wiring is
 * intentionally deferred to @integration.eng (*integrate-api) — see
 * src/lib/mockInquiryClient.ts for the swap boundary.
 */
export default function Chat() {
  // SC 2.4.2 Page Titled — SPA routes share one HTML document, so each
  // route sets its own title on mount.
  useEffect(() => {
    document.title = `Support Chat — ${HOTEL_NAME}`;
  }, []);

  return (
    <section className="chat-page">
      <h1>{HOTEL_NAME} — Support Chat</h1>
      <p className="chat-page__subtitle">
        Ask about reservations, billing, amenities, or anything else — this demo assistant
        simulates escalation to a human when needed.
      </p>
      <ChatWindow />
    </section>
  );
}
