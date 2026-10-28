"""Zero-physics necessary-condition matching of all old18D path coefficients.
Enumerates every pre-18D OUTBOUND grid candidate at recorded requests 1..4.
Feasibility/ranking are deliberately relaxed: this is a superset of old permissions.
"""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
from pathlib import Path
import json,itertools,hashlib,time
import numpy as np
from scipy.optimize import lsq_linear
P=Path(__file__).resolve().parents[1];O=Path('/home/hank/ihear-lab/autonomous_coordination_learning_v2');R=O/'runtime'
def save(n,d):(P/n).write_text(json.dumps(d,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
t0=time.time();su=json.loads((R/'source/results/MOTION_MARGIN_BACKOFF_RPASS_020/summary.json').read_text());lrs=su['learning_records'];start=np.array(lrs[-1]['selected_plan']['target_q_rad']);goal=np.array(lrs[5]['selected_plan']['target_q_rad']);span=goal-start
old=np.array(json.loads((R/'FROZEN_18D.json').read_text())['free_parameters']);old[[1,6]]+=.002*np.array([.8245887463260377,-.9835625245511301]);scales=np.array([x['scale'] for x in json.loads((R/'PARAMETER_MAP.json').read_text())['parameters']]);idx=[0,10,11,1,2,12]
slots=[]
for lr in lrs[1:5]:
 target=np.array(lr['selected_plan']['target_q_rad']);cs=[]
 for c in lr['candidate_set']:
  if not c['label'].startswith('outbound_dq_'):continue
  q=np.array(c['target_q_rad']);m=np.mean((q-start)/span);e=np.sin(np.pi*np.clip(m,0,1))**2;u=2*m-1;b=e*np.array([1,u,u*u]);mat=np.vstack([span[0]*np.r_[b,b],span[1]*np.r_[b,-b]]);y=target-q
  cs.append({'label':c['label'],'q':q,'m':m,'matrix':mat,'y':y})
 slots.append({'decision':lr['decision_index'],'target':target,'candidates':cs})
rows=[];best=None
for combo in itertools.product(*[s['candidates'] for s in slots]):
 A=np.vstack([c['matrix'] for c in combo]);y=np.concatenate([c['y'] for c in combo]);x=np.linalg.lstsq(A,y,rcond=None)[0];err=A@x-y;score=float(np.linalg.norm(err))
 item={'labels':[c['label'] for c in combo],'unbounded_L2_rad':score,'unbounded_max_abs_rad':float(np.max(abs(err))),'coefficients':x.tolist(),'within_domain':bool(np.all(abs(x)<=scales[idx]+1e-12))}
 rows.append(item)
 if best is None or score<best[0]:best=(score,combo,A,y,x)
bounded_best=None;bounded_count=0
for combo in itertools.product(*[s['candidates'] for s in slots]):
 A=np.vstack([c['matrix'] for c in combo]);y=np.concatenate([c['y'] for c in combo])
 # Necessary per-row interval reachability rejects impossible grid choices.
 if np.any(abs(y)>np.abs(A)@scales[idx]+1e-12):continue
 bounded_count+=1;fit=lsq_linear(A,y,bounds=(-scales[idx],scales[idx]),tol=1e-14,max_iter=200);cost=float(np.linalg.norm(A@fit.x-y))
 if bounded_best is None or cost<bounded_best[0]:bounded_best=(cost,combo,A,y,fit)
assert bounded_best is not None
A,y,fit=bounded_best[2:];x=old.copy();x[idx]=fit.x
# Fit old passage-velocity coefficients on the target states, with native formula reconstructed from saved schedules.
velocity=[]
for phase,velidx in [('OUTBOUND',[3,4,13]),('RETURN',[8,9,17])]:
 AA=[];yy=[]
 for lr in lrs:
  s=lr['selected_plan']['schedule']
  if s['phase']!=phase:continue
  q=np.array(s['target_q_rad']);v=np.array(s['target_dq_rad_s']);modal=lr['selected_plan']['execution_screen'].get('coordination_modal_v2')
  if modal is None:continue
  native_q=np.array(modal['original_target_rad']);native_v=np.array(modal['original_pass_velocity']);orig_m=np.mean((native_q-(start if phase=='OUTBOUND' else goal))/(span if phase=='OUTBOUND' else -span));orig_e=np.sin(np.pi*np.clip(orig_m,0,1))**2;orig_u=2*orig_m-1
  vc,vd,vt=old[velidx];den=1+orig_e*np.array([vc+vd+vt*orig_u,vc-vd-vt*orig_u]);base=native_v/den
  m=np.mean((q-(start if phase=='OUTBOUND' else goal))/(span if phase=='OUTBOUND' else -span));e=np.sin(np.pi*np.clip(m,0,1))**2;u=2*m-1
  for j in range(2):
   if abs(base[j])<1e-10:continue
   AA.append(e*np.array([1,1 if j==0 else -1,u if j==0 else -u]));yy.append(v[j]/base[j]-1)
 av=np.array(AA);yv=np.array(yy);fv=lsq_linear(av,yv,bounds=(-scales[velidx],scales[velidx]),tol=1e-14);x[velidx]=fv.x
 velocity.append({'phase':phase,'coefficients':fv.x.tolist(),'residual_max_ratio':float(np.max(abs(av@fv.x-yv))),'scope':'approximate: native velocity reconstructed at pre-modal target, braking terms may change at desired target; not an infeasibility certificate'})
result={'status':'NO_EXACT_MATCH_IN_RECORDED_REQUEST_SUPERSET','physical_attempts':0,'native_steps':0,'scope':'Static full18D, identical causal states/request times and native grid at OUTBOUND slots 1..4, unchanged prefix/plant/H150 adjuncts. Every grid choice is allowed irrespective of feasibility/ranking. Does not prove no different motion can equal or beat JF/JM, nor arbitrary asynchronous polynomial resegmentation.','start_rad':start.tolist(),'goal_rad':goal.tolist(),'path_indices':idx,'candidate_counts':[len(s['candidates']) for s in slots],'combinations':len(rows),'best_unbounded':min(rows,key=lambda r:r['unbounded_L2_rad']),'bounded_reachable_combinations':bounded_count,'bounded_path_fit':{'labels':[c['label'] for c in bounded_best[1]],'coefficients':fit.x.tolist(),'residual_rad':(A@fit.x-y).tolist(),'L2_rad':float(np.linalg.norm(A@fit.x-y)),'max_abs_deg':float(np.max(abs(A@fit.x-y))*180/np.pi)},'candidate_full18d_for_physics':x.tolist(),'velocity_approximation':velocity,'wall_s':time.time()-t0}
save('analysis/OLD18D_MATCH.json',result);save('analysis/OLD18D_ALL_COMBINATIONS.json',rows)
save('analysis/OLD18D_MATCH_INPUTS.json',{'slots':[{'decision':s['decision'],'target':s['target'].tolist(),'candidates':[{'label':c['label'],'q':c['q'].tolist(),'m':c['m'],'matrix':c['matrix'].tolist(),'y':c['y'].tolist()} for c in s['candidates']]} for s in slots],'source':str(R/'source/results/MOTION_MARGIN_BACKOFF_RPASS_020/summary.json'),'sha256':hashlib.sha256((R/'source/results/MOTION_MARGIN_BACKOFF_RPASS_020/summary.json').read_bytes()).hexdigest()})
print(json.dumps(result,ensure_ascii=False))
