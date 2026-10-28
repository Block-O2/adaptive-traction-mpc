"""Two-factor compiler replay at fixed historical requests; zero plant steps."""
from pathlib import Path
import sys,os,json,time
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
P=Path(__file__).resolve().parents[1];sys.path[:0]=[str(P/'source'),str(P/'runtime/control'),str(P/'runtime/code')]
import scheduler_replay as base
from acl2_shared import put,sha
import numpy as np
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointCandidate
from traction_mpc_stage5.task import TaskPhase
O=P.parent/'autonomous_coordination_learning_v2';f=O/'runtime/source/results/MOTION_MARGIN_BACKOFF_RPASS_020/summary.json';su=json.loads(f.read_text());rows=[];start=time.time()
for lr in su['learning_records']:
 m=lr['selected_plan']['execution_screen'].get('coordination_modal_v2')
 if not m:continue
 s=lr['selected_plan']['schedule'];x=np.array(m['parameters']);phase=m['phase'];slot=m['slot'];goal=np.radians([120,120] if phase=='OUTBOUND' else [5.5,9.5]);target=np.array(m['original_target_rad']);locked=abs(target-goal)<=1e-10;j=0 if phase=='OUTBOUND' else 2;k=4 if j==0 else 5;v=6 if j==0 else 7;w=m['weight'];direction=1 if j==0 else -1;shift=np.radians(.30)*w*direction*np.array([x[j]+x[j+1],x[j]-x[j+1]]);factor=1+.08*x[k]*w;parent=m['original_duration_s'];velocity=np.array(m['proposed_pass_velocity']);elapsed=next(d['phase_elapsed_s'] for d in su['decisions'] if abs(d['decision_request_time_s']-lr['request_time_s'])<1e-8)
 factors=[]
 for lock,floor in [(0,0),(1,0),(0,1),(1,1)]:
  delta=shift.copy()
  if lock:delta[locked]=0
  proposed=target+delta;candidate=HumanWaypointCandidate('factorial_mapping',TaskPhase[phase],np.array(base.spec.outbound_goal_target_rad if phase=='OUTBOUND' else base.spec.start_return_target_rad),proposed,velocity)
  kw=dict(current_q_hat_rad=np.array(s['start_q_rad']),current_dq_hat_rad_s=np.array(s['start_dq_rad_s']),candidate=candidate,phase_elapsed_s=elapsed)
  record=dict(endpoint_lock=bool(lock),duration_floor=bool(floor),proposed_target_rad=proposed,pass_velocity_rad_s=velocity,original_parent_duration_s=parent)
  try:
   minimum=base.sched.plan_reference_contract(**kw);duration=float(np.ceil((max(parent,minimum.duration_s)*factor if floor else minimum.duration_s*({1:1.1,4:1.2,5:1.5}.get(slot,1.) if phase=='RETURN' else 1.))/.005-1e-10)*.005)
   if False:duration=parent
   fixed=base.sched.plan_fixed_duration_reference_contract(**kw,duration_s=duration)
   record.update(minimum_duration_s=minimum.duration_s,compiled_duration_s=fixed.duration_s,scheduler_certificate='PASS')
  except Exception as e:record.update(scheduler_certificate='REJECTED',error=str(e))
  factors.append(record)
 rows.append(dict(decision_index=lr['decision_index'],phase=phase,slot=slot,locked_joints=locked,original_target_rad=target,actual_target_rad=s['target_q_rad'],actual_duration_s=s['duration_s'],factorial=factors))
out=dict(status='EXECUTED_ZERO_PHYSICS_REQUEST_MAPPING',rows=rows,source_summary_sha256=sha(f),physical_steps=0,wall_s=time.time()-start,scope='Same recorded q/dq/request and modal coordinates; changing endpoint locks and duration policy separately. Scheduler-only candidate certification; full planner acceptance and trajectory effects require actual factorial branches.',coordinate_relation='New8 coordinates are not a reparameterization of full18D. Common executable subset requires matched target/pass/duration/certificate at every request; x=0 returns the same H150 adjunct reference. Neither full-family containment nor same-budget efficiency follows.')
put('analysis/PERMISSION_FACTOR_MAPPING.json',out);print('ROWS',len(rows),'wall',out['wall_s']);print([(r['phase'],r['slot'],r['locked_joints'].tolist(),[(z['endpoint_lock'],z['duration_floor'],z.get('compiled_duration_s'),z['scheduler_certificate']) for z in r['factorial']]) for r in rows])
