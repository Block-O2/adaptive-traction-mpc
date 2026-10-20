from pathlib import Path
import json,shutil,hashlib,time,sys,copy
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_free_trajectory_feasibility_v1')
C=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_free_trajectory_feasibility_v1_control')
rev=S/'preservation/code_revisions';rev.mkdir(exist_ok=True)
p=S/'code/runner.py';shutil.copy2(p,rev/(hashlib.sha256(p.read_bytes()).hexdigest()+'.py'));shutil.copy2(C/'runner.py',p)
sys.path.insert(0,str(S/'code'))
import matched_harness as mh,analyze_matched as am
old=json.loads((S/'output/development_B0_original_DATA.json').read_text())
metric=json.loads((S/'output/development_B0_zero_extension.json').read_text())
snapshot=json.loads((S/'reports/development_B0_zero_extension_SNAPSHOT.json').read_text())
assert metric['task_valid'] is True
first=json.loads((S/'reports/development_B0_original_SNAPSHOT.json').read_text())
differences=[k for k in first['manifest'] if first['manifest'][k]!=snapshot['manifest'][k]]
assert differences==['coordination_state'],differences
assert first['manifest']['native_integration']==snapshot['manifest']['native_integration']
# Reconstruct only branch accounting/log metadata from preserved identical live snapshot.
# This is not physical replay and does not manufacture state or labels.
metric['actual_new_native_physics_steps']=metric['native_physics_steps']-old['child']['physics_step_at_fork']
metric['actual_new_simulation_seconds']=metric['simulation_seconds']-old['child']['physical_time_at_fork']
mh.put(S/'output/development_B0_zero_extension.json',metric)
d=copy.deepcopy(old);d.update(id='development_B0_zero_extension',metric=metric,logging_recovery=True,status='COMPLETE_PHYSICS_LOGGING_RECOVERED')
d['child'].update(kind='B0_zero_extension',snapshot_hash=snapshot['hash'])
d['branch_start'].update(full_hash=snapshot['hash'],native_hash=snapshot['native_hash'])
d['remaining_J_F']=metric['J_F'];d['remaining_M']=metric['moment_integral']
mh.put(S/'output/development_B0_zero_extension_DATA.json',d)
gate=mh.complete_gate('development_B0_original','development_B0_zero_extension')
mh.put(S/'WRAPPER_RECOVERED_ZERO_GATE.json',gate);assert gate['status']=='PASS'
m=am.measure('development_B0_zero_extension')
mh.put(S/'WRAPPER_REPAIR_REGISTERED.json',dict(unix=time.time(),reason='Own evaluation list collided with inherited reference rows at finish; renamed eval_rows; complete physical zero trace recovered read-only by exact live snapshot and full receipt/torque/q/dq repeat',original_error_preserved=True,gate=gate['status'],actual_physics_attempts_not_reset=True,wall_origin_unchanged=True,thresholds_unchanged=True,full_partial_parent_preserved=True,physics_semantics_unchanged=True))
print('REPAIRED_AND_ZERO_REPRODUCED')
