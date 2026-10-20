"""Add causal bookkeeping hooks to a new runtime; leave all inherited files unchanged."""
from pathlib import Path
import json, hashlib, difflib, shutil
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_overnight_research_retrospective_v1/source');S=R/'stages/stage5_personalized_motion_learning'
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/single_human_sac_work')
P=S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1';D=S/'docs/single_human_sac_expert_v1'
original=(P/'runtime_online_v1.py').read_text();text=original
def replace(a,b):
    global text
    assert text.count(a)==1,(a[:80],text.count(a))
    text=text.replace(a,b,1)
replace('    online_target_callback: Any = None,\n)', '    online_target_callback: Any = None,\n    sac_hooks: Any = None,\n)')
replace('        previous_task_state = task_state\n', '        previous_task_state = task_state\n        if sac_hooks is not None:\n            sac_hooks.tick(physical_now-task_start_time, interface, observation, task_state, spec)\n')
replace('        task_state = reference_safe_task_transition(\n', '        if sac_hooks is not None:\n            transition_reference_ready = transition_reference_ready and sac_hooks.transition_allowed(previous_task_state)\n        task_state = reference_safe_task_transition(\n')
replace('observation=observation, belief=belief, interface=interface, spec=spec)\n                owned_now', 'observation=observation, belief=belief, interface=interface, spec=spec, task_state=task_state)\n                owned_now')
replace('                online_next_command_s += online_command_period_s\n', '                if sac_hooks is not None:\n                    sac_hooks.realized(row, online_owner.target, online_owner.sample(physical_now), physical_now-task_start_time)\n                online_next_command_s += online_command_period_s\n')
# Compact mode still retains the exact boundary trace in memory for accounting.
# High-rate disk artifacts are only saved in qualified evaluation/forensics mode.
replace('    (output_dir / "summary.json").write_text(', '    if sac_hooks is None or sac_hooks.retain_trace:\n        (output_dir / "summary.json").write_text(')
start=text.index('    if sac_hooks is None or sac_hooks.retain_trace:\n        (output_dir / "summary.json").write_text(')
end=text.index('    if session_context is not None:\n        session_context.update(runtime=runtime',start)
block=text[start:end]
lines=block.splitlines(True)
# Already indented first line and write_text line; indent the rest of the original save block.
text=text[:start]+lines[0]+lines[1]+''.join('    '+line if line.strip() else line for line in lines[2:])+text[end:]
replace('            persist_runtime_artifacts(output_dir, runtime_capture)\n', '            if sac_hooks is None or sac_hooks.retain_trace:\n                persist_runtime_artifacts(output_dir, runtime_capture)\n')
# Both normal and exceptional wrapper finalization paths invoke persistence.
text=text.replace('            persist_runtime_artifacts(output_dir, capture)\n','            if kwargs.get("sac_hooks") is None or kwargs["sac_hooks"].retain_trace:\n                persist_runtime_artifacts(output_dir, capture)\n')
compile(text,'runtime_sac_expert_v1.py','exec')
destination=P/'runtime_sac_expert_v1.py';destination.write_text(text)
(D/'RUNTIME_SAC_EXPERT_V1.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),fromfile='runtime_online_v1.py(frozen)',tofile='runtime_sac_expert_v1.py')))
shutil.copy2(destination,W/destination.name)
shutil.copy2(W/'build_runtime.py',S/'scripts/single_human_sac_expert_v1/build_runtime.py')
print(json.dumps(dict(runtime=str(destination),sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),diff_lines=len((D/'RUNTIME_SAC_EXPERT_V1.patch').read_text().splitlines()))))
