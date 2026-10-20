"""Restart-safe DEV-C replay of already-consumed full-3D development cases.

This runner never converts a historical qualification case into fresh evidence.
Each completed/failed run is retained in a unique DEV-C output directory.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import traceback

from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import run_executed_case


def _write_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case-keys", nargs="*")
    args = parser.parse_args()
    case_files = sorted(args.cases.glob("*.json")) if args.cases.is_dir() else [args.cases]
    if args.case_keys:
        requested = set(args.case_keys)
        case_files = [path for path in case_files if path.stem in requested]
        if {path.stem for path in case_files} != requested:
            raise ValueError("one or more requested case keys have no case JSON")
    if not case_files:
        raise ValueError("no development cases selected")
    args.output.mkdir(parents=True, exist_ok=True)
    state = {
        "schema": "full3d_dev_c_development_batch_v1",
        "evidence_category": "development_replay_of_consumed_formal_v1_cases",
        "source_case_directory": str(args.cases),
        "case_keys": [path.stem for path in case_files],
        "completed_case_keys": [],
        "rows": [],
    }
    _write_json(args.output / "batch_status.json", state)
    for case_path in case_files:
        case = json.loads(case_path.read_text(encoding="utf-8"))
        if args.cases.is_dir() and case["case_key"] != case_path.stem:
            raise ValueError(f"case key mismatch: {case_path}")
        key = str(case["case_key"])
        output = args.output / key
        summary_path = output / "summary.json"
        exception_path = output / "runner_exception.json"
        if summary_path.exists():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            row = {"case_key": key, "status": summary["status"],
                   "abort_reason": summary.get("abort_reason"),
                   "recovery_entered": summary.get("dev_a_recovery", {}).get("entered"),
                   "recovery_succeeded": summary.get("dev_a_recovery", {}).get("succeeded"),
                   "latest_accepted_version": summary.get("dev_c_model_transfer", {}).get("latest_accepted_version"),
                   "fully_realized_version": summary.get("dev_c_model_transfer", {}).get("last_fully_realized_version"),
                   "resumed_existing_artifact": True}
        elif exception_path.exists():
            row = {"case_key": key, "status": "PRESERVED_RUNNER_EXCEPTION",
                   "abort_reason": json.loads(exception_path.read_text(encoding="utf-8"))["error"],
                   "resumed_existing_artifact": True}
        else:
            try:
                summary = run_executed_case(
                    output, qualification_case=case,
                    qualification_arm="continual_adaptive",
                    simulate_planning_latency=True, formal_qualification=False,
                    dev_a_recovery=True, dev_c_bumpless_transfer=True,
                )
                row = {"case_key": key, "status": summary["status"],
                       "abort_reason": summary.get("abort_reason"),
                       "recovery_entered": summary["dev_a_recovery"]["entered"],
                       "recovery_succeeded": summary["dev_a_recovery"]["succeeded"],
                       "latest_accepted_version": summary["dev_c_model_transfer"]["latest_accepted_version"],
                       "fully_realized_version": summary["dev_c_model_transfer"]["last_fully_realized_version"],
                       "resumed_existing_artifact": False}
            except Exception as error:
                output.mkdir(parents=True, exist_ok=True)
                _write_json(exception_path, {
                    "evidence_category": state["evidence_category"],
                    "case_path": str(case_path),
                    "error": f"{type(error).__name__}: {error}",
                    "traceback": traceback.format_exc(),
                })
                row = {"case_key": key, "status": "PRESERVED_RUNNER_EXCEPTION",
                       "abort_reason": f"{type(error).__name__}: {error}",
                       "resumed_existing_artifact": False}
        state["rows"].append(row)
        state["completed_case_keys"].append(key)
        _write_json(args.output / "batch_status.json", state)
        print(json.dumps(row, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
