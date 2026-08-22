/**
 * Loading state shown while the (mocked) InquiryFlow "runs" for the
 * email channel — sad.md SS3: "loading state while InquiryFlow runs."
 * Mirrors /chat's LoadingIndicator pattern (typing-dot animation,
 * reduced-motion-safe via the global CSS reset in index.css).
 */
export default function EmailLoadingIndicator() {
  return (
    <div className="email-item email-item--loading">
      {/* Announcement is handled by the parent role="log" region
          (EmailInbox) — no separate aria-live here to avoid a
          redundant/duplicate announcement. */}
      <span className="typing-dot" />
      <span className="typing-dot" />
      <span className="typing-dot" />
      <span className="sr-only">Support team is preparing a reply…</span>
    </div>
  );
}
