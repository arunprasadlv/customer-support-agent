interface BotAvatarProps {
  /** Pulses gently while a reply is in flight (LoadingIndicator only). */
  thinking?: boolean;
}

/**
 * Decorative assistant avatar shown next to every assistant-side row
 * (normal reply, escalation notice, loading state). Purely decorative
 * and redundant with the adjacent "Support Assistant" text label, so
 * it's aria-hidden rather than given alt/label text — an icon that
 * duplicated that text would itself be an accessibility anti-pattern
 * (redundant alt text). Entrance/pulse animation is neutralized by the
 * global prefers-reduced-motion reset in index.css.
 */
export default function BotAvatar({ thinking = false }: BotAvatarProps) {
  return (
    <span
      className={`bot-avatar${thinking ? " bot-avatar--thinking" : ""}`}
      aria-hidden="true"
    >
      🤖
    </span>
  );
}
