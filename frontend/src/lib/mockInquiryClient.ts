import { ApiError, apiFetch } from "./apiClient";
import type { InquiryResult } from "../types/chat";

/**
 * `@integration.eng`'s `*integrate-api` swap: real `POST /chat` call
 * (sad.md §4: `{message, session_id} -> {reply, escalated: bool}`,
 * delivered via `InquiryFlow`: pii_guard -> reasoning Crew -> escalation
 * gate). Filename/export kept as `mockInquiryClient.ts`/`sendInquiry` —
 * this is the exact swap point `@frontend.eng` built `ChatWindow.tsx`
 * against (see that component's docstring); renaming would require an
 * unrequested change to a component this run is scoped to leave alone.
 *
 * Session id (judgment call — sad.md pins the request shape but nothing
 * in the frontend previously generated a `session_id`, per
 * frontend.md's flagged gap): generated once per browser tab and cached
 * in `sessionStorage`, entirely inside this module. `sendInquiry`'s
 * signature is left unchanged (`(message: string) => Promise<InquiryResult>`)
 * rather than threading a session id through `ChatWindow.tsx`, since the
 * id is a transport-level concern the UI has no reason to own or display.
 */

const SESSION_STORAGE_KEY = "csa_chat_session_id";

function getOrCreateSessionId(): string {
  try {
    const existing = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (existing) {
      return existing;
    }
    const created = crypto.randomUUID();
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, created);
    return created;
  } catch {
    // sessionStorage can throw in locked-down browser contexts (e.g.
    // privacy mode in some browsers); fall back to a per-call id rather
    // than crashing the chat flow. Each call then reads as a new session
    // to the backend — an accepted MVP degradation, documented in
    // integration.md Assumptions.
    return crypto.randomUUID();
  }
}

// Honest, human-readable fallback shown when the backend can't be reached
// or fails unexpectedly. Reuses the existing escalation UI (EscalationNotice
// via ChatMessage.kind === "escalation") rather than inventing a new error
// component — `escalated: true` is the closest existing state to "a human
// needs to pick this up," and never fabricates a canned/grounded-looking
// answer (AC-003), matching the mock's original never-silently-drop intent.
const UNREACHABLE_REPLY =
  "I'm having trouble reaching our support system right now. I'm looping in a member of our " +
  "human support team to follow up — please try again in a moment in the meantime.";

/** One real `InquiryFlow` round trip via `POST /chat`. */
export function sendInquiry(message: string): Promise<InquiryResult> {
  const session_id = getOrCreateSessionId();
  return apiFetch<InquiryResult>("/chat", {
    method: "POST",
    body: JSON.stringify({ message, session_id }),
  }).catch((error: unknown) => {
    console.error("sendInquiry failed", error instanceof ApiError ? error.message : error);
    return { reply: UNREACHABLE_REPLY, escalated: true };
  });
}
