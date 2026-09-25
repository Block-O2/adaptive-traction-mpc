"""Restart-safe DEV-D physical development runs on versioned assemblies."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import traceback

import mujoco

from run_rigid_table_development_v1 import ContactIntervalMonitor, write_json
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import run_executed_case
from traction_mpc_stage5.rigid_table_assembly_v1 import assess_assembly


STAGE = Path(__file__).resolve().parents[1]
OLD_BASE = STAGE / "results/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1"
ASSEMBLY = OLD_BASE / "assembly_v2"
NOMINAL = (STAGE / "configs/full3d_adaptive_integration_v1/rigid_table_assembly_repair_v1"
           / "nominal_reference_rigid_table_v1.json")


def run_one(case_path: Path, output: Path, *, autonomous_recovery_options: dict | None = None,
            runtime_capture: dict | None = None,
            qualification_contract: str | None = None) -> dict:
    case = json.loads(case_path.read_text())
    screen = assess_assembly(case)
    if not screen["valid"]:
        raise ValueError(f"initial assembly invalid: {screen['category']}: {screen['reason']}")
    monitor = ContactIntervalMonitor()
    mujoco.mj_step2 = monitor.observed
    summary = None
    error = None
    try:
        summary = run_executed_case(
            output, qualification_case=case, qualification_arm="continual_adaptive",
            simulate_planning_latency=True, formal_qualification=qualification_contract is not None,
            qualification_contract=qualification_contract,
            dev_a_recovery=True, dev_c_bumpless_transfer=False,
            dev_d_rigid_table_reference=True,
            autonomous_recovery_options=autonomous_recovery_options,
            runtime_capture=runtime_capture,
        )
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc),
                 "traceback": traceback.format_exc()}
    finally:
        mujoco.mj_step2 = monitor.native
    output.mkdir(parents=True, exist_ok=True)
    contact = monitor.save(output)
    write_json(output / "dev_d_run_manifest.json", {
        "schema": "dev_d_rigid_table_reference_development_v1",
        "case_path": str(case_path),
        "case_sha256": hashlib.sha256(case_path.read_bytes()).hexdigest(),
        "autonomous_recovery_options": autonomous_recovery_options,
        "command": sys.argv, "assembly_screen": screen,
        "controller_flags": {"dev_a_recovery": True,
                             "dev_c_bumpless_transfer": False,
                             "dev_d_rigid_table_reference": True,
                             "simulate_planning_latency": True,
                             "formal_qualification": qualification_contract is not None,
                             "qualification_contract": qualification_contract,
                             "qualification_arm": "continual_adaptive"},
        "physical_contact_monitor": "post-mj_step2 native interval; evaluation only",
        "summary_status": None if summary is None else summary["status"],
        "runner_error": error,
    })
    if error:
        write_json(output / "runner_exception.json", error)
    return {"case_key": case["case_key"],
            "status": (summary["status"] if summary else "PRESERVED_RUNNER_EXCEPTION"),
            "abort_reason": (summary.get("abort_reason") if summary else error["message"]),
            "commissioning_completed": bool(summary and summary.get("commissioning")),
            "recovery_entered": (summary.get("dev_a_recovery", {}).get("entered") if summary else None),
            "recovery_succeeded": (summary.get("dev_a_recovery", {}).get("succeeded") if summary else None),
            "task_interval_count": (summary.get("task", {}).get("integration_interval_count") if summary else None),
            "thigh_normal_peak_n": contact["contacts"]["thigh"]["normal_peak_n"],
            "shank_normal_peak_n": contact["contacts"]["shank"]["normal_peak_n"],
            "physical_interval_count": contact["physical_interval_count"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case-keys", nargs="+", required=True)
    args = parser.parse_args()
    mapping = json.loads((ASSEMBLY / "OLD_TO_NEW_CASE_MAPPING.json").read_text())
    valid = {row["case_key"] for row in mapping if row["v2_validity"]["valid"]}
    valid.add("nominal_reference_rigid_table_v1")
    requested = list(dict.fromkeys(args.case_keys))
    if any(key not in valid for key in requested):
        raise ValueError("requested key has no initial-valid versioned assembly")
    args.output.mkdir(parents=True, exist_ok=True)
    batch = {"schema": "dev_d_rigid_table_reference_development_batch_v1",
             "evidence_category": "consumed_old24_development_not_fresh",
             "selected_case_keys": requested, "rows": []}
    for key in requested:
        case_path = NOMINAL if key == "nominal_reference_rigid_table_v1" else ASSEMBLY / "cases" / f"{key}.json"
        output = args.output / key
        if (output / "dev_d_run_manifest.json").exists():
            row = {"case_key": key, "status": "RESUMED_EXISTING_ARTIFACT",
                   "resumed_existing_artifact": True}
        elif output.exists() and any(output.iterdir()):
            row = {"case_key": key, "status": "INCOMPLETE_INTERRUPTED_ARTIFACT_PRESERVED",
                   "resumed_existing_artifact": True}
        else:
            row = run_one(case_path, output)
            row["resumed_existing_artifact"] = False
        batch["rows"].append(row)
        write_json(args.output / "batch_status.json", batch)
        print(json.dumps(row, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
