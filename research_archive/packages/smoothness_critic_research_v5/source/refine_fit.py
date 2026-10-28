"""Bounded approximation in all18 parameters, preserving original endpoint invariants."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import json,numpy as np
from scipy.optimize import minimize,lsq_linear
P=Path(__file__).resolve().parents[1];O=Path('/home/hank/ihear-lab/smoothness_critic_research_v5');d=json.loads((O/'runtime/source/results/MOTION_MARGIN_BACKOFF_RPASS_020/summary.json').read_text());lrs=d['learning_records'];case=json.loads((O/'runtime/source/stages/stage5_personalized_motion_learning/configs/high_rom_v1/high_rom_nominal_sync_120_v1.json').read_text());start=np.radians(case['task']['start_deg']);goal=np.radians(case['task']['goal_deg']);span=goal-start
scales=np.array([z['scale'] for z in json.loads((O/'runtime/PARAMETER_MAP.json').read_text())['parameters']]);x=np.array(json.loads((P/'analysis/OLD18D_MATCH.json').read_text())['candidate_full18d_for_physics']);records=[]
for ph,inds,indices in [('OUTBOUND',[1,2,3,4],[0,10,11,1,2,12]),('RETURN',[8,9,10,11,12],[5,14,15,6,7,16])]:
 st,sp=(start,span) if ph=='OUTBOUND' else (goal,-span);AA=[];yy=[];qnative=[]
 for ix in inds:
  lr=lrs[ix];q=np.array(next(c for c in lr['candidate_set'] if c['label'].endswith('_dq_07'))['target_q_rad'])
  fm=next((c['execution_screen']['free_trajectory'] for c in lr['candidate_set'] if c['execution_screen'].get('free_trajectory',{}).get('original_target') is not None),None)
  if fm:q=np.array(fm['original_target'])
  target=np.array(lr['selected_plan']['target_q_rad'])
  if ph=='RETURN' and ix in [10,11]:target-=np.radians([.3,-.3])
  m=np.mean((q-st)/sp);u=2*m-1;e=np.sin(np.pi*np.clip(m,0,1))**2;b=e*np.array([1,u,u*u]);AA.append(np.vstack([sp[0]*np.r_[b,b],sp[1]*np.r_[b,-b]]));yy.append(target-q);qnative.append(q)
 A=np.vstack(AA);y=np.concatenate(yy);lim=scales[indices];lockedrow=6 if ph=='OUTBOUND' else 9
 # Normalize variables, exact scalar joint-endpoint equality before original verification.
 B=A*lim;initial=x[indices]/lim;constraints={'type':'eq','fun':lambda z: (B[lockedrow]@z-y[lockedrow]),'jac':lambda z:B[lockedrow]}
 result=minimize(lambda z:float(np.sum((B@z-y)**2)),initial,jac=lambda z:2*B.T@(B@z-y),method='SLSQP',bounds=[(-1,1)]*6,constraints=constraints,options={'ftol':1e-20,'maxiter':150})
 x[indices]=result.x*lim;records.append({'phase':ph,'success':bool(result.success),'message':result.message,'coefficients':x[indices].tolist(),'residual_deg':np.degrees(A@x[indices]-y).tolist(),'L2_rad':float(np.linalg.norm(A@x[indices]-y)),'locked_equation_residual_rad':float(A[lockedrow]@x[indices]-y[lockedrow])})
(P/'analysis/OLD18D_REFINED_FIT.json').write_text(json.dumps({'parameters':x.tolist(),'path_fits':records,'scope':'Approximation fitted to saved best states, not closed-loop equivalence; exact native admission and physical scoring still required. All18 parameters available; no new timing/slot permissions.'},indent=2)+'\n');print(json.dumps(records))
