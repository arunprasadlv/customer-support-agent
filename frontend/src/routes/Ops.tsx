import { useEffect, useState } from "react";
import EscalationResolutionQueue from "../components/EscalationResolutionQueue";
import InteractionLog from "../components/InteractionLog";
import ReviewQueue from "../components/ReviewQueue";
import { HOTEL_NAME } from "../config/brand";
import "../styles/ops.css";

/**
 * /ops route — internal ops view: interaction log (sad.md SS3, PRD
 * NFR-003), escalated-interaction resolution (frontend.md §11, closing
 * the FR-008 gap between an escalated interaction and the KB review
 * queue), and the KB review queue (sad.md SS3 line ~144, PRD FR-014,
 * NFR-008, AC-010/AC-011).
 *
 * Guest-facing surfaces (/chat, /inbox) are out of scope here — this is
 * the hotel support/ops staff and Reviewer-persona surface (PRD SS2,
 * SS6 "Ops-facing").
 *
 * Real UI built by @frontend.eng (*develop-fe /ops). All three sections
 * call the real backend directly (see src/lib/mockOpsData.ts) — /ops is
 * fully live-wired, not a mock; there is no remaining swap boundary.
 */
export default function Ops() {
  // SC 2.4.2 Page Titled — SPA routes share one HTML document, so each
  // route sets its own title on mount (mirrors Chat.tsx/Inbox.tsx).
  useEffect(() => {
    document.title = `Ops — Interaction Log & KB Review — ${HOTEL_NAME}`;
  }, []);

  // Bumped whenever an escalation resolution is submitted, so the
  // Interaction Log, the Escalated — Needs Resolution list, and the KB
  // Review Queue all refetch and reflect the new state without a manual
  // page reload (frontend.md §11 "the refresh problem"). A plain number
  // counter, not any richer pub/sub — the smallest change that lets three
  // already-independent components' existing `useEffect`s pick up a
  // change made by a sibling.
  const [refreshToken, setRefreshToken] = useState(0);

  function handleResolved() {
    setRefreshToken((prev) => prev + 1);
  }

  return (
    <section className="ops-page">
      <h1>{HOTEL_NAME} — Ops</h1>
      <p className="ops-page__subtitle">
        Internal view for hotel support/ops staff: every processed inquiry, escalated inquiries
        awaiting a human resolution, and the candidate knowledge-base entries generated from those
        resolutions, awaiting Reviewer decision.
      </p>

      <section className="ops-section" aria-labelledby="ops-interaction-log-heading">
        <h2 id="ops-interaction-log-heading" className="ops-section__heading">
          Interaction Log
        </h2>
        <p className="ops-section__description">
          Read-only. One row per processed inquiry from either Chat or the Inbox, showing the
          original query, classification, sentiment, whether PII was redacted, and the outcome.
        </p>
        <InteractionLog refreshToken={refreshToken} />
      </section>

      <section className="ops-section" aria-labelledby="ops-escalation-queue-heading">
        <h2 id="ops-escalation-queue-heading" className="ops-section__heading">
          Escalated — Needs Resolution
        </h2>
        <p className="ops-section__description">
          Escalated interactions that don't yet have a submitted resolution. Write a resolution
          and submit it to queue a candidate knowledge-base entry for Reviewer decision below.
        </p>
        <EscalationResolutionQueue refreshToken={refreshToken} onResolved={handleResolved} />
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
        <ReviewQueue refreshToken={refreshToken} />
      </section>
    </section>
  );
}
