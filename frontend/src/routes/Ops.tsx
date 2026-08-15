import { useEffect } from "react";
import InteractionLog from "../components/InteractionLog";
import ReviewQueue from "../components/ReviewQueue";
import "../styles/ops.css";

/**
 * /ops route — internal ops view: interaction log (sad.md SS3, PRD
 * NFR-003) + KB review queue (sad.md SS3 line ~144, PRD FR-014,
 * NFR-008, AC-010/AC-011).
 *
 * Guest-facing surfaces (/chat, /inbox) are out of scope here — this is
 * the hotel support/ops staff and Reviewer-persona surface (PRD SS2,
 * SS6 "Ops-facing").
 *
 * Real UI built by @frontend.eng (*develop-fe /ops). Backend wiring is
 * intentionally deferred to @integration.eng (*integrate-api) — see
 * src/lib/mockOpsData.ts for the swap boundary.
 */
export default function Ops() {
  // SC 2.4.2 Page Titled — SPA routes share one HTML document, so each
  // route sets its own title on mount (mirrors Chat.tsx/Inbox.tsx).
  useEffect(() => {
    document.title = "Ops — Interaction Log & KB Review — customer-support-agent";
  }, []);

  return (
    <section className="ops-page">
      <h1>Ops</h1>
      <p className="ops-page__subtitle">
        Internal view for hotel support/ops staff: every processed inquiry, and the candidate
        knowledge-base entries generated from escalation resolutions awaiting Reviewer decision.
      </p>

      <section className="ops-section" aria-labelledby="ops-interaction-log-heading">
        <h2 id="ops-interaction-log-heading" className="ops-section__heading">
          Interaction Log
        </h2>
        <p className="ops-section__description">
          Read-only. One row per processed inquiry from either Chat or the Inbox, showing the
          original query, classification, sentiment, whether PII was redacted, and the outcome.
        </p>
        <InteractionLog />
      </section>

      <section className="ops-section" aria-labelledby="ops-review-queue-heading">
        <h2 id="ops-review-queue-heading" className="ops-section__heading">
          KB Review Queue
        </h2>
        <p className="ops-section__description">
          Candidate knowledge-base entries generated from escalation resolutions. This is the
          only path that can change the live knowledge base — nothing reaches it without an
          explicit Approve decision below.
        </p>
        <ReviewQueue />
      </section>
    </section>
  );
}
