"""Deterministic, regex/pattern-based PII detector — same style as
domain/loader.py's pure-function `kb_search`: no LLM call, no network,
fully local and explainable.

sad.md §2 ADR-003 requires `pii_guard` to redact PII "before any other
component sees the raw text" (FR-011); the stakeholder-confirmed design
decision (recorded in backend.md Assumptions) is that this detection is
deterministic rather than LLM-only, so a wrong call here — a Must-priority
security control — is never a matter of LLM judgment.

Detected entity types (minimum set required by this run's task):
    - "email"           RFC-5322-ish local@domain.tld
    - "phone"           North-American-style 10-digit phone numbers, with
                         optional country code / separators
    - "account_number"  digit sequences (6-19 digits, optional separators)
                         immediately preceded by an account/confirmation/
                         reservation/booking/card context keyword — this
                         keeps it explainable and avoids over-redacting
                         bare numbers that aren't actually account IDs
    - "name"             capitalized 1-3 word sequences following a
                         self-introduction phrase ("my name is", "I'm",
                         "I am", "this is")

Every detected span is returned with (entity_type, span_start, span_end,
method) — offsets are into the ORIGINAL input text, matching
`RedactionAction` in app.schemas.task_outputs (do not redefine that model
here; import and reuse it).
"""

from __future__ import annotations

import re

from app.schemas.task_outputs import RedactionAction, RedactionResult

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Optional country code, optional separators/parens around the area code,
# 10 digits total. Bounded by non-digit lookaround so it doesn't eat into a
# longer digit run (e.g. part of an account number).
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"
)

# Requires an explicit context keyword (optionally followed by "number"/
# "no"/"#" and a connector like "is"/"was"/":") before the digits, so a
# bare number is never treated as an account/confirmation number on its
# own — this is what keeps the match explainable per ADR-005-style
# reasoning.
_ACCOUNT_NUMBER_RE = re.compile(
    r"\b(?:account|acct|confirmation|reservation|booking|card)\b"
    r"(?:\s*(?:number|no\.?|#))?\s*(?:is|was|:|#)?\s*(\d[\d\- ]{4,17}\d)\b",
    re.IGNORECASE,
)

# Captures only the name portion (group 1), not the introductory phrase.
_NAME_RE = re.compile(
    r"\b(?:[Mm]y name is|[Ii]\s+am|[Ii]'m|[Tt]his is)\s+"
    r"([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+){0,2})"
)

_MASKS: dict[str, str] = {
    "email": "[REDACTED_EMAIL]",
    "phone": "[REDACTED_PHONE]",
    "account_number": "[REDACTED_ACCOUNT_NUMBER]",
    "name": "[REDACTED_NAME]",
}

# (entity_type, compiled pattern, capture group to use for the span or None
# for the whole match). Order = priority when spans overlap: earlier
# entries win, so a context-qualified account number is preferred over a
# bare phone-shaped digit run inside it, etc.
_PATTERNS: list[tuple[str, re.Pattern[str], int | None]] = [
    ("email", _EMAIL_RE, None),
    ("account_number", _ACCOUNT_NUMBER_RE, 1),
    ("phone", _PHONE_RE, None),
    ("name", _NAME_RE, 1),
]


def detect_pii(text: str) -> RedactionResult:
    """Detect PII spans in `text` and return a RedactionResult with
    `clean_text` (all detected spans masked) and `redaction_actions` (one
    explainable RedactionAction per span, offsets into the original text).

    Pure function: no I/O, no network, no LLM call — deterministic given
    the same input, matching the style of domain/loader.py's `kb_search`.
    """
    candidates: list[tuple[int, int, int, str]] = []  # (priority, start, end, entity_type)
    for priority, (entity_type, pattern, group) in enumerate(_PATTERNS):
        for m in pattern.finditer(text):
            start, end = (m.start(group), m.end(group)) if group else (m.start(), m.end())
            candidates.append((priority, start, end, entity_type))

    # Priority first (lower = higher precedence), then longer spans first,
    # then leftmost first — fully deterministic ordering.
    candidates.sort(key=lambda c: (c[0], -(c[2] - c[1]), c[1]))

    occupied: list[tuple[int, int]] = []
    accepted: list[tuple[int, int, str]] = []
    for _priority, start, end, entity_type in candidates:
        if any(start < occ_end and end > occ_start for occ_start, occ_end in occupied):
            continue
        occupied.append((start, end))
        accepted.append((start, end, entity_type))

    accepted.sort(key=lambda a: a[0])

    actions = [
        RedactionAction(entity_type=entity_type, span_start=start, span_end=end, method="mask")
        for start, end, entity_type in accepted
    ]

    clean_chars = list(text)
    for start, end, entity_type in sorted(accepted, key=lambda a: a[0], reverse=True):
        clean_chars[start:end] = list(_MASKS[entity_type])
    clean_text = "".join(clean_chars)

    return RedactionResult(clean_text=clean_text, redaction_actions=actions)
