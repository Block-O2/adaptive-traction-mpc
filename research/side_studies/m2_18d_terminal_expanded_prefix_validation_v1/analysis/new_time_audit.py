"""Offline reconstruction from immutable historical data; no plant/controller imports."""
from pathlib import Path
import os,sys,json,hashlib,collections,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
L=Path(__file__).resolve().parents[1];S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies');P=S/L.name;A=P
sys.path.insert(0,str(A/'control'));from independent_recompute import array_items
import numpy as np
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def quintic(s,t):
 q=np.asarray(s['start_q_rad']);v=np.asarray(s['start_dq_rad_s']);Q=np.asarray(s['target_q_rad']);V=np.asarray(s['target_dq_rad_s']);d=s['duration_s']
 a=np.linalg.solve(np.array([[d**3,d**4,d**5],[3*d**2,4*d**3,5*d**4],[6*d,12*d**2,20*d**3]]),np.stack([Q-q-v*d,V-v,np.zeros(2)]))
 t=min(max(t,0),d);pos=q+v*t+np.array([t**3,t**4,t**5])@a;vel=v+np.array([3*t*t,4*t**3,5*t**4])@a
 return pos,vel
rows=[]
for group in ['V1','V2']:
 for arm in ['E','T']:
  ident=group+'_'+arm;folder=A/'source/results'/ident;su=json.loads((folder/'summary.json').read_text());z=np.load(folder/'trace.npz');t0=float(z['time_s'][z['stage']=='TASK'][0]);goal=np.deg2rad([120,120]);pairs=[(lr,su['decisions'][lr['decision_index']]) for lr in su['learning_records'] if lr['selected_plan']['schedule']['phase']=='OUTBOUND' and np.max(abs(np.asarray(lr['selected_plan']['schedule']['target_q_rad'])-goal))<1e-10];assert len(pairs)==1
  lr,d=pairs[0];s=lr['selected_plan']['schedule'];activation=d['actual_schedule_start_physics_s'];bridge=d['rolling_composite']['splice_elapsed_s'];splice=activation+bridge;end=splice+s['duration_s'];hold=su['task']['phase_transitions'][0]['time_s']
  receipts=list(array_items(folder/'runtime_artifacts.json.gz','command_receipts'));positive=sorted([r for r in receipts if r.get('applied') and r.get('native_steps',0)>0],key=lambda r:r['start_physics_s']);selected=[r for r in positive if activation-1e-9<=r['start_physics_s']<hold-1e-9];suffix=[r for r in selected if r['start_physics_s']>=splice-1e-9];moving=[r for r in suffix if r['start_physics_s']<end-1e-9];carry=[r for r in suffix if r['start_physics_s']>=end-1e-9]
  assert abs(selected[0]['start_physics_s']-activation)<1e-8 and abs(moving[0]['start_physics_s']-splice)<1e-8
  assert abs(carry[0]['start_physics_s']-end)<1e-8
  errors=[];delays=[];refmax=0.
  for r in suffix:
   progress=r['reference_progress'];assert progress is not None
   elapsed=r['start_physics_s']-activation;expected=min(elapsed,bridge+s['duration_s']);assert abs(progress['selected_progress_s']-expected)<1e-8
   q,v=quintic(s,progress['selected_progress_s']-bridge);error=max(np.max(abs(q-r['q_ref_rad'])),np.max(abs(v-r['dq_ref_rad_s'])));refmax=max(refmax,float(error));assert error<1e-8
   delays.append(progress['delay_added_s'])
  assert max(delays)==0 and set(r['mode'] for r in selected)=={'TRACK'}
  assert all(abs(a['end_physics_s']-b['start_physics_s'])<1e-8 for a,b in zip(positive,positive[1:]))
  counter=collections.Counter();index=0;native=0;tail_native=0
  for n in array_items(folder/'runtime_artifacts.json.gz','native_states_evaluation_only'):
   begin=n.get('physical_interval_start_s',n['time_s']-.00025)
   while index+1<len(positive) and begin>=positive[index]['end_physics_s']-1e-9:index+=1
   r=positive[index];assert r['start_physics_s']-1e-8<=begin<r['end_physics_s']+1e-8 and n['command_torque_nm']==r['command_torque_nm'];counter[r['receipt_index']]+=1;native+=1
   if splice-1e-9<=begin<hold-1e-9:tail_native+=1
  assert all(counter[r['receipt_index']]==r['native_steps'] for r in positive)
  request_id=d.get('timing_request_id',d['rolling_composite']['request_id']);requests=[r for r in su['timing']['requests'] if r.get('request_id')==request_id];assert len(requests)==1 and requests[0]['outcome']=='ACTIVATED'
  cert=s['continuous_clearance_certificate'];assert cert['general_certificate']['feasible'] and lr['selected_plan']['execution_screen']['feasible']
  phase_times=[float(r['time_s']-t0) for r in su['task']['phase_transitions']];durations=np.diff([0.]+phase_times).tolist()
  ev=dict(id=ident,request_id=request_id,task_origin_physical_s=t0,request_task_s=d['decision_request_time_s']-t0,phase_elapsed_at_request_s=d['phase_elapsed_s'],activation_task_s=activation-t0,splice_task_s=splice-t0,suffix_duration_s=s['duration_s'],suffix_end_task_s=end-t0,composite_duration_s=d['rolling_composite']['total_duration_s'],endpoint_carry_until_HOLD_task_s=hold-t0,endpoint_carry_s=hold-end,phase_durations_s=durations,task_duration_s=phase_times[-1],suffix_positive_receipts=len(moving),carry_positive_receipts=len(carry),bridge_positive_receipts=len(selected)-len(suffix),terminal_modes=dict(collections.Counter(r['mode'] for r in selected)),progress_max_added_delay_s=max(delays),receipt_polynomial_max_error=refmax,native_rows_joined=native,terminal_native_steps=tail_native,all_receipt_torque_step_counts_match=True,direct_receipt_plan_request_id_present=any('plan_request_id' in r for r in selected),ownership_join='request activation physics stamp -> unique active composite / receipt progress and q,dq -> contiguous positive receipt intervals / exact torque and step counts -> native rows; original receipt has no direct plan_request_id',certificate=cert,request_record=requests[0],decision_fields={k:d.get(k) for k in ['current_state_admission','activation_outcome','activation_rejected_reason','actual_schedule_start_physics_s','rolling_composite','reference_boundary_continuity']},sources={str(folder/n):sha(folder/n) for n in ['summary.json','trace.npz','runtime_artifacts.json.gz','native_reference.npz']})
  rows.append(ev);put('audit/'+ident+'_NEW_TIME_EVIDENCE.json',ev);print(ident,'request',round(ev['request_task_s'],6),'splice',round(ev['splice_task_s'],6),'end',round(ev['suffix_end_task_s'],6),'carry',round(ev['endpoint_carry_s'],6),'native',native,flush=True)
