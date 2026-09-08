#!/usr/bin/env python3
"""Frozen OLD/NEW robot control-velocity A/B; one fresh case per invocation."""

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

import run_progressive_40_80_ab as legacy
from traction_mpc_stage4.sensor_realism import (
    PROCESSED_POSE_HISTORY_VELOCITY,
    ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY,
)


old = legacy.old
base = legacy.base
SPEC = STAGE / "docs/PHASE3A_CONTROL_VELOCITY_PATH_AB_SPEC.json"
DOC = SPEC.with_suffix(".md")
ROOT = STAGE / "results/engineering_validation/control_velocity_path_ab_20260908_v1"
IMPLEMENTATION_FILES = (
    STAGE / "src/traction_mpc_stage4/measurement.py",
    STAGE / "src/traction_mpc_stage4/sensor_realism.py",
    STAGE / "src/traction_mpc_stage4/executable_command.py",
    STAGE / "src/traction_mpc_stage4/separated_runtime.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def write(path: Path, value: object) -> None:
    old.write(path, value)


def contract() -> dict:
    spec = read(SPEC)
    assert spec["status"] == "FROZEN_USER_AUTHORIZED_EXPLORATORY_40_40_40_80_ONLY"
    assert spec["physics_dt_s"] == 0.00025
    assert spec["control_substeps"] == 20
    assert spec["low_level_period_s"] == 0.005
    assert spec["measurement_update_rate_hz"] == 200.0
    assert spec["measurement_seed"] == 44104
    assert len(spec["runs"]) == spec["max_runs"] == 4
    assert [
        (run["point"]["endpoint_deg"], run["velocity_path"])
        for run in spec["runs"]
    ] == [
        ([40, 40], "OLD"),
        ([40, 40], "NEW"),
        ([40, 80], "OLD"),
        ([40, 80], "NEW"),
    ]
    assert all(run["arm"] == "rigid" for run in spec["runs"])
    for relative, expected in spec["frozen_source_hashes"].items():
        assert sha(REPO / relative) == expected, relative
    ancestor = subprocess.run(
        [
            "git",
            "merge-base",
            "--is-ancestor",
            spec["implementation_commit"],
            "HEAD",
        ],
        cwd=REPO,
        check=False,
    )
    assert ancestor.returncode == 0, "implementation commit is not an ancestor"
    assert not subprocess.check_output(
        ["git", "diff", "--name-only", "HEAD"], cwd=REPO, text=True
    ).strip(), "tracked worktree changes invalidate the frozen run"
    return spec


class RigidVelocityPlant(legacy.DiagnosticMixin, base.SensorBoundaryStage4Plant):
    """Rigid frozen plant with only the velocity measurement source selected."""

    is_progressive = False

    def __init__(self, human, spec: dict, manager, velocity_path: str):
        self.setup(spec, manager)
        self.commands: list[dict] = []
        source = (
            PROCESSED_POSE_HISTORY_VELOCITY
            if velocity_path == "OLD"
            else ROBOT_JOINT_CUFF_JACOBIAN_VELOCITY
        )
        super().__init__(
            human,
            attachment_from_cuff=old.ENGINEERING_ATTACHMENT_FROM_CUFF,
            engineering_scenario=old.SUSPENDED_SEATED_LIKE_SCENARIO,
            translational_velocity_feedback_source=source,
        )
        self.model.opt.timestep = spec["physics_dt_s"]
        self.capture_enabled = True

    def apply_executable_command(self, preview):
        super().apply_executable_command(preview)
        self.commands.append(
            {
                "time_s": float(self.data.time),
                "force": preview.force_total_n.copy(),
                "moment": preview.moment_total_nm.copy(),
                "torque": preview.joint_torque_command_nm.copy(),
                "ctrl": self.data.ctrl.copy(),
            }
        )


def metric(values: np.ndarray, times: np.ndarray) -> dict[str, float | None]:
    values = np.asarray(values)
    times = np.asarray(times)
    if not len(values):
        return {"rms": None, "peak": None}
    return legacy.vector_metrics(values, times)


def scalar_metric(values: np.ndarray) -> dict[str, float | None]:
    values = np.asarray(values, dtype=float)
    if not len(values):
        return {"rms": None, "peak": None}
    return {
        "rms": float(np.sqrt(np.mean(values**2))),
        "peak": float(np.max(np.abs(values))),
    }


def add_control_metrics(result: dict, trace: dict, run: dict) -> dict:
    control_time = trace["control_time_s"]
    point = run["point"]
    leg = float(point["outbound_duration_s"])
    phase = trace["reference_phase_time_s"]
    maximum_phase = float(np.max(phase))
    result["velocity_path"] = run["velocity_path"]
    result["actual_trajectory_completion"] = {
        "outbound_percent": float(
            100.0 * np.clip((maximum_phase - 1.0) / leg, 0.0, 1.0)
        ),
        "return_percent": float(
            100.0
            * np.clip((maximum_phase - (2.5 + leg)) / leg, 0.0, 1.0)
        ),
        "formal_completion_tolerance_deg": 0.06896926724078867,
        "formal_classification": result["task"],
    }
    result["control_feedback"] = {
        "velocity_force_n": metric(
            trace["executable_force_velocity_world_n"], control_time
        ),
        "raw_velocity_force_n": metric(
            trace["executable_raw_force_velocity_world_n"], control_time
        ),
        "position_force_n": metric(
            trace["executable_force_position_world_n"], control_time
        ),
        "raw_position_force_n": metric(
            trace["executable_raw_force_position_world_n"], control_time
        ),
        "human_level_allocator_force_n": metric(
            trace["executable_force_allocator_world_n"], control_time
        ),
        "target_velocity_m_s": metric(
            trace["control_velocity_target_world_m_s"], control_time
        ),
        "old_processed_velocity_m_s": metric(
            trace["control_velocity_processed_world_m_s"], control_time
        ),
        "new_joint_jacobian_velocity_m_s": metric(
            trace["control_velocity_joint_jacobian_world_m_s"], control_time
        ),
        "selected_velocity_m_s": metric(
            trace["control_velocity_selected_world_m_s"], control_time
        ),
        "equivalent_old_minus_new_history_force_n": metric(
            trace["equivalent_history_velocity_force_delta_world_n"],
            control_time,
        ),
        "maximum_signal_age_ms": float(
            1000.0
            * np.max(
                control_time - trace["control_velocity_sample_time_s"]
            )
        ),
        "frame": "WORLD",
        "reference_point": "registered 140 mm cuff center",
        "gain_ns_per_m": 140.0,
    }
    result["nominal_executable_force_before_filter_n"] = scalar_metric(
        trace["safety_filter_nominal_executable_force_norm_n"]
    )
    statuses = trace["safety_filter_status"].astype(str)
    result["safety_filter_interventions"] = {
        "sample_count": int(len(statuses)),
        "safe_filtered_count": int(np.count_nonzero(statuses == "SAFE_FILTERED")),
        "filter_infeasible_count": int(
            np.count_nonzero(statuses == "FILTER_INFEASIBLE")
        ),
        "peak_force_intervention_n": float(
            np.max(trace["safety_filter_force_intervention_norm_n"], initial=0.0)
        ),
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
    plants: list[RigidVelocityPlant] = []
    matrix = base.load_report_validation_matrix(base.DEFAULT_MATRIX)
    case = base.measurement_case(matrix, measurement_seed=spec["measurement_seed"])
    allocator = base.default_engineering_cuff_allocator()
    manager = base.UnifiedReferenceManager(trajectory.reference, confidence_aware=False)
    supervisor = legacy.DetailedSupervisor()
    monitor = legacy.StopMonitor(plants)
    model_lock = base.CompleteModelLockMonitor(allocator)

    def factory(human):
        plant = RigidVelocityPlant(human, spec, manager, run["velocity_path"])
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
        summary, trace = legacy.make_runtime(False)(
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
            "velocity_path": run["velocity_path"],
            "single_scientific_variable": spec["single_variable"],
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
        result = add_control_metrics(result, trace, run)
    write(output / "result.json", result)
    hard_stop = bool(result["stop_reasons"])
    write(
        ROOT / "campaign_status.json",
        {
            "last_run": run["id"],
            "runs_executed": index + 1,
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
                    "velocity_path",
                    "task",
                    "termination_reason",
                    "tracking_rmse_deg",
                    "endpoint_error_deg",
                    "return_error_deg",
                    "stop_reasons",
                )
            },
            indent=2,
        ),
        flush=True,
    )


def build_report(spec: dict) -> None:
    results = [read(ROOT / run["id"] / "result.json") for run in spec["runs"]]
    pairs = {}
    for endpoint in ([40, 40], [40, 80]):
        selected = [row for row in results if row["endpoint_deg"] == endpoint]
        pairs[f"{endpoint[0]}/{endpoint[1]}"] = {
            row["velocity_path"]: row for row in selected
        }
    write(ROOT / "comparison.json", {"spec_sha256": sha(SPEC), "pairs": pairs})
    lines = [
        "# Phase-3A Robot Control Velocity Path A/B",
        "",
        "Exploratory diagnostic evidence only. Formal classifications are preserved.",
        "",
        "| case | path | formal | outbound % | return % | tracking RMSE deg | endpoint deg | return deg | velocity F RMS/peak N | command peak N | physical peak N | BRAKE entries | FILTER_INFEASIBLE |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in results:
        completion = row["actual_trajectory_completion"]
        velocity = row["control_feedback"]["velocity_force_n"]
        safety = row["safety_filter_interventions"]
        brake = row["brake"]
        lines.append(
            "| {case} | {path} | {task} | {out:.2f} | {ret:.2f} | {track:.6f} | {end} | {back:.6f} | {vr:.3f}/{vp:.3f} | {cmd:.3f} | {phys:.3f} | {brake_count} | {fi} |".format(
                case=f"{row['endpoint_deg'][0]}/{row['endpoint_deg'][1]}",
                path=row["velocity_path"],
                task=row["task"],
                out=completion["outbound_percent"],
                ret=completion["return_percent"],
                track=row["tracking_rmse_deg"],
                end="—" if row["endpoint_error_deg"] is None else f"{row['endpoint_error_deg']:.6f}",
                back=row["return_error_deg"],
                vr=velocity["rms"],
                vp=velocity["peak"],
                cmd=row["command_force_n"]["peak"],
                phys=row["physical_force_n"]["peak"],
                brake_count=brake.get("brake_entry_count", brake.get("entry_count", 0)),
                fi=safety["filter_infeasible_count"],
            )
        )
    lines.extend(
        [
            "",
            "No controller, model, gain, force threshold, timing, trajectory, or completion tolerance was changed.",
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
                "implementation_commit": spec["implementation_commit"],
                "runner_sha256": sha(Path(__file__)),
                "implementation_hashes": {
                    str(path.relative_to(REPO)): sha(path)
                    for path in IMPLEMENTATION_FILES
                },
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
    while completed < len(spec["runs"]) and (ROOT / spec["runs"][completed]["id"]).exists():
        prior = read(ROOT / spec["runs"][completed]["id"] / "result.json")
        completed += 1
        if completed < len(spec["runs"]):
            assert prior["admit_next"], "campaign stopped; no further run admitted"
    if args.report:
        assert completed == len(spec["runs"]), "all four registered runs are required"
        build_report(spec)
        return
    assert completed < len(spec["runs"]), "no fifth run"
    print("START", spec["runs"][completed]["id"], flush=True)
    run_one(spec, completed)
    contract()


if __name__ == "__main__":
    main()
