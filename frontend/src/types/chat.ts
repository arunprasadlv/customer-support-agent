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

export type ChatMessageKind = "text" | "escalation" | "options";

/**
 * One clickable quick-reply pill (frontend.md §12: taxonomy category
 * chips, then a category's common-question chips). `onSelect` is baked
 * in by whoever builds the `ChatMessage` (ChatWindow) — a category chip's
 * `onSelect` appends a new `"options"` message with that category's
 * questions (pure local UI nav, no backend call); a common-question
 * chip's `onSelect` calls `handleSend` with `label`, i.e. sends it exactly
 * as if the guest had typed and submitted it. Keeping the behavior on the
 * option itself (rather than branching on a second "chip type" enum
 * inside the renderer) lets a single `"options"` message kind and a
 * single `QuickReplyOptions` renderer serve both steps without the
 * renderer needing to know category-vs-question semantics.
 */
export interface QuickReplyOption {
  id: string;
  label: string;
  onSelect: () => void;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  kind: ChatMessageKind;
  text: string;
  /** Only set when `kind === "options"`; the chip choices to render. */
  options?: QuickReplyOption[];
  /** Only set when `kind === "options"`; accessible label for the chip group. */
  optionsGroupLabel?: string;
  timestamp: number;
}

export interface InquiryResult {
  reply: string;
  escalated: boolean;
}
