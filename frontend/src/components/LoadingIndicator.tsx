/**
 * Loading state shown while the (mocked) InquiryFlow "runs" —
 * sad.md SS3: "loading state while InquiryFlow runs."
 */
export default function LoadingIndicator() {
  return (
    <div className="chat-row chat-row--assistant">
      {/* Announcement is handled by the parent role="log" region
          (ChatWindow) — no separate aria-live here to avoid a
          redundant/duplicate announcement. */}
      <div className="chat-bubble chat-bubble--assistant chat-bubble--loading">
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="sr-only">Support assistant is composing a reply…</span>
      </div>
    </div>
  );
}
