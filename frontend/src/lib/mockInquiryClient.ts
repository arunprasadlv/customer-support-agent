import type { InquiryResult } from "../types/chat";

/**
 * MOCK ONLY — do not treat as production logic.
 *
 * Stands in for the future `POST /chat` call (sad.md SS4:
 * `{message, session_id} -> {reply, escalated: bool}`, delivered via
 * `InquiryFlow`: pii_guard -> reasoning Crew -> escalation gate). This
 * module is the intended swap point for `@integration.eng`'s
 * `*integrate-api`: replace the body of `sendInquiry` with a real
 * `fetch()` call against `VITE_API_BASE_URL` (see
 * frontend/.env.example). The function signature and `InquiryResult`
 * shape already match the real contract, so no caller (ChatWindow)
 * needs to change when the swap happens.
 *
 * Per @frontend.eng's persona Workflow Notes, this file must NOT call a
 * real backend endpoint.
 */

const MOCK_LATENCY_MS = 1100;

// Deliberately simple, demo-only heuristic — not a stand-in for the real
// sentiment_analyzer/escalation_gate (sad.md SS2 ADR-002). Typing any of
// these words/phrases (or literally "escalate") triggers the escalation
// UI state for demo purposes.
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
      "I found your reservation details in our system. Standard check-in is 3:00 PM and " +
      "check-out is 11:00 AM; early check-in is subject to availability. Would you like me " +
      "to check availability for a different date?",
  },
  {
    keywords: ["bill", "invoice", "charge", "folio", "payment"],
    reply:
      "I've reviewed the billing entry you're asking about. Incidental charges (minibar, " +
      "room service) are itemized separately from the room rate on your folio. Let me know " +
      "if you'd like a full breakdown emailed to you.",
  },
  {
    keywords: ["towel", "service", "amenity", "amenities", "spa", "gym", "wifi"],
    reply:
      "That amenity is available. The spa and gym are open 6:00 AM to 10:00 PM daily, and " +
      "extra towels can be requested anytime via housekeeping.",
  },
];

const FALLBACK_REPLY =
  "Thanks for reaching out. I don't have a confident, grounded answer for that specific " +
  "question yet — could you share a bit more detail so I can look into it further?";

const ESCALATION_REPLY =
  "I understand this is frustrating, and I don't want to guess at a resolution here. I'm " +
  "looping in a member of our human support team to take over from this point — they'll " +
  "follow up shortly. (Simulated hand-off — no real agent is notified in this demo.)";

function isEscalationWorthy(message: string): boolean {
  const normalized = message.toLowerCase();
  return ESCALATION_KEYWORDS.some((keyword) => normalized.includes(keyword));
}

function pickCannedReply(message: string): string {
  const normalized = message.toLowerCase();
  const match = CANNED_REPLIES.find(({ keywords }) =>
    keywords.some((keyword) => normalized.includes(keyword)),
  );
  return match ? match.reply : FALLBACK_REPLY;
}

/**
 * Simulates one InquiryFlow round trip. Resolves after a fixed delay
 * with either a grounded canned reply or an honest, clearly-labeled
 * escalation notice — mirroring AC-003's "never silently drop or
 * fabricate" intent even in mock form.
 */
export function sendInquiry(message: string): Promise<InquiryResult> {
  return new Promise((resolve) => {
    setTimeout(() => {
      if (isEscalationWorthy(message)) {
        resolve({ reply: ESCALATION_REPLY, escalated: true });
        return;
      }
      resolve({ reply: pickCannedReply(message), escalated: false });
    }, MOCK_LATENCY_MS);
  });
}
