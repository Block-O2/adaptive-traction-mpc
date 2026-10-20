"""Pin the source lineage of seemingly ambiguous trace names."""
from pathlib import Path
import json,hashlib,time
import numpy as np
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
base=P/'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5'
runtime=base/'full3d_adaptive_integration_v1/runtime_coordination_v1.py';shadow=base/'human_waypoint_shadow.py'
src=runtime.read_text();ss=shadow.read_text()
snippets=['"cuff_force_world_n": interface.measured_force_world_n.copy()', '"cuff_moment_world_nm": interface.measured_moment_world_nm.copy()', '"actual_acceleration_rad_s2": split.human_motion_acceleration_rad_s2.copy()', 'estimated_dq_rad_s=state[2:]']
assert all(s in src for s in snippets)
assert 'self.position_gain * (candidate.q_waypoint_rad - state[:2])' in ss
assert '+ self.velocity_gain * (candidate.dq_waypoint_rad_s - state[2:])' in ss
rows=[]
for folder in [P.parent/'ihear_model_terminal_compensation_v1/source/results'/name for name in ['Ctrl_B','Ctrl_ER','Ctrl_H150','W2_B','W2_ER','W2_H150']]:
    z=np.load(folder/'trace.npz');mask=z['stage']=='TASK';valid=z['actual_human_acceleration_valid'][mask]
    for horizon in [20,40]:
        origins=np.arange(20,len(valid)-horizon,10);assert np.all(valid[origins])
    rows.append(dict(id=folder.name,all_selected_acceleration_origins_valid=True))
out=dict(status='PASS',unix=time.time(),runtime_sha256=hashlib.sha256(runtime.read_bytes()).hexdigest(),waypoint_contract_sha256=hashlib.sha256(shadow.read_bytes()).hexdigest(),source_snippets=snippets,trace_name_warning='physical_cuff_* are recorded from measured interface; actual_human_acceleration is the causal split estimate, not native evaluation truth',PD_request_formula='Kp*(q_reference-q_estimated)+Kd*(dq_reference-dq_estimated), no reference-acceleration term in this waypoint execution contract',validity_checks=rows,truth_role='native accelerations and future q/dq only offline labels/evaluation')
(P/'audit/FEATURE_SOURCE_LINEAGE.json').write_text(json.dumps(out,indent=2)+'\n')
print('FEATURE_LINEAGE_PASS',flush=True)
