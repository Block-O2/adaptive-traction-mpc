"""Run one versioned paired full-3D physical episode; never overwrite outputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import traceback

from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import run_executed_case


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--arm", choices=("continual_adaptive", "commissioning_only", "fixed_population"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    case = json.loads(args.case.read_text(encoding="utf-8"))
    try:
        summary = run_executed_case(args.output, qualification_case=case,
            qualification_arm=args.arm, simulate_planning_latency=True)
    except Exception as error:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "runner_exception.json").write_text(json.dumps({
            "case_path": str(args.case), "arm": args.arm,
            "error": f"{type(error).__name__}: {error}",
            "traceback": traceback.format_exc(),
        }, indent=2) + "\n", encoding="utf-8")
        raise
    print(json.dumps({"case_key": case["case_key"], "arm": args.arm,
                      "status": summary["status"], "abort_reason": summary["abort_reason"],
                      "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
