"""Matched DEV-C first-segment physical replay from a preserved DEV-B checkpoint.

This script never creates a new controller observation from simulation truth.
Truth and contact are recorded for evaluation after the production command.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random

import numpy as np

from dev_b_matched_diagnostics_v1 import (
    command_components, guard, integration_state, load_checkpoint, physics_record,
    production, save_json, sha,
)
from traction_mpc_stage5.full3d_adaptive_integration_v1.bumpless_transfer import (
    BumplessHumanActionTransfer,
)
from traction_mpc_stage5.full3d_adaptive_integration_v1.dev_a_recovery import mapped_with_bridge
from traction_mpc_stage5.human_waypoint_shadow import WaypointExecutionContext
from traction_mpc_stage5.task import TaskPhase


def run(checkpoint_dir: Path, output: Path, *, arm: str, duration_s: float,
        transfer_config_path: Path | None = None) -> None:
    if arm not in {"direct", "bumpless"}:
        raise ValueError("unsupported arm")
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    cp = load_checkpoint(checkpoint_dir / "checkpoint.pkl.gz")
    runtime, rec, saved = cp["runtime"], cp["recovery"], cp["execute_kwargs"]
    plant = runtime["plant"]
    start_state = integration_state(plant)
    start_hash = hashlib.sha256(start_state.tobytes()).hexdigest()
    prior = checkpoint_dir / "analysis_0200ms" / "activated_model.json"
    historical = json.loads(prior.read_text())
    if start_hash != historical["initial_integration_state_sha256"]:
        raise AssertionError("DEV-C initial integration state differs from DEV-B direct branch")
    segment = rec["active_segment"]
    if duration_s > segment["schedule"].duration_s + 1e-12:
        raise ValueError("matched run exceeds the common first scheduled segment")
    if abs(duration_s / production.CONTROL_DT_S - round(duration_s / production.CONTROL_DT_S)) > 1e-10:
        raise ValueError("duration must contain whole physical control intervals")
    random.setstate(cp["python_random_state"])
    np.random.set_state(cp["numpy_random_state"])
    runtime["model"] = rec["target_model"]
    runtime["contract"].human_model = rec["target_model"]
    runtime["last_executed_generalized_action_nm"] = np.asarray(
        json.loads((checkpoint_dir / "preactivation_trace.json").read_text())[-1]["generalized_action_nm"],
        dtype=float,
    )
    previous = cp["previous_command_record"]
    runtime["last_action_executable_verified"] = bool(
        previous["execution"]["safety_mode"] == "TRACK"
        and previous["execution"]["safety_filter"].get("status") == "SAFE_UNCHANGED"
        and np.max(np.abs(previous["components"]["saturation_delta_nm"])) <= 1e-10
    )
    if not runtime["last_action_executable_verified"]:
        raise AssertionError("matched activation predecessor was not an unchanged executed TRACK action")
    if arm == "bumpless":
        config_path = (transfer_config_path if transfer_config_path is not None else
                       Path(__file__).resolve().parents[1] / "configs"
                       / "full3d_adaptive_integration_v1"
                       / "dev_c_bumpless_transfer_v1.json")
        config = json.loads(config_path.read_text())
        manager = BumplessHumanActionTransfer(
            rec["old_model"], initial_version="population_prior_v1",
            duration_s=float(config["transfer_duration_s"]),
            small_direct_action_change_nm=float(config["small_direct_action_change_nm"]),
            duration_policy=config.get("duration_policy"),
            output_envelope=config.get("output_envelope"),
        )
        manager.offer(rec["target_model"], version=f"belief_{rec['belief'].sequence}",
                      time_s=float(plant.data.time))
        runtime["model_transfer"] = manager
    else:
        runtime.pop("model_transfer", None)
    records = []
    physics = [physics_record(plant)]
    reason = None
    original_step = plant.step

    def observed_step():
        original_step()
        physics.append(physics_record(plant))

    plant.step = observed_step
    try:
        for index in range(round(duration_s / production.CONTROL_DT_S)):
            if index == 0:
                measurement = saved["measurement"]
                observation = saved["observation"]
                interface = saved["interface"]
            else:
                measurement = runtime["measurement_layer"].update(plant.observe())
                observation, interface = runtime["observer"].update(
                    measurement, rec["target_model"], human_model_version=f"belief_{rec['belief'].sequence}"
                )
                reason = guard(runtime, rec, observation, interface, measurement)
                if reason is not None:
                    break
            elapsed = float(plant.data.time) - segment["start_time_s"]
            sample = segment["schedule"].sample(elapsed)
            candidate = production._candidate(
                f"dev_c_{arm}_{index:04d}", TaskPhase.RETURN,
                sample.q_rad, sample.dq_rad_s, rec["spec"],
                WaypointExecutionContext.ACTIVE_RECOVERY,
            )
            mapped = runtime["contract"].prepare(candidate)
            mapped = mapped_with_bridge(
                mapped, candidate, sample.q_rad, sample.dq_rad_s, sample.ddq_rad_s2,
                segment["bridge"], elapsed,
            )
            plant._measured_robot_model.set_configuration(
                measurement.robot_q_rad, measurement.robot_dq_rad_s,
            )
            bias = plant._measured_robot_model.bias_torque_nm()
            before = physics_record(plant)
            try:
                command, execution = production._execute_interval(
                    runtime, observation=observation, interface=interface,
                    measurement=measurement, candidate=candidate,
                    actuation_enabled=True, mapped_override=mapped,
                )
            except (ValueError, RuntimeError) as error:
                reason = f"LOW_LEVEL_EXECUTION:{type(error).__name__}:{error}"
                break
            components = command_components(command, bias)
            records.append({
                "time_s": before["time_s"], "estimated_state": observation.as_array(),
                "physics_before": before, "reference_q_rad": sample.q_rad,
                "reference_dq_rad_s": sample.dq_rad_s,
                "reference_ddq_rad_s2": sample.ddq_rad_s2,
                "desired_cuff_position_world_m": mapped.reference.world_from_cuff.translation,
                "desired_cuff_rotation_world": mapped.reference.world_from_cuff.rotation,
                "desired_cuff_twist_world": np.r_[
                    mapped.execution_target.robot_cuff_target.linear_velocity_world_m_s,
                    mapped.execution_target.robot_cuff_target.angular_velocity_world_rad_s,
                ],
                "generalized_action_nm": execution["generalized_action_nm"],
                "accepted_beta": rec["target_model"].beta,
                "accepted_residual_weights_nm": rec["target_model"].residual_weights_nm,
                "desired_acceleration_rad_s2": execution["desired_acceleration_rad_s2"],
                "force_total_n": command.force_total_n,
                "moment_total_nm": command.moment_total_nm,
                "force_allocator_n": command.force_allocator_n,
                "moment_allocator_nm": command.moment_allocator_nm,
                "robot_torque_nm": command.joint_torque_command_nm,
                "robot_torque_components": components,
                "safety_mode": str(execution["safety_mode"]),
                "safety_filter": execution["safety_filter"],
                "transfer": execution["model_transfer"],
            })
    finally:
        plant.step = original_step
    if len(physics) != 20*len(records)+1:
        raise AssertionError("substep trace violates N+1 physical boundary rule")
    if arm == "direct" and len(records) >= 40:
        error = max(float(np.max(np.abs(records[i]["robot_torque_nm"]
                                        - historical["records"][i]["command"]["joint_torque_command_nm"])))
                    for i in range(40))
        if error > 1e-7:
            raise AssertionError(f"new diagnostic direct replay differs from DEV-B: {error} Nm")
    else:
        error = None
    save_json(output / "matched_trace.json", {
        "schema": "dev_c_matched_physical_v1", "arm": arm,
        "checkpoint": str(checkpoint_dir), "checkpoint_sha256": sha(checkpoint_dir / "checkpoint.pkl.gz"),
        "initial_integration_state_sha256": start_hash,
        "final_integration_state_sha256": hashlib.sha256(integration_state(plant).tobytes()).hexdigest(),
        "requested_duration_s": duration_s,
        "actual_duration_s": float(plant.data.time)-rec["now_s"],
        "abort_reason": reason, "records": records, "physics": physics,
        "dev_b_direct_command_max_difference_nm": error,
        "model_transfer_events": [] if arm == "direct" else runtime["model_transfer"].events,
        "last_fully_realized_version": (None if arm == "direct"
                                        else runtime["model_transfer"].last_realized_version),
        "source_script_sha256": sha(__file__),
        "truth_consumed_by_control": False,
    })
    print(json.dumps({"arm": arm, "duration_s": float(plant.data.time)-rec["now_s"],
                      "abort": reason, "intervals": len(records), "output": str(output)}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--arm", choices=["direct", "bumpless"], required=True)
    parser.add_argument("--duration", type=float, default=.30)
    parser.add_argument("--transfer-config", type=Path)
    args = parser.parse_args()
    run(args.checkpoint_dir, args.output, arm=args.arm, duration_s=args.duration,
        transfer_config_path=args.transfer_config)


if __name__ == "__main__":
    main()
