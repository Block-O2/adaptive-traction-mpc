from pathlib import Path
import json,numpy as np
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/single_human_sac_r2')
r=json.loads((W/'REQUESTS.json').read_text());print('REQUESTS',json.dumps([{k:x.get(k) for k in ('request_id','source_sample_time_s','fallback_intervals','fallback_physics_s','activation_simulation_version')} for x in r if 19<=x.get('source_sample_time_s',0)<=20.1]))
s=json.loads((W/'OLD_MATCHED_SUMMARY.json').read_text());print('DECISIONS',json.dumps([{k:d.get(k) for k in ('phase','decision_request_time_s','actual_schedule_start_physics_s','activation_timestamp_s','phase_elapsed_s','executed_label')} for d in s['decisions'] if 19<=d.get('decision_request_time_s',0)<=20.1]))
z=np.load(W/'old_matched_trace.npz');mask=z['stage']=='TASK';t=z['time_s'][mask]
for lo,hi in ((19.545,19.585),(20.045,20.081)):
 print('TRACE',json.dumps([{k:z[k][mask][i].tolist() for k in ('time_s','task_phase','selected_schedule_label','terminal_boundary_node','reference_dq_rad_s','reference_ddq_rad_s2')} for i in np.where((t>=lo)&(t<=hi))[0]]))
