"""Live eval check for the accuracy dimension (EC-001) and latency
observability (EC-006/EC-007) — calls the real `run_inquiry()` entry point
(`app.flows.inquiry_flow`), the same one `POST /chat` uses, so this
exercises the full 5-agent pipeline against live Anthropic API calls.

Costs real API calls. Not run automatically by `evals/run.py` unless
`--live` is passed, per this project's low-stakes/no-cost-ceiling operator
answer (Step 2) — cost isn't gated, but live calls still aren't free, so
they're opt-in rather than run on every invocation.

Run from `backend/` with `backend/.venv`'s python (ANTHROPIC_API_KEY must
be set, e.g. via `backend/.env` + python-dotenv, already loaded by
`app.main` at import time):
    python ../evals/checks/check_live_accuracy.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_BACKEND_SRC = Path(__file__).resolve().parents[3] / "backend" / "src"
sys.path.insert(0, str(_BACKEND_SRC))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[3] / "backend" / ".env")

from app.flows.inquiry_flow import run_inquiry  # noqa: E402

DATASET_DIR = Path(__file__).resolve().parents[1] / "dataset"
DATASETS = ["accuracy_grounded.jsonl", "accuracy_ungrounded.jsonl"]

LATENCY_TARGET_S = 5.0  # sad.md §7 p95 target
LATENCY_CEILING_S = 10.0  # sad.md §7 stated hard ceiling (code currently uses 30s - known defect, see qa.md)


def _load_items() -> list[dict]:
    items = []
    for name in DATASETS:
        path = DATASET_DIR / name
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                items.append(json.loads(line))
    return items


def run() -> dict:
    results = []
    for item in _load_items():
        start = time.monotonic()
        outcome = run_inquiry(
            channel=item["channel"],
            raw_text=item["message"],
            sender_id=f"eval-{item['id']}",
        )
        duration_s = time.monotonic() - start

        expected_escalated = item.get("expected_escalated")
        expected_grounded = item.get("expected_grounded")
        escalated_ok = expected_escalated is None or outcome.get("escalated") == expected_escalated
        # `run_inquiry`'s response payload doesn't expose `grounded` directly
        # (it's internal to the reasoning Crew) - grounded is inferred here
        # from escalated=False implying a grounded, non-escalated reply, and
        # from the KB-coverage design of the dataset itself; a true
        # `grounded` field would need `run_inquiry` to surface it, which is
        # out of this eval action's scope to add (see evals.md Future Work).
        results.append(
            {
                "id": item["id"],
                "message": item["message"],
                "escalated": outcome.get("escalated"),
                "expected_escalated": expected_escalated,
                "escalated_pass": escalated_ok,
                "reply": outcome.get("reply"),
                "reason": outcome.get("reason"),
                "duration_s": round(duration_s, 2),
                "meets_latency_target": duration_s <= LATENCY_TARGET_S,
                "within_latency_ceiling": duration_s <= LATENCY_CEILING_S,
                "expected_grounded": expected_grounded,
            }
        )
    durations = sorted(r["duration_s"] for r in results)
    p50 = durations[len(durations) // 2] if durations else None
    p95_index = max(0, int(len(durations) * 0.95) - 1)
    p95 = durations[p95_index] if durations else None
    return {
        "check": "live_accuracy_and_latency",
        "total": len(results),
        "escalation_passed": sum(r["escalated_pass"] for r in results),
        "latency_p50_s": p50,
        "latency_p95_s": p95,
        "meets_5s_target_count": sum(r["meets_latency_target"] for r in results),
        "within_10s_ceiling_count": sum(r["within_latency_ceiling"] for r in results),
        "items": results,
    }


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, indent=2, default=str))
