#!/usr/bin/env python3
"""Minimal nominal two-repetition comparison of Stage-5 trust semantics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

import run_stage5_human_id_confidence_pacing_v1 as pacing_study
from traction_mpc_stage4.mpc import HumanMPCConfig
from traction_mpc_stage5.baseline_replay import Stage5SensorBoundaryPlant
from traction_mpc_stage5.confidence_pacing import (
    Stage5ConfidencePacing,
    Stage5CurrentModelTrust,
    Stage5PacingEvidence,
    current_nominal_model_trust_from_shadow_service,
)
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.goal_mpc_smoke import (
    FIXED_HUMAN_MODEL_VERSION,
    run_goal_mpc_smoke,
)
from traction_mpc_stage5.human_identification import Stage5HumanIDMeasurement
from traction_mpc_stage5.human_identification_reduced import (
    ReducedShadowHumanIdentificationService,
)
from traction_mpc_stage5.mechanics import STAGE5_RIGID_INTERFACE


def _first_time(mask: np.ndarray, time_s: np.ndarray) -> float | None:
    indices = np.flatnonzero(mask)
    return None if not len(indices) else float(time_s[indices[0]])


def _run_arm(
    *, semantics: str, output_dir: Path, config: dict[str, Any]
) -> dict[str, Any]:
    geometry = pacing_study._geometry()
    service = ReducedShadowHumanIdentificationService(geometry)
    pacing = Stage5ConfidencePacing()
    trust = (
        Stage5CurrentModelTrust(FIXED_HUMAN_MODEL_VERSION)
        if semantics == "persistent_model_versioned"
        else None
    )
    human = pacing_study._human([1.0, 1.0, 1.0])
    base_ceiling = tuple(
        np.radians(config["controller"]["base_planning_joint_velocity_ceiling_deg_s"])
    )
    reset_gap_s = float(config["session"]["physical_reset_gap_in_session_time_s"])
    session_offset_s = 0.0
    episodes: list[dict[str, Any]] = []
    arm_support_events: list[dict[str, Any]] = []
    arm_wall_start = perf_counter()

    for repetition in (1, 2):
        service.begin_episode(repetition - 1, session_offset_s)
        attempts_before = len(service.attempts)
        publications_before = len(service.publication_history)
        pacing_history_before = len(pacing.evidence_history)
        trust_history_before = 0 if trust is None else len(trust.history)
        support_at_start = (
            current_nominal_model_trust_from_shadow_service(
                {"attempts": service.attempts}
            )[0]
            if trust is None
            else trust.supported
        )
        callback_last_support: bool | None = None

        def callback(payload: dict[str, Any]) -> dict[str, Any]:
            nonlocal callback_last_support
            session_time_s = session_offset_s + float(payload["episode_time_s"])
            service.observe(
                Stage5HumanIDMeasurement(
                    arrival_time_s=session_time_s,
                    sample_time_s=session_time_s,
                    estimated_human_state_rad_rad_s=payload[
                        "estimated_human_state_rad_rad_s"
                    ],
                    measured_human_cuff_force_world_n=payload[
                        "measured_human_cuff_force_world_n"
                    ],
                    measured_human_cuff_moment_world_nm=payload[
                        "measured_human_cuff_moment_world_nm"
                    ],
                    measured_generalized_human_input_nm=payload[
                        "measured_generalized_human_input_nm"
                    ],
                    task_phase=str(payload["task_phase"]),
                    interface_model_version=str(payload["interface_model_version"]),
                )
            )
            if trust is None:
                supported, reason = current_nominal_model_trust_from_shadow_service(
                    {"attempts": service.attempts}
                )
            else:
                trust.observe_shadow_service(
                    {"attempts": service.attempts},
                    session_time_s=session_time_s,
                )
                supported = trust.supported
                reason = str(trust.status()["state_reason"])
            if supported != callback_last_support:
                arm_support_events.append(
                    {
                        "session_time_s": session_time_s,
                        "repetition": repetition,
                        "supported": bool(supported),
                        "reason": reason,
                    }
                )
                callback_last_support = bool(supported)
            information = pacing_study._latest_information(service)
            pacing.update(
                Stage5PacingEvidence(
                    session_time_s=session_time_s,
                    identification_informative=bool(information.get("rank", 0) == 3),
                    information_rank=int(information.get("rank", 0)),
                    information_condition_number=float(
                        information.get("condition_number", float("inf"))
                    ),
                    current_nominal_model_adequate=bool(supported),
                    current_model_evidence_reason=reason,
                    challenger_status=pacing_study._challenger_status(service),
                    shadow_publication_count=len(service.publication_history) - 1,
                )
            )
            return pacing.status(session_time_s)

        def plant_factory(parameters):
            return Stage5SensorBoundaryPlant(human, interface_parameters=parameters)

        episode_dir = output_dir / f"episode_{repetition:02d}"
        wall_start = perf_counter()
        summary = run_goal_mpc_smoke(
            episode_dir,
            maximum_duration_s=25.5,
            plant_interface_parameters=STAGE5_RIGID_INTERFACE,
            plant_case_name=f"trust_persistence__{semantics}__rep{repetition:02d}",
            record_selected_horizon_diagnostics=False,
            use_loaded_local_hold=True,
            use_bumpless_return_handoff=True,
            initialize_loaded_equilibrium_with_plant_truth=True,
            interface_uncertainty_spec=None,
            planning_physical_force_ceiling_n=float(
                config["controller"]["planning_physical_force_ceiling_n"]
            ),
            planning_joint_velocity_ceiling_rad_s=base_ceiling,
            mpc_config=HumanMPCConfig(
                random_seed=int(config["controller"]["cem_random_seed"])
            ),
            plant_factory=plant_factory,
            progress_pacing_callback=callback,
        )
        wall_time_s = perf_counter() - wall_start
        with np.load(episode_dir / "trace.npz") as loaded:
            trace = {key: loaded[key] for key in loaded.files}
        time_s = np.asarray(trace["time_s"], dtype=float)
        session_time = session_offset_s + time_s
        gamma = np.asarray(trace["progress_pacing_gamma"], dtype=float)
        gamma_rate = np.asarray(trace["progress_pacing_gamma_rate_per_s"], dtype=float)
        ceiling = np.degrees(
            np.asarray(trace["progress_pacing_velocity_ceiling_rad_s"], dtype=float)
        )
        episode_pacing_events = pacing.evidence_history[pacing_history_before:]
        episode_trust_events = (
            [] if trust is None else trust.history[trust_history_before:]
        )
        first_support = next(
            (
                event["session_time_s"]
                for event in arm_support_events
                if event["repetition"] == repetition and event["supported"]
            ),
            None,
        )
        plateau_mask = (gamma > 0.5 + 1.0e-12) & (
            np.abs(gamma_rate) <= 1.0e-12
        )
        episodes.append(
            {
                "repetition": repetition,
                "task_status": summary["task_status"],
                "abort_reason": summary.get("abort_reason"),
                "task_duration_s": float(summary["task_duration_s"]),
                "current_control_model_version": FIXED_HUMAN_MODEL_VERSION,
                "support_at_repetition_start": bool(support_at_start),
                "first_support_session_time_s": first_support,
                "support_at_repetition_end": bool(
                    current_nominal_model_trust_from_shadow_service(
                        {"attempts": service.attempts}
                    )[0]
                    if trust is None
                    else trust.supported
                ),
                "final_filtered_confidence": float(
                    pacing.status(float(session_time[-1]))[
                        "filtered_current_model_confidence"
                    ]
                ),
                "final_hysteresis_high": bool(
                    pacing.status(float(session_time[-1]))[
                        "execution_confidence_high"
                    ]
                ),
                "final_gamma_target": float(
                    pacing.status(float(session_time[-1]))["gamma_target"]
                ),
                "first_gamma_above_minimum_session_time_s": _first_time(
                    gamma > 0.5 + 1.0e-12, session_time
                ),
                "first_higher_plateau_session_time_s": _first_time(
                    plateau_mask, session_time
                ),
                "gamma_minimum": float(np.min(gamma)),
                "gamma_maximum": float(np.max(gamma)),
                "gamma_final": float(gamma[-1]),
                "planning_velocity_ceiling_deg_s_min": np.min(ceiling, axis=0).tolist(),
                "planning_velocity_ceiling_deg_s_max": np.max(ceiling, axis=0).tolist(),
                "peak_deployable_acceleration_deg_s2": summary[
                    "peak_abs_estimated_joint_acceleration_deg_s2"
                ],
                "peak_truth_acceleration_deg_s2_evaluation_only": summary[
                    "peak_abs_evaluation_only_joint_acceleration_deg_s2"
                ],
                "force_gate_events": int(summary["force_gate_event_count"]),
                "safety_filter_status_counts": summary[
                    "safety_filter_status_counts"
                ],
                "brake_events": int(summary["brake_event_count"]),
                "mujoco_warning_counts": summary["mujoco_warning_counts"],
                "new_challenger_attempts": service.attempts[attempts_before:],
                "new_shadow_publications": service.publication_history[
                    publications_before:
                ],
                "pacing_transition_events": episode_pacing_events,
                "trust_transition_events": episode_trust_events,
                "wall_time_s": wall_time_s,
            }
        )
        session_offset_s += float(summary["task_duration_s"]) + reset_gap_s

    return {
        "semantics": semantics,
        "episodes": episodes,
        "support_events": arm_support_events,
        "trust_summary": None if trust is None else trust.summary(),
        "pacing_summary": pacing.summary(float(service.last_sample_time_s or 0.0)),
        "service_summary": service.summary(),
        "total_wall_time_s": perf_counter() - arm_wall_start,
        "fixed_nominal_human_model_in_control": True,
        "shadow_model_applied_to_control": False,
        "acceleration_monitor_changed": False,
        "truth_used_online": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STAGE5_ROOT / "results" / "trust_persistence_v1",
    )
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    config = pacing_study._load_config()
    arms = []
    for semantics in ("historical_stateless", "persistent_model_versioned"):
        row = _run_arm(
            semantics=semantics,
            output_dir=args.output_dir / semantics,
            config=config,
        )
        arms.append(row)
        print(
            json.dumps(
                {
                    "completed_arm": semantics,
                    "statuses": [item["task_status"] for item in row["episodes"]],
                    "final_gammas": [item["gamma_final"] for item in row["episodes"]],
                }
            ),
            flush=True,
        )
    result = {
        "schema": "stage5_trust_persistence_v1_results",
        "arms": arms,
        "current_control_model_version": FIXED_HUMAN_MODEL_VERSION,
        "human_truth_scales_evaluation_only": [1.0, 1.0, 1.0],
        "same_seed_and_controller_settings": True,
        "maximum_two_repetitions_per_arm": True,
        "physical_reset_between_repetitions": True,
        "trust_and_human_id_persist_across_repetitions": True,
        "regression_windows_cross_artificial_reset": False,
        "formal_personalization_claim": False,
    }
    output = args.output_dir / "summary.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"summary": str(output)}, indent=2))


if __name__ == "__main__":
    main()
