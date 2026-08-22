/**
 * Shared chat types for the /chat route.
 *
 * @frontend.eng, *develop-fe. `InquiryResult` intentionally mirrors the
 * future real backend contract (sad.md SS4: `POST /chat` ->
 * `{reply, escalated: bool}`) so `@integration.eng` can swap the mock
 * client for a real fetch call without changing these types or any
 * component that consumes them.
 */

export type ChatRole = "guest" | "assistant";

export type ChatMessageKind = "text" | "escalation";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  kind: ChatMessageKind;
  text: string;
  timestamp: number;
}

export interface InquiryResult {
  reply: string;
  escalated: boolean;
}
