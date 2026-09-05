"""Code-based eval check for the escalation dimension (EC-002, EC-003).

Reuses the real production functions (`evaluate_escalation`,
`contains_dispute_language` from `app.flows.escalation_gate`) rather than
reimplementing threshold/phrase-match logic — per run-evals SKILL.md Step 4
("default to code-based wherever the behavior allows it") and to guarantee
the eval suite can never silently drift from the shipped decision logic.

This is a product-acceptance-level eval (traces to AC-002/AC-003/ADR-002
Addendum), distinct in purpose from `tests/unit/test_escalation_gate.py`'s
much larger unit-test suite (42 cases) even though both call the same
functions — the eval suite is what `evals.md`/Deliver cites as behavioral
evidence, and is expected to be re-run after any prompt/model change, not
just after a code change.

Run from `backend/` with `backend/.venv`'s python:
    python ../evals/checks/check_escalation_logic.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend" / "src"))

from app.flows.escalation_gate import contains_dispute_language, evaluate_escalation  # noqa: E402

DATASET_PATH = Path(__file__).resolve().parents[1] / "dataset" / "safety_escalation_logic.jsonl"


def run() -> dict:
    results = []
    for line in DATASET_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        dispute_detected = contains_dispute_language(item["text_for_dispute_check"])
        decision = evaluate_escalation(
            confidence=item["confidence"],
            sentiment_score=item["sentiment_score"],
            grounded=item["grounded"],
            dispute_language_detected=dispute_detected,
        )
        passed = decision == item["expected_decision"]
        results.append(
            {
                "id": item["id"],
                "expected": item["expected_decision"],
                "actual": decision,
                "dispute_language_detected": dispute_detected,
                "pass": passed,
                "reason": item.get("reason", ""),
            }
        )
    return {
        "check": "escalation_logic",
        "total": len(results),
        "passed": sum(r["pass"] for r in results),
        "failed": [r for r in results if not r["pass"]],
        "items": results,
    }


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, indent=2))
    print(f"\n{report['passed']}/{report['total']} passed")
    if report["failed"]:
        sys.exit(1)
