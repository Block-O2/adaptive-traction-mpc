"""NONDEPLOYABLE DEV-B diagnostics; production modules are never edited.

Capture runs the unchanged DEV-A loop to immediately before its first fitted
command. Saved historical planner timing reconstructs the historical boundary.
Analysis clones the complete runtime and holds the scheduled reference fixed.
Only locally generated checkpoint files may be loaded (pickle is trusted input).
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import asdict, is_dataclass, replace
import gzip
import hashlib
import inspect
import json
from pathlib import Path
import pickle
import platform
import random
import subprocess
import sys

import mujoco
import numpy as np
import scipy

from traction_mpc_stage3.executable_command import preview_executable_command_from_context
from traction_mpc_stage4.estimator_v2 import BaseParameterHumanModel, dynamic_regressor_row
from traction_mpc_stage4.mpc import SAFE_ACTION
from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime as production
from traction_mpc_stage5.full3d_adaptive_integration_v1.dev_a_recovery import mapped_with_bridge
from traction_mpc_stage5.human_waypoint_shadow import WaypointExecutionContext
from traction_mpc_stage5.loaded_execution import build_stage5_loaded_execution_context
from traction_mpc_stage5.task_observation import make_task_observation
from traction_mpc_stage5.task import TaskPhase, task_limit_violation
from traction_mpc_stage5.cr12_robot import CR12_VELOCITY_LIMITS_RAD_S

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
DT = production.CONTROL_DT_S
SCHEMA = "NONDEPLOYABLE_DEV_B_MATCHED_DIAGNOSTIC_V1"


def serial(value):
    if is_dataclass(value):
        return serial(asdict(value))
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def save_json(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(serial(record), indent=2, sort_keys=True) + "\n")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def integration_state(plant):
    flag = mujoco.mjtState.mjSTATE_INTEGRATION
    state = np.empty(mujoco.mj_stateSize(plant.model, flag))
    mujoco.mj_getState(plant.model, plant.data, state, flag)
    return state


def physics_record(plant):
    # Evaluation only. No refresh, forward or integration side effects here.
    data, model = plant.data, plant.model
    interface = plant._evaluate_current_interface()
    sid = int(model.geom("shank_geom").id)
    axis = data.geom_xmat[sid].reshape(3, 3)[:, 2]
    clearance = (data.geom_xpos[sid, 2] - abs(axis[2]) * model.geom_size[sid, 1]
                 - model.geom_size[sid, 0] - data.geom_xpos[plant.bed_geom_id, 2])
    contact_load = 0.0
    for i in range(data.ncon):
        if plant.bed_geom_id in (int(data.contact[i].geom1), int(data.contact[i].geom2)):
            force = np.zeros(6)
            mujoco.mj_contactForce(model, data, i, force)
            contact_load += abs(float(force[0]))
    return {
        "time_s": float(data.time),
        "q_true_rad": data.qpos[plant.human_qpos_indices].copy(),
        "dq_true_rad_s": data.qvel[plant.human_dof_indices].copy(),
        "ddq_true_rad_s2": data.qacc[plant.human_dof_indices].copy(),
        "robot_q_rad": data.qpos[plant.robot_qpos_indices].copy(),
        "robot_dq_rad_s": data.qvel[plant.robot_dof_indices].copy(),
        "robot_ddq_rad_s2": data.qacc[plant.robot_dof_indices].copy(),
        "human_cuff_wrench_world": interface.human_wrench_world.copy(),
        "robot_reaction_wrench_world": interface.robot_wrench_world.copy(),
        "interface_x_human_m": interface.displacement_human_m.copy(),
        "interface_v_human_m_s": interface.velocity_human_m_s.copy(),
        "interface_theta_human_rad": interface.rotation_error_human_rad.copy(),
        "interface_omega_human_rad_s": interface.angular_velocity_human_rad_s.copy(),
        "spring_energy_j": interface.spring_energy_j,
        "damping_dissipation_w": interface.damping_dissipation_w,
        "true_shank_clearance_m": float(clearance),
        "contact_pairs": production._active_contact_pairs(plant),
        "bed_normal_load_n": contact_load,
    }


def command_components(command, bias):
    j = command.robot_attachment_jacobian
    parts = {
        "allocator_nm": j.T @ np.r_[command.force_allocator_n, command.moment_allocator_nm],
        "position_nm": j[:3].T @ command.force_position_n,
        "linear_velocity_nm": j[:3].T @ command.force_velocity_n,
        "orientation_nm": j[3:].T @ command.moment_orientation_nm,
        "angular_velocity_nm": j[3:].T @ command.moment_angular_velocity_nm,
        "bias_nm": np.asarray(bias).copy(),
        "saturation_delta_nm": command.joint_torque_command_nm - command.unclipped_joint_torque_nm,
    }
    base = command.unclipped_joint_torque_nm - j.T @ command.wrench_total_world
    parts["nullspace_posture_nm"] = base - bias
    error = sum(parts.values()) - command.joint_torque_command_nm
    if np.max(np.abs(error)) > 1e-10:
        raise AssertionError("robot torque decomposition does not close")
    return {**parts, "sum_error_nm": error}


class Captured(BaseException):
    pass


def capture(case_path, historical, output):
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    case = json.loads(case_path.read_text())
    history = json.loads((historical / "summary.json").read_text())
    historical_ms = history["dev_a_recovery"]["planner_decisions"][0]["runtime_ms"]
    original_execute, original_timer = production._execute_interval, production.perf_counter
    timer_calls = 0
    last_record = None

    def recorded_timer():
        nonlocal timer_calls
        timer_calls += 1
        if timer_calls > 2:
            raise RuntimeError("capture unexpectedly reached a second planning call")
        return 100.0 + (historical_ms / 1000.0 if timer_calls == 2 else 0.0)

    def intercept(runtime, **kwargs):
        nonlocal last_record
        candidate = kwargs["candidate"]
        if (candidate.execution_context is WaypointExecutionContext.ACTIVE_RECOVERY
                and kwargs["observation"].human_model_version.startswith("belief_")):
            local = inspect.currentframe().f_back.f_locals
            keys = ["spec", "updater", "scheduler", "clearance", "old_model",
                    "old_robot_cuff_pose", "target_model", "belief", "active_segment",
                    "pending", "phase", "reference_q", "reference_dq", "reference_ddq",
                    "settle_since_s", "start_time_s", "now_s", "step", "config", "result",
                    "model_activated", "maximum_age_s", "timeout_s", "last_desired_pose"]
            checkpoint = copy.deepcopy({
                "runtime": runtime, "execute_kwargs": kwargs,
                "recovery": {k: local[k] for k in keys},
                "python_random_state": random.getstate(),
                "numpy_random_state": np.random.get_state(),
                "previous_command_record": last_record,
            })
            with gzip.open(output / "checkpoint.pkl.gz", "wb", compresslevel=1) as stream:
                pickle.dump(checkpoint, stream, protocol=5)
            np.savez_compressed(output / "checkpoint_mujoco.npz",
                integration=integration_state(runtime["plant"]),
                qacc=runtime["plant"].data.qacc.copy(),
                qacc_warmstart=runtime["plant"].data.qacc_warmstart.copy())
            rows = local["trace"]
            save_json(output / "preactivation_trace.json", rows[-8:])
            h = np.load(historical / "trace.npz", allow_pickle=True)
            times = np.asarray(h["time_s"], dtype=float)
            matching = np.flatnonzero(np.isclose(times, local["now_s"], rtol=0, atol=1e-10))
            idx = int(matching[-1])
            p = runtime["plant"]
            truth = np.r_[p.data.qpos[p.human_qpos_indices], p.data.qvel[p.human_dof_indices]]
            source = {}
            for module in tuple(sys.modules.values()):
                file = getattr(module, "__file__", None)
                if file and Path(file).is_file() and str(file).startswith(str(REPO)):
                    source[str(Path(file).relative_to(REPO))] = sha(file)
            save_json(output / "capture_manifest.json", {
                "schema": SCHEMA, "command": sys.argv, "case": case, "case_path": str(case_path),
                "historical_path": str(historical), "historical_summary_sha256": sha(historical / "summary.json"),
                "historical_trace_sha256": sha(historical / "trace.npz"),
                "historical_planner_ms_replayed": historical_ms,
                "replayed_wait_steps": round((local["now_s"]-local["start_time_s"])/DT),
                "checkpoint_time_s": local["now_s"], "historical_boundary_index": idx,
                "historical_truth_max_abs_delta": float(np.max(np.abs(truth-h["evaluation_only_human_state_rad_rad_s"][idx]))),
                "historical_robot_q_max_abs_delta": float(np.max(np.abs(p.data.qpos[p.robot_qpos_indices]-h["cr12_q_rad"][idx]))),
                "historical_estimate_max_abs_delta": float(np.max(np.abs(kwargs["observation"].as_array()-h["estimated_human_state_rad_rad_s"][idx]))),
                "historical_beta_max_abs_delta": float(np.max(np.abs(local["target_model"].beta-np.asarray(history["dev_a_recovery"]["beta_start"])))),
                "checkpoint_sha256": sha(output / "checkpoint.pkl.gz"),
                "runtime_keys": sorted(runtime), "recovery_keys": keys,
                "checkpoint_position": "model/observer activated in software, before first fitted command calculation/application; old model and common interface retained for exact cross evaluation",
                "mujoco_state": "full MjModel and MjData pickled, plus independent mjSTATE_INTEGRATION vector and qacc_warmstart; robot helper models, histories and aliases retained",
                "pending": "already accepted first schedule, remaining wait zero, no asynchronous worker; active_segment includes exact plan and bridge",
                "python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__,
                "mujoco": mujoco.__version__, "platform": platform.platform(),
                "source_sha256": source,
                "branch": subprocess.check_output(["git", "branch", "--show-current"], text=True).strip(),
                "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            })
            print(json.dumps({"captured": case["case_key"], "time_s": local["now_s"], "output": str(output)}), flush=True)
            raise Captured()
        p = runtime["plant"]
        if candidate.label.startswith("recovery_"):
            physical = physics_record(p)
            state = kwargs["observation"].as_array().copy()
            measurement = kwargs["measurement"]
            p._measured_robot_model.set_configuration(measurement.robot_q_rad, measurement.robot_dq_rad_s)
            bias = p._measured_robot_model.bias_torque_nm()
        result = original_execute(runtime, **kwargs)
        if candidate.label.startswith("recovery_"):
            command, execution = result
            last_record = {"physics_before": physical, "estimated_state": state,
                "command": asdict(command), "components": command_components(command, bias),
                "execution": execution}
        return result

    production._execute_interval = intercept
    production.perf_counter = recorded_timer
    try:
        production.run_executed_case(output / "capture_prefix", qualification_case=case,
            qualification_arm="continual_adaptive", simulate_planning_latency=True,
            dev_a_recovery=True, formal_qualification=False)
    except Captured:
        pass
    finally:
        production._execute_interval = original_execute
        production.perf_counter = original_timer
    if not (output / "checkpoint.pkl.gz").exists():
        raise RuntimeError("production did not reach model activation")


def make_observation(state, measurement, version):
    return make_task_observation(state, sample_timestamp_s=measurement.sample_time_s,
        controller_timestamp_s=measurement.arrival_time_s, human_model_version=version)


def evaluate_chain(runtime, measurement, interface, mapped, model, state, *,
                   allocation_model=None, action_override=None):
    """Same production PD/ID/filter/supervisor, with explicit diagnostic slots."""
    allocation_model = model if allocation_model is None else allocation_model
    contract, plant = runtime["contract"], runtime["plant"]
    observation = make_observation(state, measurement, "NONDEPLOYABLE_DIAGNOSTIC")
    candidate = mapped.candidate
    ddq = contract.position_gain*(candidate.q_waypoint_rad-state[:2]) + contract.velocity_gain*(candidate.dq_waypoint_rad_s-state[2:])
    action = model.inverse_dynamics(state[:2], state[2:], ddq)
    if action_override is not None:
        action = np.asarray(action_override).copy()
    ctx = build_stage5_loaded_execution_context(plant=plant, measurement=measurement,
        observation=observation, interface_state=interface, human_model=allocation_model,
        cuff_allocator=runtime["allocator"], target=mapped.execution_target)
    # Retain production reference-history/acceleration validation as well as
    # force filtering. Geometry affects allocation but not this beta model's ID.
    prior_model=contract.human_model
    contract.human_model=replace(model,geometry=allocation_model.geometry)
    try:
        production_command=contract.command(plant=plant,measurement=measurement,
            observation=observation,interface_state=interface,mapped_waypoint=mapped)
    finally:
        contract.human_model=prior_model
    if action_override is None:
        if not np.allclose(action,production_command.generalized_action_nm,rtol=0,atol=1e-12):
            raise AssertionError("diagnostic inverse dynamics differs from production")
        selected=production_command.filter_result
    else:
        filt = ctx.make_force_filter()
        filt(action[None, :])
        selected = filt.selected_result(action)
    runtime["supervisor"].bind_loaded_execution(observation, interface, mapped.execution_target)
    decision = runtime["supervisor"].command(plant=plant, measurement=measurement,
        estimated_state=state, human_model=allocation_model, cuff_allocator=runtime["allocator"],
        track_reference=mapped.reference, proposed_action_nm=action, mpc_status=SAFE_ACTION,
        proposed_filter_result=selected)
    if decision.executable_preview is None:
        raise RuntimeError(decision.terminate_reason or "NO_EXECUTABLE_COMMAND")
    command = decision.executable_preview.command
    plant._measured_robot_model.set_configuration(measurement.robot_q_rad, measurement.robot_dq_rad_s)
    bias = plant._measured_robot_model.bias_torque_nm()
    allocation = runtime["allocator"].allocate(action, state[:2], allocation_model)
    factors = runtime["allocator"]._prepare_factors(state[:2], allocation_model)
    base = BaseParameterHumanModel(model.geometry, model.beta, model.rom_human)
    record = {
        "timestamp_s": measurement.sample_time_s, "measurement_age_s": measurement.age_s,
        "state": state.copy(), "reference": asdict(mapped.reference),
        "desired_acceleration_rad_s2": ddq, "generalized_action_nm": action,
        "base_zero_acceleration_action_nm": base.inverse_dynamics(state[:2],state[2:],np.zeros(2)),
        "mass_times_pd_acceleration_nm": model.mass_matrix(state[:2])@ddq,
        "residual_nm": model.state_residual_nm(state),
        "beta": model.beta.copy(), "residual_weights_nm": model.residual_weights_nm.copy(),
        "regressor_parameter_contributions_nm": dynamic_regressor_row(state[:2],state[2:],ddq)*model.beta[None,:],
        "allocation_human_wrench_world": allocation["wrench_world"],
        "allocation_residual_nm": allocation["allocation_residual_nm"],
        "allocation_matrix": factors.matrix, "action_to_wrench_world": factors.action_to_wrench_world,
        "allocation_singular_values": np.linalg.svd(factors.matrix, compute_uv=False),
        "allocation_dual_condition": float(np.linalg.cond(factors.dual_matrix)),
        "robot_from_human_world_m": ctx.robot_from_human_world_m,
        "command": asdict(command), "robot_torque_components": command_components(command,bias),
        "safety_mode": decision.mode, "filter_feasible": selected.feasible,
        "filter_diagnostics": decision.safety_filter,
        "session_clearance_m": production.SessionClearanceContract(allocation_model.geometry).evaluate(state[:2]),
        "robot_target": asdict(mapped.execution_target.robot_cuff_target),
    }
    return command, record


def load_checkpoint(path):
    with gzip.open(path, "rb") as stream:
        return pickle.load(stream)


def algebra(checkpoint, output):
    runtime, rec, kw = checkpoint["runtime"], checkpoint["recovery"], checkpoint["execute_kwargs"]
    plant = runtime["plant"]
    old, new = rec["old_model"], rec["target_model"]
    measurement, interface, mapped = kw["measurement"], kw["interface"], kw["mapped_override"]
    state_old = old.geometry.estimate_state(interface.human_position_world_m,interface.human_rotation_world,
        interface.human_velocity_world_m_s,interface.human_angular_velocity_world_rad_s)
    state_new = kw["observation"].as_array()
    state_true = np.r_[plant.data.qpos[plant.human_qpos_indices],plant.data.qvel[plant.human_dof_indices]]
    records = {}
    # Same runtime physical state; fresh deep-copied controller for each query.
    for name, model, state, geom_model in [
        ("old_model_old_estimate",old,state_old,old),
        ("new_model_old_estimate_old_allocation",new,state_old,old),
        ("old_model_new_estimate_old_allocation",old,state_new,old),
        ("new_model_new_estimate_old_allocation",new,state_new,old),
        ("new_model_new_estimate",new,state_new,new),
        ("old_model_new_estimate",old,state_new,new),
        ("new_model_old_estimate",new,state_old,new),
        ("old_model_true_state",old,state_true,old),
        ("new_model_true_state",new,state_true,new),
        ("new_beta_zero_residual",replace(new,residual_weights_nm=np.zeros((2,5))),state_new,new),
        ("old_beta_new_residual",replace(new,beta=old.beta),state_new,new),
    ]:
        original_supervisor = runtime["supervisor"]
        runtime["supervisor"] = copy.deepcopy(original_supervisor)
        _, records[name] = evaluate_chain(runtime,measurement,interface,mapped,model,state,allocation_model=geom_model)
        runtime["supervisor"] = original_supervisor
    # Verify reimplementation against production command (history/filter exact).
    contract = copy.deepcopy(runtime["contract"])
    expected = contract.command(plant=plant,measurement=measurement,observation=kw["observation"],
        interface_state=interface,mapped_waypoint=mapped)
    expected_command = expected.filter_result.filtered_preview.command
    got = records["new_model_new_estimate"]
    agreement = np.max(np.abs(expected_command.joint_torque_command_nm-np.array(got["command"]["joint_torque_command_nm"])))
    if agreement > 1e-10 or np.max(np.abs(expected.generalized_action_nm-got["generalized_action_nm"]))>1e-10:
        raise AssertionError("diagnostic chain differs from production")
    context_candidate=replace(mapped.candidate,execution_context=WaypointExecutionContext.COMMISSIONING)
    context_mapped=replace(mapped,candidate=context_candidate)
    context_contract=copy.deepcopy(runtime["contract"])
    context_command=context_contract.command(plant=plant,measurement=measurement,
        observation=kw["observation"],interface_state=interface,mapped_waypoint=context_mapped)
    context_delta=context_command.filter_result.filtered_preview.command.joint_torque_command_nm-expected_command.joint_torque_command_nm
    # Fixed q and identical generalized action isolate allocation geometry.
    u = got["generalized_action_nm"]
    allocations = {}
    for name,m in [("old",old),("new",new)]:
        factors=runtime["allocator"]._prepare_factors(state_new[:2],m)
        allocations[name] = {"result":runtime["allocator"].allocate(u,state_new[:2],m),
            "singular_values":np.linalg.svd(factors.matrix,compute_uv=False),
            "dual_condition":np.linalg.cond(factors.dual_matrix),
            "action_to_wrench":factors.action_to_wrench_world,
            "geometry":asdict(m.geometry)}
    # Fixed measured robot pose/twist implies identical execution context. No
    # alternative execution controller is necessary when this closure holds.
    actual_interface=plant._evaluate_current_interface()
    true_generalized=(plant._site_pose_jacobian(plant.sleeve_site_id)[:,plant.human_dof_indices].T
                      @actual_interface.human_wrench_world)
    true_acceleration=plant.data.qacc[plant.human_dof_indices].copy()
    prediction={}
    for mn,m in [("old",old),("new",new)]:
        for sn,s in [("old_estimate",state_old),("new_estimate",state_new),("true_state",state_true)]:
            ddq=m.continuous_dynamics(s,true_generalized)[2:]
            prediction[mn+"_"+sn]={"predicted_ddq_rad_s2":ddq,
                "error_vs_true_ddq_rad_s2":ddq-true_acceleration,
                "inverse_dynamics_residual_nm":m.inverse_dynamics(s[:2],s[2:],true_acceleration)-true_generalized}
    save_json(output / "algebra.json", {"schema":SCHEMA,"state_old":state_old,"state_new":state_new,
        "state_true_evaluation_only":state_true,"records":records,"allocations":allocations,
        "production_command_max_abs_difference_nm":agreement,
        "commissioning_vs_active_recovery_context_torque_delta_nm":context_delta,
        "prediction_evaluation_only":prediction,
        "true_transmitted_generalized_input_nm_evaluation_only":true_generalized,
        "true_acceleration_rad_s2_evaluation_only":true_acceleration,
        "previous_command_record":checkpoint["previous_command_record"],
        "observation":asdict(measurement),"interface_estimate":asdict(interface),
        "physical_at_checkpoint":physics_record(plant),
        "world_from_robot_base":asdict(plant.geometry.world_from_base),
        "allocation_note":"force N and moment Nm analyzed separately; singular values of mixed-unit B are diagnostics, not a unitless physical conditioning claim"})
    return records


def guard(runtime, rec, observation, interface, measurement):
    state=observation.as_array()
    split=runtime["monitor"].update(sample_timestamp_s=observation.sample_timestamp_s,
        estimated_dq_rad_s=state[2:],cuff_force_world_n=interface.measured_force_world_n,
        cuff_moment_world_nm=interface.measured_moment_world_nm,
        interface_translation_human_m=interface.displacement_human_m,
        interface_velocity_human_m_s=interface.velocity_human_m_s,
        interface_rotation_human_rad=interface.rotation_error_human_rad,
        interface_angular_velocity_human_rad_s=interface.angular_velocity_human_rad_s,
        command_wrench_world=runtime["last_command"].wrench_total_world,
        robot_joint_torque_command_nm=runtime["last_command"].joint_torque_command_nm)
    authority=runtime["authority"].evaluate(split)
    reason=authority.abort_reason if authority.violation else task_limit_violation(rec["spec"],state[:2],state[2:],
        split.human_motion_acceleration_rad_s2,acceleration_authority_valid=split.human_motion_valid)
    if reason is None and np.linalg.norm(interface.measured_force_world_n)>rec["config"]["cuff_force_limit_n"]+1e-9:
        reason="REALIZED_CUFF_FORCE_LIMIT"
    if reason is None and np.linalg.norm(interface.measured_moment_world_nm)>rec["config"]["cuff_moment_limit_nm"]+1e-9:
        reason="REALIZED_CUFF_MOMENT_LIMIT"
    if reason is None and np.any(np.abs(measurement.robot_dq_rad_s)>CR12_VELOCITY_LIMITS_RAD_S+1e-9):
        reason="CR12_VELOCITY_LIMIT"
    p=runtime["plant"]
    bounds=p.model.jnt_range[p.robot_joint_ids]
    if reason is None and np.any((measurement.robot_q_rad<bounds[:,0]-1e-9)|(measurement.robot_q_rad>bounds[:,1]+1e-9)):
        reason="CR12_POSITION_LIMIT"
    if reason is None and rec["clearance"].evaluate(state[:2]) < -1e-9:
        reason="SESSION_CLEARANCE_LIMIT"
    return reason


def physical_branch(checkpoint, name, duration_s, output):
    cp=copy.deepcopy(checkpoint)
    runtime,rec,kw=cp["runtime"],cp["recovery"],cp["execute_kwargs"]
    plant=runtime["plant"]
    initial_state=integration_state(plant)
    if not np.array_equal(initial_state,integration_state(checkpoint["runtime"]["plant"])):
        raise AssertionError("checkpoint clone integration state mismatch")
    random.setstate(cp["python_random_state"])
    np.random.set_state(cp["numpy_random_state"])
    old,new=rec["old_model"],rec["target_model"]
    model=old if name in ("retained_model","old_model_new_estimate") else new
    estimate_model=old if name in ("retained_model","new_model_old_estimate") else new
    segment=rec["active_segment"]
    if duration_s>segment["schedule"].duration_s+1e-12:
        raise ValueError("bounded branch must not cross first scheduled segment")
    records,physics=[],[physics_record(plant)]
    reason=None
    # Narrow diagnostic intervention: preserve the new model but fade one
    # INITIAL generalized-action offset over 100 ms. Not a production repair.
    initial_interface=kw["interface"]
    old_state=old.geometry.estimate_state(initial_interface.human_position_world_m,
        initial_interface.human_rotation_world,initial_interface.human_velocity_world_m_s,
        initial_interface.human_angular_velocity_world_rad_s)
    new_state=kw["observation"].as_array()
    ref=kw["candidate"]
    kp,kd=runtime["contract"].position_gain,runtime["contract"].velocity_gain
    initial_offset=(old.inverse_dynamics(old_state[:2],old_state[2:],kp*(ref.q_waypoint_rad-old_state[:2])+kd*(ref.dq_waypoint_rad_s-old_state[2:]))
                    -new.inverse_dynamics(new_state[:2],new_state[2:],kp*(ref.q_waypoint_rad-new_state[:2])+kd*(ref.dq_waypoint_rad_s-new_state[2:])))
    for step in range(round(duration_s/DT)):
        if step==0:
            measurement=kw["measurement"]
            # Both old/new observer mappings share the exact cached inversion.
        else:
            measurement=runtime["measurement_layer"].update(plant.observe())
        observation,interface=runtime["observer"].update(measurement,estimate_model,human_model_version=name)
        if step>0:
            reason=guard(runtime,rec,observation,interface,measurement)
        else:
            state0=observation.as_array()
            reason=task_limit_violation(rec["spec"],state0[:2],state0[2:],None,
                acceleration_authority_valid=False)
            if reason is None and rec["clearance"].evaluate(state0[:2]) < -1e-9:
                reason="SESSION_CLEARANCE_LIMIT"
        if reason:
            break
        elapsed=float(plant.data.time)-segment["start_time_s"]
        sample=segment["schedule"].sample(elapsed)
        candidate=production._candidate(f"dev_b_{name}_{step}",TaskPhase.RETURN,sample.q_rad,sample.dq_rad_s,
            rec["spec"],WaypointExecutionContext.ACTIVE_RECOVERY)
        # Fixed reference computed by the candidate model in every branch;
        # old-model continuation isolates ID/state, not reference redesign.
        runtime["contract"].human_model=new
        mapped=runtime["contract"].prepare(candidate)
        mapped=mapped_with_bridge(mapped,candidate,sample.q_rad,sample.dq_rad_s,sample.ddq_rad_s2,
            segment["bridge"],elapsed)
        # For model-vs-state factorial branches, allocation geometry follows
        # the estimator model. This relation is documented in the branch table.
        action_override=None
        transfer_fraction=0.0
        if name=="diagnostic_action_transfer_100ms":
            s=float(np.clip(elapsed/0.100,0,1))
            transfer_fraction=1-(10*s**3-15*s**4+6*s**5)
            state=observation.as_array()
            ddq=kp*(sample.q_rad-state[:2])+kd*(sample.dq_rad_s-state[2:])
            action_override=new.inverse_dynamics(state[:2],state[2:],ddq)+transfer_fraction*initial_offset
        command,row=evaluate_chain(runtime,measurement,interface,mapped,model,observation.as_array(),allocation_model=estimate_model,action_override=action_override)
        row["diagnostic_action_offset_nm"]=transfer_fraction*initial_offset
        row["physics_before"]=physics_record(plant)
        plant.apply_executable_command(command)
        for _ in range(round(DT/production.NOMINAL_PHYSICS_DT_S)):
            plant.step()
            physics.append(physics_record(plant))
        runtime["last_command"]=command
        runtime["contract"].reference_motion_history.commit(measurement.sample_time_s,sample.q_rad,sample.dq_rad_s)
        records.append(row)
    # N intervals, N+1 physical boundaries. Commands attach to interval starts.
    save_json(output / f"{name}.json", {"schema":SCHEMA,"name":name,
        "duration_s":float(plant.data.time)-rec["now_s"],"requested_duration_s":duration_s,
        "initial_integration_state_sha256":hashlib.sha256(initial_state.tobytes()).hexdigest(),
        "abort_reason":reason,"records":records,"physics":physics,
        "final_integration_state_sha256":hashlib.sha256(integration_state(plant).tobytes()).hexdigest(),
        "truth_consumed_by_branch_control":False,
        "reference_policy":"same new-model certified first-segment q/dq and robot cuff bridge, no replanning",
        "model":name,"beta_residual_updates":0,
        "planner_age_at_capture_s":segment["plan_age_s"]})
    print(json.dumps({"branch":name,"duration_s":float(plant.data.time)-rec["now_s"],"abort":reason}),flush=True)


def analyze(checkpoint_dir, duration_s, branches):
    output=checkpoint_dir / f"analysis_{round(duration_s*1000):04d}ms"
    if output.exists():
        raise FileExistsError(output)
    output.mkdir()
    save_json(output/"command.json",{"schema":SCHEMA,"argv":sys.argv,"duration_s":duration_s,"branches":branches,
        "diagnostic_script_sha256":sha(__file__)})
    checkpoint=load_checkpoint(checkpoint_dir / "checkpoint.pkl.gz")
    original=integration_state(checkpoint["runtime"]["plant"])
    # Algebra only changes robot helper model/cache; use a separate clone so
    # every physical branch begins from the pristine serialized checkpoint.
    algebra(copy.deepcopy(checkpoint),output)
    for branch in branches:
        physical_branch(checkpoint,branch,duration_s,output)
    if not np.array_equal(original,integration_state(checkpoint["runtime"]["plant"])):
        raise AssertionError("analysis mutated source checkpoint")
    if "activated_model" in branches and "activated_duplicate" in branches:
        a=json.loads((output/"activated_model.json").read_text())
        b=json.loads((output/"activated_duplicate.json").read_text())
        delta=max(float(np.max(np.abs(np.array(x["q_true_rad"])-np.array(y["q_true_rad"]))))
            for x,y in zip(a["physics"],b["physics"]))
        same=(a["final_integration_state_sha256"]==b["final_integration_state_sha256"])
        save_json(output/"clone_validation.json",{"duplicate_physics_exact":same,"max_q_delta_rad":delta,
            "physics_boundary_counts":[len(a["physics"]),len(b["physics"])],
            "initial_hash_equal":a["initial_integration_state_sha256"]==b["initial_integration_state_sha256"]})
        if not same:
            raise AssertionError("duplicate activated physical branches differ")
    manifest_path=checkpoint_dir/"capture_manifest.json"
    if manifest_path.exists() and "activated_model" in branches:
        manifest=json.loads(manifest_path.read_text())
        historical=np.load(Path(manifest["historical_path"])/"trace.npz",allow_pickle=True)
        result=json.loads((output/"activated_model.json").read_text())
        max_state=max_command=max_estimate=0.0
        for row in result["records"]:
            indices=np.flatnonzero(np.isclose(historical["time_s"],row["timestamp_s"],rtol=0,atol=1e-10))
            idx=int(indices[-1])
            actual=np.r_[row["physics_before"]["q_true_rad"],row["physics_before"]["dq_true_rad_s"]]
            max_state=max(max_state,float(np.max(np.abs(actual-historical["evaluation_only_human_state_rad_rad_s"][idx]))))
            max_command=max(max_command,float(np.max(np.abs(np.array(row["command"]["joint_torque_command_nm"])-historical["cr12_actuator_command_nm"][idx]))))
            max_estimate=max(max_estimate,float(np.max(np.abs(np.array(row["state"])-historical["estimated_human_state_rad_rad_s"][idx]))))
        save_json(output/"historical_replay_validation.json",{"max_abs_state_difference_rad_rad_s":max_state,
            "max_abs_estimate_difference_rad_rad_s":max_estimate,"max_abs_command_difference_nm":max_command,
            "interval_count":len(result["records"]),"historical_source":manifest["historical_path"]})
        if max_state>1e-9 or max_command>1e-7 or max_estimate>1e-9:
            raise AssertionError("activated branch does not reproduce historical trajectory")


def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="mode",required=True)
    c=sub.add_parser("capture")
    c.add_argument("--case",type=Path,required=True)
    c.add_argument("--historical",type=Path,required=True)
    c.add_argument("--output",type=Path,required=True)
    a=sub.add_parser("analyze")
    a.add_argument("--checkpoint-dir",type=Path,required=True)
    a.add_argument("--duration",type=float,default=0.2)
    a.add_argument("--branches",nargs="+",default=["retained_model","activated_model","activated_duplicate","new_model_old_estimate","old_model_new_estimate"])
    args=p.parse_args()
    if args.mode=="capture":
        capture(args.case,args.historical,args.output)
    else:
        analyze(args.checkpoint_dir,args.duration,args.branches)


if __name__=="__main__":
    main()
