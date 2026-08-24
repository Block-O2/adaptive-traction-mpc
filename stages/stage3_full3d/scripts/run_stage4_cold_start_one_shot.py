from __future__ import annotations

import argparse
import json
from pathlib import Path

from traction_mpc_stage4.cold_start import (
    COLD_START_TEACHING_DURATION_S,
    COLD_START_VALIDATION_DURATION_S,
    cold_start_mechanically_viable,
    run_cold_start_adaptive_case,
    save_case,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--skip-final", action="store_true")
    parser.add_argument(
        "--final-only",
        action="store_true",
        help="Run the one final trajectory after viable validations already exist in output-dir.",
    )
    args = parser.parse_args()
    if args.skip_final and args.final_only:
        parser.error("--skip-final and --final-only are mutually exclusive")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.final_only:
        summary_path = args.output_dir / "run_summary.json"
        if not summary_path.exists():
            raise RuntimeError("--final-only requires an existing validation run_summary.json")
        combined = json.loads(summary_path.read_text(encoding="utf-8"))
        validation = combined.get("cold_start_validation", {})
        if set(validation) != {"nominal", "cold_start_perturbed"} or not all(
            bool(item.get("mechanically_viable")) for item in validation.values()
        ):
            raise RuntimeError("cold-start validations are absent or not mechanically viable")
        summary, trace = run_cold_start_adaptive_case(
            true_case="cold_start_perturbed",
            duration_s=COLD_START_TEACHING_DURATION_S,
        )
        save_case(args.output_dir, "high_flexion_one_shot_adaptive", summary, trace)
        combined["final_run_started"] = True
        combined["final_run_mechanically_completed"] = bool(
            summary["mechanically_completed_requested_duration"]
        )
        combined["final_summary_file"] = "high_flexion_one_shot_adaptive.json"
        summary_path.write_text(
            json.dumps(combined, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return

    validation = {}
    viable = True
    for case in ("nominal", "cold_start_perturbed"):
        summary, trace = run_cold_start_adaptive_case(
            true_case=case, duration_s=COLD_START_VALIDATION_DURATION_S
        )
        name = f"cold_start_validation_{case}"
        save_case(args.output_dir, name, summary, trace)
        mechanical = cold_start_mechanically_viable(summary)
        validation[case] = {
            "mechanically_viable": mechanical,
            "summary_file": f"{name}.json",
        }
        viable = viable and mechanical

    combined = {
        "cold_start_validation": validation,
        "final_run_started": False,
    }
    if viable and not args.skip_final:
        summary, trace = run_cold_start_adaptive_case(
            true_case="cold_start_perturbed",
            duration_s=COLD_START_TEACHING_DURATION_S,
        )
        save_case(args.output_dir, "high_flexion_one_shot_adaptive", summary, trace)
        combined["final_run_started"] = True
        combined["final_run_mechanically_completed"] = bool(
            summary["mechanically_completed_requested_duration"]
        )
        combined["final_summary_file"] = "high_flexion_one_shot_adaptive.json"
    (args.output_dir / "run_summary.json").write_text(
        json.dumps(combined, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
