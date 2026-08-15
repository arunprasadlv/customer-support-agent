import { useEffect } from "react";
import EmailInbox from "../components/EmailInbox";
import "../styles/inbox.css";

/**
 * /inbox route — simulated email inbox (sad.md SS3, PRD FR-009/FR-010,
 * AC-006).
 *
 * Real UI built by @frontend.eng (*develop-fe /inbox). Backend wiring
 * is intentionally deferred to @integration.eng (*integrate-api) — see
 * src/lib/mockEmailClient.ts for the swap boundary.
 */
export default function Inbox() {
  // SC 2.4.2 Page Titled — SPA routes share one HTML document, so each
  // route sets its own title on mount (mirrors Chat.tsx).
  useEffect(() => {
    document.title = "Simulated Email Inbox — customer-support-agent";
  }, []);

  return (
    <section className="inbox-page">
      <h1>Simulated Email Inbox</h1>
      <p className="inbox-page__subtitle">
        Submit a request the way you'd send an email — this demo runs it through the same
        support pipeline as chat, and simulates escalation to a human when needed.
      </p>
      <EmailInbox />
    </section>
  );
}
