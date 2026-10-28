"""One old-case DEVELOPMENT replay through the versioned DEV-A lifecycle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import traceback

from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import run_executed_case


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    case = json.loads(args.case.read_text(encoding="utf-8"))
    try:
        summary = run_executed_case(
            args.output, qualification_case=case,
            qualification_arm="continual_adaptive",
            simulate_planning_latency=True,
            formal_qualification=False,
            dev_a_recovery=True,
        )
    except Exception as error:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "runner_exception.json").write_text(
            json.dumps({
                "evidence_category": "development_replay_of_consumed_formal_v1_case",
                "case_path": str(args.case),
                "error": f"{type(error).__name__}: {error}",
                "traceback": traceback.format_exc(),
            }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        raise
    print(json.dumps({
        "case_key": case["case_key"], "status": summary["status"],
        "abort_reason": summary["abort_reason"],
        "recovery": summary["dev_a_recovery"],
        "output": str(args.output),
    }, sort_keys=True, default=lambda value: value.tolist() if hasattr(value, "tolist") else str(value)))


if __name__ == "__main__":
    main()
