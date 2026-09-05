"""LLM-as-judge runner for the faithfulness/tone dimension (EC-004).

Judge model: claude-opus-5 (operator's Step 2 answer — different from both
models under test, claude-haiku-4-5/claude-sonnet-5, to avoid
self-preference bias). Uses the `anthropic` SDK directly (already a
dependency via the `crewai[anthropic]` extra, per backend.md).

Two modes:
  --calibrate   Run against judge/calibration_set.jsonl, compute agreement
                rate vs. the (author-labeled, not yet human-reviewed - see
                evals.md Open Questions) labels in that file. Run this
                FIRST and check agreement before trusting full-dataset runs.
  --items FILE  Run against a JSON file of {guest_message, sentiment_label,
                kb_snippets, grounded, draft_response} records (e.g. the
                output of check_live_accuracy.py, reshaped) and print a
                verdict per item with no ground-truth comparison.

Costs real API calls (one claude-opus-5 call per item).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

_JUDGE_DIR = Path(__file__).resolve().parent
_BACKEND_ROOT = _JUDGE_DIR.parents[1]
load_dotenv(_BACKEND_ROOT / ".env")

JUDGE_MODEL = "claude-opus-5"

PROMPT_TEMPLATE = """You are grading a hotel customer-support assistant's response. You did not write this response and have no stake in defending it - grade strictly.

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
Then one sentence explaining why."""

_VERDICT_RE = re.compile(r"VERDICT:\s*(PASS|FAIL|BORDERLINE)", re.IGNORECASE)


def _judge_one(client: Anthropic, item: dict) -> tuple[str, str]:
    prompt = PROMPT_TEMPLATE.format(
        guest_message=item["guest_message"],
        sentiment_label=item["sentiment_label"],
        kb_snippets=json.dumps(item.get("kb_snippets", [])),
        grounded=item["grounded"],
        draft_response=item["draft_response"],
    )
    response = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    # claude-opus-5 may emit a leading ThinkingBlock before the TextBlock -
    # find the first block that actually has text rather than assuming index 0.
    text = next((block.text for block in response.content if hasattr(block, "text")), "")
    match = _VERDICT_RE.search(text)
    verdict = match.group(1).upper() if match else "UNPARSEABLE"
    return verdict, text


def calibrate() -> dict:
    client = Anthropic()
    path = _JUDGE_DIR / "calibration_set.jsonl"
    results = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        verdict, raw = _judge_one(client, item)
        agree = verdict == item["label"]
        results.append(
            {
                "id": item["id"],
                "expected_label": item["label"],
                "judge_verdict": verdict,
                "agree": agree,
                "judge_explanation": raw,
            }
        )
    agreement_rate = sum(r["agree"] for r in results) / len(results) if results else 0.0
    return {
        "mode": "calibrate",
        "judge_model": JUDGE_MODEL,
        "n": len(results),
        "agreement_rate": round(agreement_rate, 3),
        "items": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibrate", action="store_true")
    parser.add_argument("--items", type=str, default=None)
    args = parser.parse_args()

    if args.calibrate:
        print(json.dumps(calibrate(), indent=2))
    elif args.items:
        client = Anthropic()
        items = json.loads(Path(args.items).read_text(encoding="utf-8"))
        out = []
        for item in items:
            verdict, raw = _judge_one(client, item)
            out.append({"id": item.get("id"), "judge_verdict": verdict, "judge_explanation": raw})
        print(json.dumps(out, indent=2))
    else:
        print("Pass --calibrate or --items FILE", file=sys.stderr)
        sys.exit(2)
