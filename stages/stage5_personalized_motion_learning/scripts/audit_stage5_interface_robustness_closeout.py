#!/usr/bin/env python3
"""Re-score existing Stage-5 traces under the robustness closeout contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.interface_robustness import (
    load_interface_robustness_contract,
    score_trace,
)


CHECKPOINT_ROOT = (
    STAGE5_ROOT / "results" / "goal_mpc_runtime_v1" / "optimized_attempt_03_final"
)
MISMATCH_ROOT = STAGE5_ROOT / "results" / "interface_mismatch_v1_attempt03"


def _legacy_strict_arrival(trace, summary) -> dict[str, object]:
    time = np.asarray(trace["time_s"], dtype=float)
    q = np.degrees(np.asarray(trace["evaluation_human_q_rad"], dtype=float))
    dq = np.degrees(np.abs(np.asarray(trace["evaluation_human_dq_rad_s"], dtype=float)))
    targets = {"HOLD": np.array([20.0, 35.0]), "COMPLETE": np.array([5.0, 10.0])}
    result = {}
    for phase, target in targets.items():
        event = next(
            (item for item in summary.get("phase_transitions", []) if item["phase"] == phase),
            None,
        )
        if event is None:
            result[phase] = {"available": False, "accepted": False}
            continue
        index = int(np.argmin(np.abs(time - float(event["time_s"]))))
        result[phase] = {
            "available": True,
            "truth_abs_angle_error_deg": np.abs(q[index] - target).tolist(),
            "truth_abs_velocity_deg_s": dq[index].tolist(),
            "accepted": bool(
                np.all(np.abs(q[index] - target) <= 1.0 + 1.0e-12)
                and np.all(dq[index] <= 2.0 + 1.0e-12)
            ),
        }
    result["both_arrivals_accepted"] = bool(
        result["HOLD"]["accepted"] and result["COMPLETE"]["accepted"]
    )
    return result


def _score_directory(path: Path, contract) -> dict[str, object]:
    summary = json.loads((path / "summary.json").read_text(encoding="utf-8"))
    with np.load(path / "trace.npz") as trace:
        score = score_trace(summary, trace, contract)
        strict = _legacy_strict_arrival(trace, summary)
    return {"score": score, "former_strict_1deg_2deg_s_arrival": strict}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STAGE5_ROOT / "results" / "interface_robustness_closeout_v1",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "saved_trace_rescore_final.json"
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    contract = load_interface_robustness_contract()
    rows = [
        {
            "case": "frozen_nominal_checkpoint",
            "source": str(CHECKPOINT_ROOT.relative_to(STAGE5_ROOT)),
            **_score_directory(CHECKPOINT_ROOT, contract),
        }
    ]
    aggregate = json.loads((MISMATCH_ROOT / "sweep_summary.json").read_text())
    cells = {cell["case"]: cell for cell in aggregate["cells"]}
    for case in ("nominal_1p0", "kt_0p7", "kt_1p3", "kr_0p7", "kr_1p3", "d_0p7", "d_1p3"):
        case_root = MISMATCH_ROOT / case
        row: dict[str, object] = {
            "case": case,
            "source": str(case_root.relative_to(STAGE5_ROOT)),
        }
        if (case_root / "trace.npz").exists():
            row.update(_score_directory(case_root, contract))
        else:
            cell = cells[case]
            row.update(
                {
                    "score": {
                        "online_result": cell["task_status"],
                        "abort_reason": cell["abort_reason"],
                        "online_complete": False,
                        "evaluation_truth_complete": False,
                        "evaluation_acceptance": False,
                        "false_complete": False,
                        "false_negative_constraint_violation": False,
                        "false_positive_abort": False,
                        "initialization_failure": True,
                        "motion_envelope": {
                            "online_peak_velocity_deg_s": cell["peak_estimated_velocity_deg_s"],
                            "truth_peak_velocity_deg_s": cell["peak_truth_velocity_deg_s"],
                            "online_peak_acceleration_deg_s2": cell["peak_deployable_acceleration_deg_s2"],
                            "truth_peak_acceleration_deg_s2": cell["peak_truth_acceleration_deg_s2"],
                        },
                        "physical": {
                            "peak_force_n": cell["peak_physical_force_n"],
                            "cumulative_force_n_s": cell["cumulative_physical_force_n_s"],
                            "peak_moment_nm": cell["peak_physical_moment_nm"],
                        },
                        "truth_used_online": False,
                    },
                    "former_strict_1deg_2deg_s_arrival": {
                        "available": False,
                        "accepted": False,
                    },
                }
            )
        rows.append(row)
    result = {
        "schema": "stage5_interface_robustness_saved_trace_rescore_v1",
        "new_mujoco_episodes": 0,
        "contract": str(
            (STAGE5_ROOT / "configs" / "stage5_interface_robustness_v1.json").relative_to(STAGE5_ROOT)
        ),
        "rows": rows,
        "truth_used_online": False,
        "historical_outputs_modified": False,
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
