"""AAMAD eval suite runner for customer-support-agent.

Default (no flags): runs only the free, deterministic code-based checks
(escalation logic, PII redaction) - no API calls, no cost.

`--live`: also runs the live accuracy/latency check against the real
5-agent pipeline (real Anthropic API calls - not free, no cost ceiling
was set for this MVP per the operator's Step 2 answer, but it isn't run
by default to avoid surprise spend).

`--judge-calibrate`: also runs the LLM-as-judge calibration pass against
`judge/calibration_set.jsonl` (real claude-opus-5 API calls).

Run from `backend/` with `backend/.venv`'s python:
    python ../evals/run.py [--live] [--judge-calibrate]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent


def _run_script(relpath: str, *extra_args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(EVALS_DIR / relpath), *extra_args],
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):  # 1 = check ran but found failures
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"{relpath} crashed (exit {result.returncode})")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        # check_escalation_logic.py / check_pii_redaction.py print a trailing
        # "N/M passed" line after the JSON block - take the JSON prefix only.
        json_text = result.stdout.rsplit("\n\n", 1)[0]
        return json.loads(json_text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Run live accuracy/latency check (costs API calls)")
    parser.add_argument("--judge-calibrate", action="store_true", help="Run judge calibration (costs API calls)")
    args = parser.parse_args()

    report = {"code_based_checks": {}, "live_checks": {}, "judge": {}}

    print("Running code-based checks (free, deterministic)...")
    report["code_based_checks"]["escalation_logic"] = _run_script("checks/check_escalation_logic.py")
    report["code_based_checks"]["pii_redaction"] = _run_script("checks/check_pii_redaction.py")

    if args.live:
        print("Running live accuracy/latency check (real API calls)...")
        report["live_checks"]["accuracy_and_latency"] = _run_script("checks/check_live_accuracy.py")

    if args.judge_calibrate:
        print("Running judge calibration (real API calls)...")
        report["judge"]["calibration"] = _run_script("judge/run_judge.py", "--calibrate")

    out_path = EVALS_DIR / "last_run_report.json"
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nFull report written to {out_path}")

    esc = report["code_based_checks"]["escalation_logic"]
    pii = report["code_based_checks"]["pii_redaction"]
    print(f"\nescalation_logic: {esc['passed']}/{esc['total']} passed")
    print(f"pii_redaction:    {pii['passed']}/{pii['total']} passed")
    if args.live:
        acc = report["live_checks"]["accuracy_and_latency"]
        print(f"live escalation:  {acc['escalation_passed']}/{acc['total']} passed")
        print(f"latency p50/p95:  {acc['latency_p50_s']}s / {acc['latency_p95_s']}s")
    if args.judge_calibrate:
        cal = report["judge"]["calibration"]
        print(f"judge agreement:  {cal['agreement_rate'] * 100:.1f}% (n={cal['n']})")


if __name__ == "__main__":
    main()
