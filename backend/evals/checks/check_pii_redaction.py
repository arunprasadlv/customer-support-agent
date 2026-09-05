"""Code-based eval check for the security dimension (EC-005, AC-007/FR-011).

Reuses the real `detect_pii` function from `app.tools.pii_detector` — never
reimplements the regex patterns. Verifies two properties per item:
1. Every expected entity_type is present in `redaction_actions`.
2. No raw PII substring from the original text survives into `clean_text`
   (the actual security property FR-011 requires, not just "some action
   was recorded" — a detector could record an action but redact the wrong
   span, which this check would catch and the entity-type check alone
   would not).

Run from `backend/` with `backend/.venv`'s python:
    python ../evals/checks/check_pii_redaction.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend" / "src"))

from app.tools.pii_detector import detect_pii  # noqa: E402

DATASET_PATH = Path(__file__).resolve().parents[1] / "dataset" / "security_pii_redaction.jsonl"


def run() -> dict:
    results = []
    for line in DATASET_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        result = detect_pii(item["raw_text"])
        detected_types = sorted({a.entity_type for a in result.redaction_actions})
        expected_types = sorted(item["expected_entity_types"])
        types_match = detected_types == expected_types

        # Confirm every redacted span's original substring is gone from clean_text.
        no_leak = True
        for action in result.redaction_actions:
            original_span = item["raw_text"][action.span_start : action.span_end]
            if original_span and original_span in result.clean_text:
                no_leak = False

        passed = types_match and no_leak
        results.append(
            {
                "id": item["id"],
                "expected_entity_types": expected_types,
                "detected_entity_types": detected_types,
                "no_leak_into_clean_text": no_leak,
                "clean_text": result.clean_text,
                "pass": passed,
                "notes": item.get("notes", ""),
            }
        )
    return {
        "check": "pii_redaction",
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
