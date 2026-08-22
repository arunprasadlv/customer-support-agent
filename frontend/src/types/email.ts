/**
 * Shared email types for the /inbox route.
 *
 * @frontend.eng, *develop-fe /inbox. `EmailComposeInput`/`EmailResult`
 * intentionally mirror the future real backend contract (sad.md SS4:
 * `POST /email` -> `{from, subject, body}` -> `{reply_body, escalated:
 * bool}`) so `@integration.eng` can swap the mock client for a real
 * fetch call without changing these types or any component that
 * consumes them.
 */

export type EmailThreadEntryKind = "sent" | "reply" | "escalation";

export interface EmailThreadEntry {
  id: string;
  kind: EmailThreadEntryKind;
  /** Sender email/name — only present on "sent" entries. */
  from?: string;
  subject: string;
  body: string;
  timestamp: number;
}

export interface EmailComposeInput {
  from: string;
  subject: string;
  body: string;
}

export interface EmailResult {
  reply_body: string;
  escalated: boolean;
}
