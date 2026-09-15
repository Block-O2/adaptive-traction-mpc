#!/usr/bin/env python3
"""Execute the user-authorized, preregistered Interface Robustness campaign.

This runner freezes a source/config fingerprint before the first episode and
refuses to continue if any fingerprinted implementation file changes.  It does
not modify controller parameters, costs, constraints, or online authority.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable

import numpy as np

from traction_mpc_stage4.mpc import HumanMPCConfig
from traction_mpc_stage5.baseline_replay import Stage5SensorBoundaryPlant
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.controller_interface import CONTROLLER_NOMINAL_INTERFACE
from traction_mpc_stage5.goal_mpc import GoalDirectedHumanSpaceMPC
from traction_mpc_stage5.goal_mpc_smoke import (
    InitialConditionValidationError,
    run_goal_mpc_smoke,
)
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.interface_robustness import (
    ProgressiveTranslationStage5Plant,
    load_interface_robustness_contract,
    score_trace,
)
from traction_mpc_stage5.interface_robustness_campaign import (
    classify_boundary,
    compact_score_row,
    linear_trend,
    load_final_campaign_spec,
    scaled_interface,
)
from traction_mpc_stage5.mechanics import (
    NOMINAL_PHYSICS_DT_S,
    STAGE5_RIGID_INTERFACE,
)
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK


REPOSITORY_ROOT = STAGE5_ROOT.parents[1]
DEFAULT_OUTPUT = STAGE5_ROOT / "results" / "interface_robustness_final_campaign_v1"
PLANNING_FORCE_CEILING_N = 180.0
PLANNING_VELOCITY_CEILING_DEG_S = (15.0, 25.0)
PHYSICAL_FORCE_GATE_N = 200.0
REPEATABILITY_CONDITION = {
    "name": "moderately_soft_low_low_low",
    "alpha_t": 0.9,
    "alpha_r": 0.9,
    "alpha_d": 0.8,
    "resolution_basis": (
        "The frozen final-campaign JSON names a fixed moderately-soft condition "
        "without repeating its numeric values; the only preregistered named "
        "moderately-soft condition is low_low_low=(0.9,0.9,0.8), shared by "
        "the uncertainty config and final core matrix."
    ),
}


def _json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPOSITORY_ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fingerprinted_files() -> list[Path]:
    files: list[Path] = []
    for relative_root in ("src", "configs"):
        root = STAGE5_ROOT / relative_root
        files.extend(
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix in {".py", ".json"}
        )
    files.extend(
        [
            STAGE5_ROOT / "scripts" / "run_stage5_interface_robustness_final_campaign_v1.py",
            STAGE5_ROOT / "scripts" / "run_stage5_interface_robustness_v1.py",
        ]
    )
    return sorted(set(files))


def _manifest() -> dict[str, str]:
    return {
        str(path.relative_to(REPOSITORY_ROOT)): _sha256_file(path)
        for path in _fingerprinted_files()
    }


def _write_untracked_patch(path: Path, relative_files: list[str]) -> None:
    pieces: list[str] = []
    for relative in relative_files:
        result = _git("diff", "--no-index", "--", "/dev/null", relative, check=False)
        if result.returncode not in (0, 1):
            raise RuntimeError(result.stderr)
        pieces.append(result.stdout)
    path.write_text("".join(pieces), encoding="utf-8")


def freeze_campaign_fingerprint(
    output_dir: Path,
    contract: dict[str, Any],
    campaign: dict[str, Any],
) -> dict[str, Any]:
    fingerprint_dir = output_dir / "campaign_fingerprint"
    fingerprint_dir.mkdir(parents=True, exist_ok=False)
    tracked_patch = _git(
        "diff",
        "--binary",
        "HEAD",
        "--",
        "stages/stage5_personalized_motion_learning",
    ).stdout
    (fingerprint_dir / "stage5_dirty_tracked.patch").write_text(
        tracked_patch, encoding="utf-8"
    )
    relevant_untracked = [
        item[3:]
        for item in _git(
            "status",
            "--short",
            "--untracked-files=all",
            "--",
            "stages/stage5_personalized_motion_learning",
        ).stdout.splitlines()
        if item.startswith("?? ")
        and any(
            token in item
            for token in (
                "interface_robustness",
                "interface_uncertainty",
                "interface_mismatch",
            )
        )
    ]
    _write_untracked_patch(
        fingerprint_dir / "stage5_relevant_untracked.patch", relevant_untracked
    )
    config_dir = fingerprint_dir / "configs"
    config_dir.mkdir()
    for name in (
        "stage5_interface_robustness_v1.json",
        "stage5_interface_robustness_final_campaign_v1.json",
        "stage5_controller_nominal_interface_v1.json",
        "stage5_goal_task_v1.json",
        "stage5_geometry_mechanics_v2.json",
    ):
        shutil.copy2(STAGE5_ROOT / "configs" / name, config_dir / name)

    default_mpc = HumanMPCConfig()
    probe_mpc = GoalDirectedHumanSpaceMPC(
        default_mpc,
        planning_physical_force_ceiling_n=PLANNING_FORCE_CEILING_N,
        planning_joint_velocity_ceiling_rad_s=tuple(
            np.radians(PLANNING_VELOCITY_CEILING_DEG_S)
        ),
    )
    fingerprint = {
        "schema": "stage5_interface_robustness_final_campaign_fingerprint_v1",
        "user_authorization": (
            "Current user task explicitly authorizes execution; frozen config "
            "preregistration status is intentionally not rewritten."
        ),
        "head": _git("rev-parse", "HEAD").stdout.strip(),
        "git_status_before_first_episode": _git("status", "--short").stdout.splitlines(),
        "stage5_tracked_dirty_patch": "stage5_dirty_tracked.patch",
        "stage5_relevant_untracked_patch": "stage5_relevant_untracked.patch",
        "source_and_config_sha256": _manifest(),
        "fixed_random_seeds": campaign["fixed_random_seeds"],
        "core_conditions": campaign["core_box"]["conditions"],
        "boundary_conditions": campaign["boundary_challenges"]["conditions"],
        "repeatability_condition": REPEATABILITY_CONDITION,
        "plant_v1_truth_nominal": {
            "translation_stiffness_n_m": list(
                STAGE5_RIGID_INTERFACE.translation_stiffness_n_m
            ),
            "translation_damping_ns_m": list(
                STAGE5_RIGID_INTERFACE.translation_damping_ns_m
            ),
            "rotation_stiffness_nm_rad": (
                STAGE5_RIGID_INTERFACE.rotation_stiffness_nm_rad
            ),
            "rotation_damping_nms_rad": (
                STAGE5_RIGID_INTERFACE.rotation_damping_nms_rad
            ),
            "physics_dt_s": NOMINAL_PHYSICS_DT_S,
        },
        "controller_nominal_interface": {
            "model_version": CONTROLLER_NOMINAL_INTERFACE.model_version,
            "translation_stiffness_n_m": list(
                CONTROLLER_NOMINAL_INTERFACE.translation_stiffness_n_m
            ),
            "translation_damping_ns_m": list(
                CONTROLLER_NOMINAL_INTERFACE.translation_damping_ns_m
            ),
            "rotation_stiffness_nm_rad": (
                CONTROLLER_NOMINAL_INTERFACE.rotation_stiffness_nm_rad
            ),
            "rotation_damping_nms_rad": (
                CONTROLLER_NOMINAL_INTERFACE.rotation_damping_nms_rad
            ),
        },
        "goal_mpc": {
            **vars(default_mpc),
            "motion_config": vars(probe_mpc.motion_config),
            "goal_objective": vars(probe_mpc.goal_objective),
            "planning_physical_force_ceiling_n": PLANNING_FORCE_CEILING_N,
            "planning_joint_velocity_ceiling_deg_s": list(
                PLANNING_VELOCITY_CEILING_DEG_S
            ),
        },
        "physical_200n_engineering_gate_n": PHYSICAL_FORCE_GATE_N,
        "task_spec": vars(PROVISIONAL_LOW_MODERATE_GOAL_TASK),
        "acceptance_contract": contract,
        "online_authority": {
            "fixed_nominal_interface_only": True,
            "interface_identification_or_adaptation": False,
            "human_adaptation": False,
            "value_or_rl_learning": False,
            "plant_truth_online": False,
        },
        "not_a_clinical_hardware_or_hard_realtime_claim": True,
    }
    _json_write(fingerprint_dir / "fingerprint.json", fingerprint)
    return fingerprint


def _assert_frozen(expected: dict[str, str]) -> None:
    actual = _manifest()
    if actual != expected:
        changed = sorted(set(expected) | set(actual))
        changed = [name for name in changed if expected.get(name) != actual.get(name)]
        raise RuntimeError(f"fingerprinted campaign implementation changed: {changed}")


def _startup_row(
    section: str,
    condition: dict[str, Any],
    seed: int,
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "campaign_section": section,
        "condition": condition,
        "seed": seed,
        "online_result": "ABORTED",
        "abort_reason": diagnostics.get("abort_reason"),
        "truth_complete": False,
        "accepted": False,
        "false_complete": False,
        "silent_motion_violation": False,
        "initialization_failure": True,
        "startup_diagnostics": diagnostics,
        "force_gate_event_count": 0,
        "structural_event_count": 0,
        "brake_event_count": 0,
        "mujoco_warning_counts": diagnostics.get("mujoco_warning_counts", {}),
    }


def _run_episode(
    output_dir: Path,
    *,
    section: str,
    condition: dict[str, Any],
    seed: int,
    contract: dict[str, Any],
    hold_s: float = 0.5,
    session_context: dict[str, Any] | None = None,
    plant_factory: Callable[[Any], Stage5SensorBoundaryPlant] | None = None,
) -> dict[str, Any]:
    plant_parameters = scaled_interface(
        float(condition["alpha_t"]),
        float(condition["alpha_r"]),
        float(condition["alpha_d"]),
    )
    task = replace(PROVISIONAL_LOW_MODERATE_GOAL_TASK, hold_duration_s=hold_s)
    try:
        summary = run_goal_mpc_smoke(
            output_dir,
            spec=task,
            maximum_duration_s=(30.0 if hold_s >= 5.0 else 25.0),
            plant_interface_parameters=plant_parameters,
            plant_case_name=f"final_campaign__{section}__{condition['name']}",
            record_selected_horizon_diagnostics=True,
            use_loaded_local_hold=True,
            stop_on_return_entry=False,
            use_bumpless_return_handoff=True,
            initialize_loaded_equilibrium_with_plant_truth=True,
            interface_uncertainty_spec=None,
            planning_physical_force_ceiling_n=PLANNING_FORCE_CEILING_N,
            planning_joint_velocity_ceiling_rad_s=tuple(
                np.radians(PLANNING_VELOCITY_CEILING_DEG_S)
            ),
            mpc_config=HumanMPCConfig(random_seed=seed),
            plant_factory=plant_factory,
            session_context=session_context,
        )
    except InitialConditionValidationError as error:
        diagnostics = dict(error.diagnostics)
        _json_write(output_dir / "startup_abort.json", diagnostics)
        return _startup_row(section, condition, seed, diagnostics)
    with np.load(output_dir / "trace.npz") as trace:
        score = score_trace(
            summary,
            trace,
            contract,
            long_hold_expected=hold_s >= 5.0,
        )
    row = compact_score_row(
        campaign_section=section,
        condition=condition,
        seed=seed,
        score=score,
        summary=summary,
    )
    row["long_hold"] = score["long_hold"]
    row["initialization_failure"] = False
    return row


def _repeatability_summary(rows: list[dict[str, Any]], campaign: dict[str, Any]) -> dict[str, Any]:
    repeat = campaign["repeatability"]
    terminal = np.asarray(
        [row["return_truth_angle_error_deg"] for row in rows], dtype=float
    )
    drift = np.mean(terminal[-5:], axis=0) - np.mean(terminal[:5], axis=0)
    metrics = {
        "peak_force_n": [row["peak_physical_force_n"] for row in rows],
        "interface_translation_mm": [
            row["peak_interface_translation_mm"] for row in rows
        ],
        "interface_rotation_deg": [row["peak_interface_rotation_deg"] for row in rows],
        "q_error_max_norm_deg": [
            float(np.linalg.norm(row["q_max_abs_deg"])) for row in rows
        ],
        "dq_error_max_norm_deg_s": [
            float(np.linalg.norm(row["dq_max_abs_deg_s"])) for row in rows
        ],
        "task_duration_s": [row["duration_s"] for row in rows],
        "mpc_runtime_mean_ms": [row["runtime_ms"]["mean"] for row in rows],
    }
    long_holds = {
        str(index): rows[index - 1]["long_hold"]
        for index in repeat["five_second_hold_episodes"]
    }
    numerical_requirements = bool(
        len(rows) == repeat["continuous_episode_count"]
        and all(row["accepted"] for row in rows)
        and all(not row["false_complete"] for row in rows)
        and all(not row["silent_motion_violation"] for row in rows)
        and all(not row["brake_event_count"] for row in rows)
        and all(not row["force_gate_event_count"] for row in rows)
        and np.all(
            np.abs(drift)
            <= np.asarray(repeat["last5_vs_first5_terminal_drift_abs_max_deg"])
        )
        and all(item["accepted"] for item in long_holds.values())
    )
    return {
        "episode_count": len(rows),
        "truth_complete_count": sum(bool(row["truth_complete"]) for row in rows),
        "accepted_count": sum(bool(row["accepted"]) for row in rows),
        "false_completion_count": sum(bool(row["false_complete"]) for row in rows),
        "silent_motion_violation_count": sum(
            bool(row["silent_motion_violation"]) for row in rows
        ),
        "terminal_truth_abs_error_deg": terminal.tolist(),
        "last5_minus_first5_mean_terminal_error_deg": drift.tolist(),
        "long_hold_episodes": long_holds,
        "metric_trends": {name: linear_trend(values) for name, values in metrics.items()},
        "numerical_requirements_satisfied": numerical_requirements,
        "material_degradation_requires_frozen_evidence_review": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    contract = load_interface_robustness_contract()
    campaign = load_final_campaign_spec()
    fingerprint = freeze_campaign_fingerprint(args.output_dir, contract, campaign)
    frozen_manifest = fingerprint["source_and_config_sha256"]

    core_rows: list[dict[str, Any]] = []
    for condition in campaign["core_box"]["conditions"]:
        for seed in campaign["fixed_random_seeds"]:
            _assert_frozen(frozen_manifest)
            row = _run_episode(
                args.output_dir / "core" / condition["name"] / f"seed_{seed}",
                section="core",
                condition=condition,
                seed=seed,
                contract=contract,
            )
            core_rows.append(row)
            _json_write(args.output_dir / "core_progress.json", core_rows)
            print(
                f"CORE {len(core_rows):02d}/27 {condition['name']} seed={seed} "
                f"online={row['online_result']} accepted={row['accepted']}",
                flush=True,
            )

    boundary_rows: list[dict[str, Any]] = []
    boundary_seed = int(campaign["boundary_challenges"]["seed"])
    for condition in campaign["boundary_challenges"]["conditions"]:
        _assert_frozen(frozen_manifest)
        factory = None
        if condition["name"] == "progressive_translation_stiffness":
            beta = float(condition["beta"])
            x_ref_m = float(condition["x_ref_m"])

            def factory(
                parameters: Any,
                *,
                beta: float = beta,
                x_ref_m: float = x_ref_m,
            ) -> Stage5SensorBoundaryPlant:
                return ProgressiveTranslationStage5Plant(
                    STAGE5_HUMAN,
                    interface_parameters=parameters,
                    beta=beta,
                    x_ref_m=x_ref_m,
                )

        row = _run_episode(
            args.output_dir / "boundary" / condition["name"],
            section="boundary",
            condition=condition,
            seed=boundary_seed,
            contract=contract,
            plant_factory=factory,
        )
        row.update(classify_boundary(row))
        boundary_rows.append(row)
        _json_write(args.output_dir / "boundary_progress.json", boundary_rows)
        print(
            f"BOUNDARY {len(boundary_rows)}/4 {condition['name']} "
            f"classification={row['classification']}",
            flush=True,
        )

    repeat_rows: list[dict[str, Any]] = []
    session_context: dict[str, Any] = {}
    repeat_seed = int(campaign["repeatability"]["seed_stream_initialization"])
    long_hold_episodes = set(campaign["repeatability"]["five_second_hold_episodes"])
    for episode in range(1, campaign["repeatability"]["continuous_episode_count"] + 1):
        _assert_frozen(frozen_manifest)
        hold_s = 5.0 if episode in long_hold_episodes else 0.5
        row = _run_episode(
            args.output_dir / "repeatability" / f"episode_{episode:02d}",
            section="repeatability",
            condition=REPEATABILITY_CONDITION,
            seed=repeat_seed,
            contract=contract,
            hold_s=hold_s,
            session_context=session_context,
        )
        row["episode"] = episode
        repeat_rows.append(row)
        _json_write(args.output_dir / "repeatability_progress.json", repeat_rows)
        print(
            f"REPEAT {episode:02d}/30 online={row['online_result']} "
            f"accepted={row['accepted']}",
            flush=True,
        )

    repeat_summary = _repeatability_summary(repeat_rows, campaign)
    core_all = len(core_rows) == 27 and all(row["accepted"] for row in core_rows)
    boundary_all = len(boundary_rows) == 4 and all(
        row["boundary_acceptable"] for row in boundary_rows
    )
    result = {
        "schema": "stage5_interface_robustness_final_campaign_results_v1",
        "evidence_category": "user_authorized_formal_simulation_campaign",
        "fingerprint": "campaign_fingerprint/fingerprint.json",
        "fingerprint_sha256": _sha256_file(
            args.output_dir / "campaign_fingerprint" / "fingerprint.json"
        ),
        "implementation_unchanged_after_first_episode": True,
        "core": {
            "rows": core_rows,
            "accepted_count": sum(bool(row["accepted"]) for row in core_rows),
            "required_count": 27,
            "all_accepted": core_all,
        },
        "boundary": {
            "rows": boundary_rows,
            "acceptable_count": sum(
                bool(row["boundary_acceptable"]) for row in boundary_rows
            ),
            "required_count": 4,
            "all_acceptable": boundary_all,
        },
        "repeatability": {"rows": repeat_rows, "summary": repeat_summary},
        "exit_preconditions": {
            "exit_a_numerical_preconditions": bool(
                core_all
                and boundary_all
                and repeat_summary["numerical_requirements_satisfied"]
            ),
            "trend_review_still_required": True,
            "no_posthoc_rescue_or_replacement": True,
        },
        "scope": {
            "simulation_mechanical_engineering_evidence_only": True,
            "clinical_safety_validation": False,
            "hardware_validation": False,
            "hard_realtime_or_wcet_certification": False,
            "continuous_robustness_guarantee": False,
        },
    }
    _json_write(args.output_dir / "campaign_results.json", result)
    print(json.dumps(result["exit_preconditions"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
