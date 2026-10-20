"""Offline chronology of reference, tracking, feedback, commands and native peaks."""
from pathlib import Path
import json,os,gzip,ast
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
P=Path(__file__).resolve().parents[1];S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies');A=S/'m2_18d_autonomous_review_v1';Q=S/'m2_18d_baseline_qualification_v1'
tree=ast.parse((P/'control/diagnose.py').read_text());utility=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['items','clean']],type_ignores=[]);exec(compile(utility,'diagnostic_utilities','exec'))
def put(n,x):(P/n).write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
rows={}
for root,ident in [(A,'N2_B'),(A,'N2_E'),(Q,'N1_E')]:
 f=root/'source/results'/ident;z=np.load(f/'trace.npz');mask=z['stage']=='TASK';t0=z['time_s'][mask][0];t=z['time_s']-t0;rt=json.loads(gzip.open(f/'runtime_artifacts.json.gz','rt').read());m=np.load(root/'motion_series'/(ident+'.npz'));nt=m['time_s']-t0;a=np.rad2deg(m['acceleration_rad_s2']);q=np.rad2deg(m['true_q_rad']);v=np.rad2deg(m['true_dq_rad_s']);ref=np.load(f/'native_reference.npz')['data'];ix=(ref[:,0]>6.8)&(ref[:,0]<7.4);indexes=np.flatnonzero(ix);ai=indexes[np.argmax(abs(ref[ix,6]))];pi=np.argmax(abs(a[:,1]));peak=nt[pi]
 receipts=[r for r in items(f/'runtime_artifacts.json.gz','command_receipts') if r.get('applied') and 6.75<=r['start_physics_s']-t0<=7.4]
 attempts=[r for r in rt['execution_attempts'] if 6.75<=r.get('start_physics_s',-999)-t0<=7.4]
 samples=[]
 for sample in [6.78,6.83,ref[ai,0],7.05,peak,peak+.05]:
  k=int(np.argmin(abs(t-sample)));n=int(np.argmin(abs(nt-sample)));r=int(np.argmin(abs(ref[:,0]-sample)))
  chosen=[x for x in receipts if x['start_physics_s']-t0<=nt[n]+1e-10<x['end_physics_s']-t0+1e-10]
  samples.append(dict(anchor_task_s=sample,trace_task_s=t[k],native_task_s=nt[n],native_q_deg=q[n],native_dq_deg_s=v[n],native_acceleration_deg_s2=a[n],issued_sample=ref[r],estimated_q_dq=z['estimated_human_state_rad_rad_s'][k],actual_q_dq=z['evaluation_only_human_state_rad_rad_s'][k],tracking_error_q_deg=np.rad2deg(z['evaluation_only_human_state_rad_rad_s'][k,:2]-z['reference_q_rad'][k]),tracking_error_dq_deg_s=np.rad2deg(z['evaluation_only_human_state_rad_rad_s'][k,2:]-z['reference_dq_rad_s'][k]),robot_torque_nm=z['cr12_actuator_command_nm'][k],robot_components_nm={part:z['robot_torque_component_'+part+'_nm'][k] for part in ['base','position','velocity','allocator','clipping']},applied_generalized_action_nm=z['applied_generalized_action_nm'][k],force_N=z['physical_cuff_force_world_n'][k],moment_Nm=z['physical_cuff_moment_world_nm'][k],owner_receipt=chosen))
 rows[ident]=dict(issued_knee_terminal_acceleration_peak=dict(task_s=ref[ai,0],value_deg_s2=np.rad2deg(ref[ai,6])),actual_peak=dict(task_s=peak,value_deg_s2=a[pi,1]),samples=samples,positive_receipts=receipts,execution_attempts=attempts)
put('derived/RESPONSE_CHANNELS.json',rows)
print('RESPONSE_CHANNELS',[(k,v['issued_knee_terminal_acceleration_peak'],v['actual_peak']) for k,v in rows.items()])