for g in ['V1','V2']:
 e,t=[r for r in rows if r['id']==g+'_'+a for a in []] if False else ([next(r for r in rows if r['id']==g+'_'+a) for a in ['E','T']])
 assert abs(t['suffix_duration_s']-np.ceil(e['suffix_duration_s']*1.5/.005-1e-10)*.005)<1e-12
 assert e['phase_durations_s']==t['phase_durations_s']
 assert abs((e['endpoint_carry_s']-t['endpoint_carry_s'])-(t['suffix_duration_s']-e['suffix_duration_s']))<1e-8
# Capture exact frozen source rules with verified hashes and line numbers.
rules=[]
for relative,needle,radius in [('source/stages/stage5_personalized_motion_learning/scripts/single_human_sac_expert_v1/sac_env.py','def transition_allowed',4),('source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_coordination_residual_v2.py','sac_hooks.transition_allowed',7),('source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/receipt_reference_governor.py','selected_progress_s',5),('code/terminal_repair.py','class FixedTerminalScheduler',14)]:
 f=A/relative;lines=f.read_text().splitlines();hits=[i for i,line in enumerate(lines) if needle in line];assert hits
 for i in hits[:2]:rules.append(dict(path=str(f),sha256=sha(f),start_line=max(1,i-radius+1),text='\n'.join(f'{j+1}: {lines[j]}' for j in range(max(0,i-radius),min(len(lines),i+radius+1)))))
put('audit/EXPANDED_EXECUTION_TIME_AUDIT.json',dict(status='PASS',physical_started=True,unix=time.time(),new_rows=rows,rules=rules,explanation='Suffix extends inside pre-existing MATCHED minimum 9s OUTBOUND. Endpoint TRACK carry shortens exactly by suffix extension. No added progress delay, BRAKE switch or task/phase config change. Extra .005 phase and .020 HOLD are existing causal grid/state-transition behavior, identical across arms.',limitations=['PHYSICAL_LEVEL1 new frozen validation raw reconstruction only; no host realtime qualification','Receipt has no direct plan_request_id; link reconstructed using activation, active composite progress, exact polynomial boundary/reference and contiguous native torque/step ownership','Settling/tracking changes are downstream effects; no claim of equal physical state during shortened endpoint carry']))
