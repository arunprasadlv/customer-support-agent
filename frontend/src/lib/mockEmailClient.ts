import type { EmailComposeInput, EmailResult } from "../types/email";

/**
 * MOCK ONLY — do not treat as production logic.
 *
 * Stands in for the future `POST /email` call (sad.md SS4:
 * `{from, subject, body} -> {reply_body, escalated: bool}`, delivered
 * via the same `InquiryFlow` as chat with `channel=email`: pii_guard ->
 * reasoning Crew -> escalation gate). This module is the intended swap
 * point for `@integration.eng`'s `*integrate-api`: replace the body of
 * `sendEmail` with a real `fetch()` call against `VITE_API_BASE_URL`
 * (see frontend/.env.example). The function signature and `EmailResult`
 * shape already match the real contract, so no caller (EmailInbox)
 * needs to change when the swap happens.
 *
 * Per @frontend.eng's persona Workflow Notes, this file must NOT call a
 * real backend endpoint. Kept fully independent from
 * `mockInquiryClient.ts` (chat's mock) — no shared imports — so this
 * route can be built/reasoned about without touching `/chat`.
 */

const MOCK_LATENCY_MS = 1300;

// Deliberately simple, demo-only heuristic — not a stand-in for the real
// sentiment_analyzer/escalation_gate (sad.md SS2 ADR-002). Mirrors the
// same trigger words as chat's mock for consistent demo behavior across
// channels, but is its own independent list/module.
const ESCALATION_KEYWORDS = [
  "angry",
  "furious",
  "unacceptable",
  "terrible",
  "worst",
  "disgusting",
  "lawsuit",
  "refund now",
  "speak to a manager",
  "escalate",
  "human agent",
  "ridiculous",
];

const CANNED_REPLIES: Array<{ keywords: string[]; reply: string }> = [
  {
    keywords: ["book", "reservation", "reserve", "room"],
    reply:
      "Thanks for your email. I found your reservation details in our system. Standard " +
      "check-in is 3:00 PM and check-out is 11:00 AM; early check-in is subject to " +
      "availability. Reply to this email if you'd like me to check a different date.",
  },
  {
    keywords: ["bill", "invoice", "charge", "folio", "payment"],
    reply:
      "Thanks for your email. I've reviewed the billing entry you're asking about. " +
      "Incidental charges (minibar, room service) are itemized separately from the room " +
      "rate on your folio. Let me know if you'd like a full breakdown sent over.",
  },
  {
    keywords: ["towel", "service", "amenity", "amenities", "spa", "gym", "wifi"],
    reply:
      "Thanks for your email. That amenity is available — the spa and gym are open 6:00 AM " +
      "to 10:00 PM daily, and extra towels can be requested anytime via housekeeping.",
  },
];

const FALLBACK_REPLY =
  "Thanks for reaching out. I don't have a confident, grounded answer for that specific " +
  "question yet — could you reply with a bit more detail so I can look into it further?";

const ESCALATION_REPLY =
  "I understand this is frustrating, and I don't want to guess at a resolution over email. " +
  "I'm looping in a member of our human support team to take over from this point — they'll " +
  "follow up shortly by email. (Simulated hand-off — no real agent is notified in this demo.)";

function isEscalationWorthy(subject: string, body: string): boolean {
  const normalized = `${subject} ${body}`.toLowerCase();
  return ESCALATION_KEYWORDS.some((keyword) => normalized.includes(keyword));
}

function pickCannedReply(subject: string, body: string): string {
  const normalized = `${subject} ${body}`.toLowerCase();
  const match = CANNED_REPLIES.find(({ keywords }) =>
    keywords.some((keyword) => normalized.includes(keyword)),
  );
  return match ? match.reply : FALLBACK_REPLY;
}

/**
 * Simulates one InquiryFlow round trip for the email channel. Resolves
 * after a fixed delay with either a grounded canned reply or an honest,
 * clearly-labeled escalation notice — mirroring AC-003's "never
 * silently drop or fabricate" intent even in mock form.
 */
export function sendEmail(input: EmailComposeInput): Promise<EmailResult> {
  return new Promise((resolve) => {
    setTimeout(() => {
      if (isEscalationWorthy(input.subject, input.body)) {
        resolve({ reply_body: ESCALATION_REPLY, escalated: true });
        return;
      }
      resolve({ reply_body: pickCannedReply(input.subject, input.body), escalated: false });
    }, MOCK_LATENCY_MS);
  });
}
