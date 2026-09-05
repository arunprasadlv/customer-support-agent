# Judge Rubric — Response Faithfulness & Tone (EC-001, EC-004)

**Judge model**: `claude-opus-5` — deliberately different from both models under test (`claude-haiku-4-5`, `claude-sonnet-5`, per ADR-004) to avoid self-preference bias, per operator's Step 2 answer.

**Grades**: the `response_composer` agent's `draft_response`, given the original guest message, the retrieved KB snippet(s) (if any), and the sentiment label.

## Verdict labels (constrained, not free-form score)

- `PASS` — response is grounded only in the retrieved KB content (no invented facts, prices, policies, or availability not present in the snippets), and tone is appropriate to the guest's sentiment label (calmer/more empathetic for `frustrated`/`angry`, neutral-friendly for `neutral`).
- `FAIL` — response fabricates a fact not present in the retrieved KB content, OR tone is dismissive/inappropriate given the sentiment label, OR the response contradicts the `grounded` flag (e.g. states a specific policy when `grounded=false`).
- `BORDERLINE` — technically accurate but noticeably terse/robotic for a highly frustrated guest, or includes a minor unsupported embellishment that doesn't change the substantive answer. Use sparingly — most items should resolve to PASS or FAIL.

## Prompt template

```
You are grading a hotel customer-support assistant's response. You did not write this response and have no stake in defending it — grade strictly.

Guest message: {guest_message}
Guest sentiment label: {sentiment_label}
Retrieved KB content (empty if none matched): {kb_snippets}
System's grounded flag: {grounded}
Assistant's response: {draft_response}

Grade this response PASS, FAIL, or BORDERLINE per the rubric:
- PASS: grounded only in the KB content shown above, tone matches the sentiment label.
- FAIL: invents a fact/policy/price not in the KB content shown, OR tone is dismissive given the sentiment label, OR contradicts the grounded flag.
- BORDERLINE: accurate but tonally flat for a frustrated/angry guest, or a minor unsupported embellishment that doesn't change the substantive answer.

Respond with exactly one line: VERDICT: <PASS|FAIL|BORDERLINE>
Then one sentence explaining why.
```

## Calibration procedure (per SKILL.md reference.md)

1. Run this judge against `calibration_set.jsonl` (author-labeled — see that file's own provenance note; not yet independently human-reviewed, see evals.md Open Questions).
2. Compute agreement rate between judge verdict and the label.
3. If agreement is low on any category, revise this rubric before trusting the judge on the full `accuracy_grounded.jsonl`/`accuracy_ungrounded.jsonl` datasets.
4. Re-calibrate if the judge model, this rubric, or `response_composer`'s system prompt changes.
