import { useState } from "react";
import type { FormEvent } from "react";
import type { EmailComposeInput } from "../types/email";

interface EmailComposeFormProps {
  onSend: (input: EmailComposeInput) => void;
  disabled: boolean;
}

/**
 * Compose form matching the `POST /email` contract shape (sad.md SS4:
 * `{from, subject, body}`). Every field has a real, visible
 * `<label for>` — unlike /chat's single sr-only-labeled input, this
 * form has three distinct fields, so visible labels were chosen for
 * clarity for a non-technical demo audience (PRD NFR-001) rather than
 * placeholder-only or visually-hidden text.
 */
export default function EmailComposeForm({ onSend, disabled }: EmailComposeFormProps) {
  const [from, setFrom] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");

  const canSubmit = Boolean(from.trim() && subject.trim() && body.trim()) && !disabled;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;
    onSend({ from: from.trim(), subject: subject.trim(), body: body.trim() });
    setFrom("");
    setSubject("");
    setBody("");
  }

  return (
    <form className="email-compose-form" onSubmit={handleSubmit} aria-label="Compose email">
      <h2 className="email-compose-form__heading">Compose Email</h2>

      <div className="email-compose-form__field">
        <label htmlFor="email-from-input">Your email or name</label>
        <input
          id="email-from-input"
          name="from"
          type="email"
          value={from}
          onChange={(event) => setFrom(event.target.value)}
          placeholder="guest@example.com"
          disabled={disabled}
          required
        />
      </div>

      <div className="email-compose-form__field">
        <label htmlFor="email-subject-input">Subject</label>
        <input
          id="email-subject-input"
          name="subject"
          type="text"
          value={subject}
          onChange={(event) => setSubject(event.target.value)}
          placeholder="e.g. Question about my reservation"
          disabled={disabled}
          required
        />
      </div>

      <div className="email-compose-form__field">
        <label htmlFor="email-body-input">Message</label>
        <textarea
          id="email-body-input"
          name="body"
          value={body}
          onChange={(event) => setBody(event.target.value)}
          placeholder="Describe your reservation, billing, amenity, or other request…"
          rows={5}
          disabled={disabled}
          required
        />
      </div>

      <button type="submit" disabled={!canSubmit}>
        Send Email
      </button>
    </form>
  );
}
