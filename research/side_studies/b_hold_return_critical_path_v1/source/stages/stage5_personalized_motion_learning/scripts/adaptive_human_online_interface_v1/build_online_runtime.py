"""Generate a versioned research runtime; original implementation remains frozen."""
from pathlib import Path
import difflib,hashlib,json,shutil
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1/source');S=R/'stages/stage5_personalized_motion_learning';D=S/'docs/adaptive_human_online_interface_v1'
P=S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1';original=(P/'runtime.py').read_text()
record=json.loads((D/'SOURCE_FINGERPRINTS.json').read_text());assert hashlib.sha256((P/'runtime.py').read_bytes()).hexdigest()==record[str((P/'runtime.py').relative_to(R))]
text=original.replace('    session_context: dict[str, Any] | None = None,\n) -> dict[str, Any]:','    session_context: dict[str, Any] | None = None,\n    online_command_period_s: float | None = None,\n    online_target_callback: Any = None,\n) -> dict[str, Any]:',1)
text=text.replace('    recovery_options = dict(autonomous_recovery_options or {})','    recovery_options = dict(autonomous_recovery_options or {})\n    if online_command_period_s is not None and online_command_period_s not in (.005, .01, .02, .05):\n        raise ValueError("invalid research command cadence")',1)
needle='    phase_previous = task_state.phase\n'
text=text.replace(needle,'    online_owner = None\n    online_phase = None\n    online_next_command_s = -math.inf\n    online_terminal_target = None\n    runtime["online_reference_records"] = []\n    if online_command_period_s is not None:\n        reference_governor = None  # Representation-specific progress preference; receipt safety remains active.\n'+needle,1)
start=text.index('        if (fallback_latch is not None and fallback_latch.mode == "BRAKING"\n                and active_schedule is fallback_bridge):',text.index('    for step in range(maximum_steps + 1):'))
end=text.index('        reference_state = np.concatenate([reference.q_rad, reference.dq_rad_s])',start)
old=text[start:end]
new='''        if online_command_period_s is not None:
            from .online_reference import OnlineReferenceOwner
            from .terminal_reference import select_robust_terminal_reference
            if online_owner is None or online_phase is not task_state.phase:
                online_phase = task_state.phase
                online_owner = OnlineReferenceOwner((reference_state[:2], reference_state[2:], reference_acceleration), epoch_s=physical_now)
                online_next_command_s = physical_now
                goal = np.asarray(spec.start_return_target_rad if task_state.phase is TaskPhase.RETURN else spec.outbound_goal_target_rad)
                selection = select_robust_terminal_reference(spec=spec, goal=goal, clearance=clearance, origin=reference_state[:2])
                if not selection["feasible"]:
                    task_state = abort_episode(task_state, "ONLINE_TERMINAL_REFERENCE_INFEASIBLE")
                    continue
                online_terminal_target = np.asarray(selection["reference_target_rad"])
                runtime["online_reference_records"].append(dict(event="PHASE_TARGET", phase=task_state.phase.value, selection=selection))
            if physical_now + 1e-12 >= online_next_command_s:
                intended = online_terminal_target.copy()
                if online_target_callback is not None:
                    intended = online_target_callback(task_state.phase, physical_now-task_start_time, intended, online_owner.sample(physical_now), observation=observation, belief=belief, interface=interface, spec=spec)
                owned_now = online_owner.sample(physical_now)
                vlimit = np.asarray(spec.task_joint_velocity_limit_rad_s)*scheduler.reference_velocity_fraction
                alimit = np.asarray(spec.task_joint_acceleration_limit_rad_s2)*scheduler.reference_acceleration_fraction
                row = online_owner.offer(intended, received_s=physical_now, ready_s=physical_now, requested_s=physical_now,
                    spec=spec, phase=task_state.phase, remaining_s=spec.phase_timeout_s-task_state.phase_elapsed_s,
                    belief=belief, clearance=clearance, max_velocity=vlimit, max_acceleration=alimit, max_jerk=alimit/.020,
                    tracking_error=state[:2]-owned_now.q_rad if recovery_options.get("causal_tracking_offset_clearance",False) else None)
                runtime["online_reference_records"].append(dict(phase=task_state.phase.value, **row))
                online_next_command_s += online_command_period_s
                if row["status"] == "BLOCKED_CONTINUATION_INVALIDATED" or online_owner.schedule is None:
                    task_state = abort_episode(task_state, "ONLINE_NO_CURRENT_CERTIFIED_CONTINUATION")
                    continue
            active_schedule = online_owner.schedule
            schedule_start_time = online_owner.schedule_epoch_s
            reference = online_owner.sample(physical_now)
        else:
'''+''.join('    '+line if line.strip() else line for line in old.splitlines(keepends=True))
text=text[:start]+new+text[end:]
text=text.replace('        "adaptation_trace": adaptation_trace,','        "adaptation_trace": adaptation_trace,\n        "online_reference_records": runtime.get("online_reference_records", []),\n        "online_interface_research_version": "local_ruckig_v1" if online_command_period_s is not None else None,',1)
text=text.replace('"model_version": observation.human_model_version,','"model_version": observation.human_model_version,')
assert text!=original
assert 'validate_activation(*' not in text # imported frozen validator remains untouched
(P/'runtime_online_v1.py').write_text(text)
(D/'ONLINE_RUNTIME_CHANGE.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),fromfile='runtime.py(frozen)',tofile='runtime_online_v1.py(research)')))
shutil.copy2('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/adaptive_human_online_work/online_reference.py',P/'online_reference.py')
print(json.dumps({'research_runtime':str(P/'runtime_online_v1.py'),'original_unchanged':True,'diff_lines':len((D/'ONLINE_RUNTIME_CHANGE.patch').read_text().splitlines())}))
