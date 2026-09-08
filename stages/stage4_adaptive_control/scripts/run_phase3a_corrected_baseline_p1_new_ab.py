#!/usr/bin/env python3
"""Frozen corrected-baseline Rigid NEW vs P1 NEW study.

The runner executes at most one newly registered trajectory per invocation.  The
already completed rigid 40/80 NEW arm is referenced by hash and is never replayed.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

import numpy as np


REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / "stages/stage4_adaptive_control"
sys.path.insert(0, str(STAGE / "scripts"))

import run_phase3a_control_velocity_path_ab as velocity_ab
import run_progressive_120_120_ab as legacy
from traction_mpc_stage4.sensor_realism import (
    ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY,
)


old = legacy.old
base = legacy.base
SPEC = STAGE / "docs/PHASE3A_CORRECTED_BASELINE_P1_NEW_AB_SPEC.json"
DOC = SPEC.with_suffix(".md")
ROOT = (
    STAGE
    / "results/engineering_validation/corrected_baseline_p1_new_ab_20260908_v1"
)
REUSED_RIGID_40_80 = (
    STAGE
    / "results/engineering_validation/control_velocity_path_ab_20260908_v1"
    / "hip40_knee80_new_velocity_dt0250us"
)
IMPLEMENTATION_FILES = (
    Path(__file__),
    STAGE / "scripts/run_phase3a_control_velocity_path_ab.py",
    STAGE / "scripts/run_progressive_120_120_ab.py",
    STAGE / "scripts/run_stage4_phase3a_soft_qualification.py",
    STAGE / "src/traction_mpc_stage4/measurement.py",
    STAGE / "src/traction_mpc_stage4/sensor_realism.py",
    STAGE / "src/traction_mpc_stage4/executable_command.py",
    STAGE / "src/traction_mpc_stage4/separated_runtime.py",
    REPO / "stages/stage3_full3d/src/traction_mpc_stage3/progressive_interface.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def write(path: Path, value: object) -> None:
    old.write(path, value)


def _assert_ancestor(commit: str) -> None:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
        cwd=REPO,
        check=False,
    )
    assert result.returncode == 0, f"required commit is not an ancestor: {commit}"


def contract() -> dict:
    spec = read(SPEC)
    assert spec["status"] == "FROZEN_USER_AUTHORIZED_CORRECTED_BASELINE_P1_NEW"
    assert spec["checkpoint_commit"] == "0382d3a648138c686392ce5f9686580f01cce9ad"
    _assert_ancestor(spec["checkpoint_commit"])
    _assert_ancestor(spec["velocity_path_implementation_commit"])
    assert spec["physics_dt_s"] == 0.00025
    assert spec["control_substeps"] == 20
    assert spec["low_level_period_s"] == 0.005
    assert spec["measurement_update_rate_hz"] == 200.0
    assert spec["measurement_seed"] == 44104
    assert spec["velocity_feedback_gain_ns_m"] == 140.0
    assert spec["velocity_path"] == "ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY"
    assert spec["candidate"]["id"] == "P1"
    assert len(spec["runs"]) == spec["max_new_runs"] == 5
    assert [
        (run["point"]["endpoint_deg"], run["arm"], run["velocity_path"])
        for run in spec["runs"]
    ] == [
        ([40, 80], "P1", "NEW"),
        ([90, 120], "rigid", "NEW"),
        ([90, 120], "P1", "NEW"),
        ([120, 120], "rigid", "NEW"),
        ([120, 120], "P1", "NEW"),
    ]
    assert all(run["point"]["endpoint_deg"] != [40, 40] for run in spec["runs"])
    for relative, expected in spec["frozen_source_hashes"].items():
        assert sha(REPO / relative) == expected, relative
    for relative, expected in spec["reused_rigid_40_80"]["sha256"].items():
        assert sha(REPO / relative) == expected, relative
    assert not subprocess.check_output(
        ["git", "diff", "--name-only", "HEAD"], cwd=REPO, text=True
    ).strip(), "tracked worktree changes invalidate the frozen run"
    return spec


class RigidNewPlant(legacy.RigidPlant):
    """Rigid plant with the corrected control-only translational velocity path."""

    def __init__(self, human, spec: dict, manager):
        super().__init__(human, spec, manager)
        self.translational_velocity_feedback_source = (
            ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY
        )


class ProgressiveNewPlant(legacy.ProgressivePlant):
    """Registered P1 plant with the same corrected velocity path as rigid."""

    def __init__(self, human, spec: dict, manager):
        super().__init__(human, spec, manager)
        self.translational_velocity_feedback_source = (
            ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY
        )


def _physical_progress(trace: dict, point: dict) -> dict:
    q = np.asarray(trace["human_q_deg_god_view"], dtype=float)
    phase = np.asarray(trace["reference_phase_time_s"], dtype=float)
    initial = np.array([5.0, 10.0])
    target = np.asarray(point["endpoint_deg"], dtype=float)
    span = target - initial
    leg = float(point["outbound_duration_s"])
    outbound_mask = phase <= 1.0 + leg + float(point["target_hold_s"])
    return_mask = phase >= 1.0 + leg + float(point["target_hold_s"])
    outward_joint_progress = (q - initial) / span
    outbound = float(
        100.0
        * np.clip(
            np.max(np.min(outward_joint_progress[outbound_mask], axis=1)), 0.0, 1.0
        )
    )
    return_joint_progress = 1.0 - np.abs((q - initial) / span)
    returned = (
        float(
            100.0
            * np.clip(
                np.max(np.min(return_joint_progress[return_mask], axis=1)),
                0.0,
                1.0,
            )
        )
        if np.any(return_mask)
        else 0.0
    )
    tolerance = 0.06896926724078867
    target_error = np.max(np.abs(q - target), axis=1)
    return_error = np.max(np.abs(q - initial), axis=1)
    return {
        "outbound_percent": outbound,
        "return_percent": returned,
        "target_minimum_max_joint_error_deg": float(np.min(target_error[outbound_mask])),
        "return_minimum_max_joint_error_deg": (
            float(np.min(return_error[return_mask])) if np.any(return_mask) else None
        ),
        "target_reached_within_retained_tolerance": bool(
            np.min(target_error[outbound_mask]) <= tolerance
        ),
        "return_reached_within_retained_tolerance": bool(
            np.any(return_mask) and np.min(return_error[return_mask]) <= tolerance
        ),
        "retained_tolerance_deg": tolerance,
        "semantics": (
            "Conservative minimum per-joint geometric progress, clipped to 0-100%. "
            "The booleans use the retained formal tolerance; no new practical threshold."
        ),
    }


def add_required_metrics(result: dict, trace: dict, run: dict) -> dict:
    result = velocity_ab.add_control_metrics(result, trace, run)
    result["velocity_path"] = "NEW"
    result["physical_trajectory_completion"] = _physical_progress(
        trace, run["point"]
    )
    q = np.asarray(trace["human_q_deg_god_view"], dtype=float)
    q_est = np.asarray(trace["estimated_human_q_deg"], dtype=float)
    proxy_error = q_est - q
    result["state_proxy_error_deg"] = {
        "rms": float(np.sqrt(np.mean(proxy_error**2))),
        "peak": float(np.max(np.abs(proxy_error))),
        "used_for_control": False,
    }
    return result


def run_one(spec: dict, index: int) -> None:
    run = spec["runs"][index]
    output = ROOT / run["id"]
    output.mkdir(exist_ok=False)
    write(
        output / "started.json",
        {
            "command": [sys.executable, *sys.argv],
            "pid": os.getpid(),
            "run": run,
            "spec_sha256": sha(SPEC),
        },
    )
    point = run["point"]
    trajectory = base.NormalizedTrajectory(point)
    plants = []
    matrix = base.load_report_validation_matrix(base.DEFAULT_MATRIX)
    case = base.measurement_case(matrix, measurement_seed=spec["measurement_seed"])
    allocator = base.default_engineering_cuff_allocator()
    manager = base.UnifiedReferenceManager(trajectory.reference, confidence_aware=False)
    supervisor = legacy.DetailedSupervisor()
    monitor = legacy.StopMonitor(plants)
    model_lock = base.CompleteModelLockMonitor(allocator)

    def factory(human):
        plant_class = RigidNewPlant if run["arm"] == "rigid" else ProgressiveNewPlant
        plant = plant_class(human, spec, manager)
        plants.append(plant)
        return plant

    def estimator(measurement, q_prior):
        return base.OnlineSingleChallengerTrustEstimator(
            measurement,
            q_prior,
            measurement_case=case,
            apply_qualified_model=False,
            rom_human=base.HIGH_ROM_HUMAN,
            freeze_control_geometry=True,
        )

    summary = trace = None
    exception = None
    started = time.perf_counter()
    try:
        summary, trace = legacy.make_runtime(run["arm"] == "P1")(
            case,
            duration_s=point["maximum_simulation_duration_s"],
            estimator_architecture="integral_minimal",
            result_case_name=run["id"],
            true_human_override=base.HIGH_ROM_HUMAN,
            true_metadata_override={"case": "nominal_high_rom"},
            reference_fn=trajectory.reference,
            trajectory_label=point["id"],
            trajectory_waypoints=trajectory.waypoints,
            plant_factory=factory,
            reference_execution=manager,
            reference_completion_phase_s=trajectory.duration,
            capture_system_pilot_diagnostics=True,
            track_brake_supervisor=supervisor,
            mpc_factory=lambda: base.HumanSpaceMPC(cuff_allocator=allocator),
            cuff_allocator=allocator,
            estimator_factory=estimator,
            physical_force_supervisor=monitor,
            terminate_on_structural_events=True,
            control_model_cycle_assertion=model_lock,
        )
    except Exception:
        exception = traceback.format_exc()
    elapsed = time.perf_counter() - started
    if not plants:
        raise RuntimeError(exception or "plant_not_created")
    plant = plants[0]
    np.savez_compressed(output / "initial_state.npz", **plant.initial_state)
    write(
        output / "run_config.json",
        {
            "measurement_case": asdict(case),
            "mpc_config": asdict(base.HumanMPCConfig()),
            "human": asdict(base.HIGH_ROM_HUMAN),
            "allocator": asdict(allocator.config),
            "point": point,
            "physics_dt_s": spec["physics_dt_s"],
            "control_substeps": spec["control_substeps"],
            "candidate": spec["candidate"] if run["arm"] == "P1" else None,
            "velocity_path": "NEW",
            "translational_velocity_feedback_source": (
                ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY
            ),
            "velocity_feedback_gain_ns_m": 140.0,
            "single_scientific_variable_within_pair": "rigid_vs_P1_interface",
        },
    )
    write(output / "model_lock.json", model_lock.diagnostics())
    model_lock.save_cycles(output / "model_lock_cycles.npz")
    old.mujoco.mj_saveLastXML(str(output / "model.xml"), plant.model)
    result = legacy.summarize(
        spec,
        run,
        output,
        plant,
        summary,
        trace,
        supervisor,
        elapsed,
        exception,
    )
    if summary is None or trace is None:
        result["stop_reasons"] = list(
            dict.fromkeys(result["stop_reasons"] + ["incomplete_evidence"])
        )
        result["admit_next"] = False
    else:
        result = add_required_metrics(result, trace, run)
    write(output / "result.json", result)
    hard_stop = bool(result["stop_reasons"])
    write(
        ROOT / "campaign_status.json",
        {
            "last_run": run["id"],
            "new_runs_executed": index + 1,
            "stop_reasons": result["stop_reasons"],
            "stop": hard_stop or index == len(spec["runs"]) - 1,
            "remaining_not_run": [item["id"] for item in spec["runs"][index + 1 :]],
        },
    )
    print(
        json.dumps(
            {
                key: result.get(key)
                for key in (
                    "id",
                    "arm",
                    "velocity_path",
                    "task",
                    "termination_reason",
                    "tracking_rmse_deg",
                    "endpoint_error_deg",
                    "return_error_deg",
                    "physical_trajectory_completion",
                    "stop_reasons",
                )
            },
            indent=2,
        ),
        flush=True,
    )


def _brake_count(row: dict) -> int:
    brake = row["brake"]
    return int(brake.get("transition_count", brake.get("brake_entry_count", 0)))


def _pair_rows(spec: dict) -> list[dict]:
    reused = read(REUSED_RIGID_40_80 / "result.json")
    reused["evidence_role"] = "REUSED_HASH_LOCKED_RIGID_NEW_BASELINE"
    rows = [reused]
    for run in spec["runs"]:
        row = read(ROOT / run["id"] / "result.json")
        row["evidence_role"] = "NEW_REGISTERED_RUN"
        rows.append(row)
    return rows


def build_report(spec: dict) -> None:
    rows = _pair_rows(spec)
    pairs: dict[str, dict] = {}
    for endpoint in ([40, 80], [90, 120], [120, 120]):
        key = f"{endpoint[0]}/{endpoint[1]}"
        pairs[key] = {
            row["arm"]: row for row in rows if row["endpoint_deg"] == endpoint
        }
    write(
        ROOT / "comparison.json",
        {
            "spec_sha256": sha(SPEC),
            "reused_rigid_40_80_checkpoint": spec["checkpoint_commit"],
            "pairs": pairs,
        },
    )
    lines = [
        "# Phase-3A corrected baseline: Rigid NEW vs P1 NEW",
        "",
        "Exploratory evidence only. Formal classifications and the prior strict P1 numerical-qualification FAIL are preserved.",
        "",
        "| case | arm | evidence | formal | physical outbound/return % | tracking RMSE deg | endpoint/return deg | Human demand RMS/peak N | position F RMS/peak N | velocity F RMS/peak N | nominal executable RMS/peak N | command RMS/peak N | physical RMS/peak N | force slew RMS/peak N/s | moment peak Nm | SF/FI/BRAKE/NSA | P1 deformation mm/deg |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        control = row["control_feedback"]
        physical = row.get("physical_trajectory_completion")
        if physical is None:
            reference = row["actual_trajectory_completion"]
            physical_text = f"reference {reference['outbound_percent']:.2f}/{reference['return_percent']:.2f}"
        else:
            physical_text = f"{physical['outbound_percent']:.2f}/{physical['return_percent']:.2f}"
        sf = row["safety_filter_interventions"]
        brake = row["brake"]
        lines.append(
            "| {case} | {arm} | {role} | {task} | {progress} | {track:.6f} | {end}/{ret:.6f} | {hd_r:.3f}/{hd_p:.3f} | {pf_r:.3f}/{pf_p:.3f} | {vf_r:.3f}/{vf_p:.3f} | {ne_r:.3f}/{ne_p:.3f} | {cmd_r:.3f}/{cmd_p:.3f} | {phys_r:.3f}/{phys_p:.3f} | {slew_r:.3f}/{slew_p:.3f} | {moment:.3f} | {safe}/{fi}/{brake_count}/{nsa} | {deform:.3f}/{rotation:.3f} |".format(
                case=f"{row['endpoint_deg'][0]}/{row['endpoint_deg'][1]}",
                arm=row["arm"],
                role=row["evidence_role"],
                task=row["task"],
                progress=physical_text,
                track=row["tracking_rmse_deg"],
                end="—" if row["endpoint_error_deg"] is None else f"{row['endpoint_error_deg']:.6f}",
                ret=row["return_error_deg"],
                hd_r=control["human_level_allocator_force_n"]["rms"],
                hd_p=control["human_level_allocator_force_n"]["peak"],
                pf_r=control["position_force_n"]["rms"],
                pf_p=control["position_force_n"]["peak"],
                vf_r=control["velocity_force_n"]["rms"],
                vf_p=control["velocity_force_n"]["peak"],
                ne_r=row["nominal_executable_force_before_filter_n"]["rms"],
                ne_p=row["nominal_executable_force_before_filter_n"]["peak"],
                cmd_r=row["command_force_n"]["rms"],
                cmd_p=row["command_force_n"]["peak"],
                phys_r=row["physical_force_n"]["rms"],
                phys_p=row["physical_force_n"]["peak"],
                slew_r=row["rates"]["physical_force_n_s"]["rms"],
                slew_p=row["rates"]["physical_force_n_s"]["peak"],
                moment=row["physical_moment_R_nm"]["peak"],
                safe=sf["safe_filtered_count"],
                fi=sf["filter_infeasible_count"],
                brake_count=_brake_count(row),
                nsa=row["no_safe_action_count"],
                deform=row["deformation_peak_mm"],
                rotation=row["rotation_peak_deg"],
            )
        )
    lines.extend(
        [
            "",
            "Reference completion and physical geometric progress are reported separately. No new practical completion threshold is introduced.",
            "",
            "No controller, estimator, gain, force threshold, timing, solver, seed, trajectory, Human/robot model, geometry, Safety Filter, BRAKE, or P1 parameter was changed.",
        ]
    )
    (ROOT / "REPORT.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--run-next", action="store_true")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    assert sum((args.freeze, args.run_next, args.report)) == 1
    spec = contract()
    if args.freeze:
        ROOT.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(SPEC, ROOT / SPEC.name)
        shutil.copyfile(DOC, ROOT / DOC.name)
        write(
            ROOT / "registration.json",
            {
                "spec_sha256": sha(SPEC),
                "md_sha256": sha(DOC),
                "checkpoint_commit": spec["checkpoint_commit"],
                "runner_sha256": sha(Path(__file__)),
                "implementation_hashes": {
                    str(path.relative_to(REPO)): sha(path)
                    for path in IMPLEMENTATION_FILES
                },
                "reused_rigid_40_80": spec["reused_rigid_40_80"],
                "command": [sys.executable, *sys.argv],
                "pid": os.getpid(),
                "numpy": np.__version__,
                "mujoco": old.mujoco.__version__,
            },
        )
        print("FROZEN", sha(SPEC))
        return

    registration = read(ROOT / "registration.json")
    assert sha(SPEC) == sha(ROOT / SPEC.name) == registration["spec_sha256"]
    assert sha(DOC) == sha(ROOT / DOC.name) == registration["md_sha256"]
    assert sha(Path(__file__)) == registration["runner_sha256"]
    for relative, expected in registration["implementation_hashes"].items():
        assert sha(REPO / relative) == expected, relative
    completed = 0
    while completed < len(spec["runs"]) and (
        ROOT / spec["runs"][completed]["id"]
    ).exists():
        prior = read(ROOT / spec["runs"][completed]["id"] / "result.json")
        completed += 1
        if completed < len(spec["runs"]):
            assert prior["admit_next"], "campaign stopped; no further run admitted"
    if args.report:
        assert completed == len(spec["runs"]), "all five new registered runs required"
        build_report(spec)
        return
    assert completed < len(spec["runs"]), "no sixth new run"
    print("START", spec["runs"][completed]["id"], flush=True)
    run_one(spec, completed)
    contract()
    for relative, expected in registration["implementation_hashes"].items():
        assert sha(REPO / relative) == expected, relative


if __name__ == "__main__":
    main()
