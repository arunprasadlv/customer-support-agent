import { ApiError, apiFetch } from "./apiClient";
import type { EmailComposeInput, EmailResult } from "../types/email";

/**
 * `@integration.eng`'s `*integrate-api` swap: real `POST /email` call
 * (sad.md §4: `{from, subject, body} -> {reply_body, escalated: bool}`,
 * delivered via the same `InquiryFlow` as chat with `channel=email`).
 * Filename/export kept as `mockEmailClient.ts`/`sendEmail` — the exact
 * swap point `@frontend.eng` built `EmailInbox.tsx` against; shapes
 * already match the real contract exactly, so this is a clean swap with
 * no request/response mapping decisions needed (unlike `/chat`'s
 * session-id gap or `/ops`'s field mismatches — see integration.md).
 */

// Same reuse-the-escalation-UI reasoning as mockInquiryClient.ts's
// UNREACHABLE_REPLY — kept as an independent constant (not shared/
// imported across the two client modules) to preserve the same
// channel-independence `@frontend.eng` established for the mocks.
const UNREACHABLE_REPLY =
  "I'm having trouble reaching our support system right now. I'm looping in a member of our " +
  "human support team to follow up by email shortly — please try again in a moment in the " +
  "meantime.";

/** One real `InquiryFlow` round trip (channel=email) via `POST /email`. */
export function sendEmail(input: EmailComposeInput): Promise<EmailResult> {
  return apiFetch<EmailResult>("/email", {
    method: "POST",
    body: JSON.stringify(input),
  }).catch((error: unknown) => {
    console.error("sendEmail failed", error instanceof ApiError ? error.message : error);
    return { reply_body: UNREACHABLE_REPLY, escalated: true };
  });
}
