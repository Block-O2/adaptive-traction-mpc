"""Create isolated closure and preregister a small, motion-directed experiment."""
from pathlib import Path
import os,sys,json,shutil,hashlib,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
from scipy.optimize import minimize
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies');P=S/'force_mechanism_waypoint_v3';O=S/'adaptive_continuous_coordination_optimization_v1'
L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def put(n,x):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
assert (P/'derived/MECHANISM_WINDOWS.json').exists(),'Archive analysis must precede physics design'
assert not (P/'CANDIDATE_PLAN.json').exists(),'Do not overwrite registered design'
for d in ['source','code','deps','weights','tests']:
 if not (P/d).exists():shutil.copytree(O/d,P/d,ignore=shutil.ignore_patterns('results','__pycache__','*.pyc'))
changed=[]
for d in ['source','code','deps','tests']:
 for f in (P/d).rglob('*'):
  if f.is_file() and f.suffix in ['.py','.json','.xml','.yaml','.yml','.toml']:
   try:s=f.read_text()
   except UnicodeError:continue
   if str(O) in s:f.write_text(s.replace(str(O),str(P)));changed.append(str(f.relative_to(P)))
for n in ['MOTION_ACCEPTANCE_PROTOCOL.json','CERTIFICATION_TEST_RESULTS.json','DENSITY_MATH_TESTS.json']:shutil.copy2(O/n,P/n)
if not (P/'key_traces').exists():(P/'key_traces').symlink_to(O/'key_traces',target_is_directory=True)
shutil.copy2(O/'control/interface_base.py',P/'control/interface_base.py')
for f in (L/'control').glob('*.py'):shutil.copy2(f,P/'control'/f.name)
sys.path.insert(0,str(P/'code'))
import study_common as sc
from traction_mpc_stage5.full3d_adaptive_integration_v1.multisegment_reference import hermite
su=json.loads((O/'source/results/development_B0/summary.json').read_text());count={};designs=[]
def eval_poly(co,u,T,der=0):
 c=co.copy()
 for _ in range(der):c=c[:,1:]*np.arange(1,c.shape[1])
 return np.array([np.polynomial.polynomial.polyval(np.atleast_1d(u),row) for row in c]).T/T**der
for lr in su['learning_records']:
 d=su['decisions'][lr['decision_index']];ph=d['phase'];slot=count.get(ph,0);count[ph]=slot+1
 if (ph,slot) not in [('OUTBOUND',3),('RETURN',3)]:continue
 sch=lr['selected_plan']['schedule'];T=sch['duration_s'];coef=np.asarray(hermite(np.array(sch['start_q_rad']),np.array(sch['start_dq_rad_s']),np.zeros(2),np.array(sch['target_q_rad']),np.array(sch['target_dq_rad_s']),np.zeros(2),T))
 # Coefficients use normalized polynomial time, as in the unchanged builder.
 fractions=np.array([0,.2,.4,.8,1.]);states=[(eval_poly(coef,u,T)[0],eval_poly(coef,u,T,1)[0],eval_poly(coef,u,T,2)[0]) for u in fractions]
 def velocity(delta):
  delta=np.radians(np.asarray(delta).reshape(3,2));ss=[[v.copy() for v in q] for q in states]
  for i in range(3):ss[i+1][0]+=delta[i]
  return np.vstack([eval_poly(np.asarray(hermite(*ss[i],*ss[i+1],T*(fractions[i+1]-fractions[i]))),np.linspace(0,1,201),T*(fractions[i+1]-fractions[i]),1) for i in range(4)])
 def cost(delta):
  vv=velocity(delta);return float(np.linalg.norm(np.diff(vv,axis=0),axis=1).sum())
 opt=minimize(cost,np.zeros(6),method='SLSQP',bounds=[(-.05,.05)]*6,options={'maxiter':120,'ftol':1e-12})
 assert opt.success,opt.message
 delta=opt.x.reshape(3,2);base=cost(np.zeros(6));pos=cost(delta);neg=cost(-delta)
 print('MATH_DESIGN',ph,base,pos,neg,opt.x.tolist(),flush=True)
 assert pos<base-1e-9,'No predicted reference smoothing'
 designs.append(dict(tag='O' if ph=='OUTBOUND' else 'R',phase=ph,slot=slot,request_task_s=d['decision_request_time_s']-10.05,expected_splice_task_s=d['decision_request_time_s']-10.05+.05,duration_s=T,local_window_task_s=[d['decision_request_time_s']-10.05+.05,d['decision_request_time_s']-10.05+.05+T],fractions=fractions[1:-1].tolist(),deltas_deg=delta.tolist(),reference_velocity_TV={'B':base,'smooth':pos,'opposite':neg},optimizer=dict(method='offline SLSQP reference velocity TV only; no force objective and no physics',evaluations=opt.nfev,message=str(opt.message)),archived_schedule=sch))
rows=[dict(id='B0',family='B')]
for d in designs:
 for kind,scale in [('zero',0),('smooth',1),('opposite',-1)]:
  rows.append(dict(id=d['tag']+'_'+kind,family='P',phase=d['phase'],slot=d['slot'],local_window_task_s=d['local_window_task_s'],spec=dict(fractions=d['fractions'],deltas_deg=(np.asarray(d['deltas_deg'])*scale).tolist())))
now=time.time();plan=dict(seed=2026101303,physics_budget=12,physical_timeout_s=300,dispatch_cutoff_unix=now+7200,physics_hard_stop_unix=now+7500,hypothesis='At a registered B velocity-oscillation window, bounded internal q waypoints reducing native actual velocity TV also reduce contemporaneous 5ms force integral/mean force.',inputs='registered offline constants; original causal observation/belief only online',hidden='Human native truth is evaluation-only; archived reference/motion used for offline experiment design',evidence='exploratory same-Human development; no held-out tuning or qualification promotion',metrics='unchanged full task J_F plus exact clipped support and 4-6/15-16 windows; native TV_v/TV_a/jerk, tracking, posture, moment, torque/allocator; all failures preserved',qualification='unchanged task/safety/motion/receipt/causal current-state gates; original identity and certificate recomputed per candidate; 0.05deg path bound retained',conditional_rule='If complete qualified smooth arm has lower actual TV_v in support (>1e-6 relative) AND lower support J_F (>1e-8 N s), run only its half amplitude and one deterministic same-state repeat. Report magnitude separately; do not optimize J_F or extend search.',stop='Initial two registered windows and opposite/zero controls only; at most two conditional half-scale and repeats; no further search if target motion fails or force lacks concordant signal',protected='formal B, plant, controller gain, thresholds, bridge40ms, lifecycle100ms, goals, endpoints and duration unchanged')
put('RUN_PLAN.json',plan);put('CANDIDATE_PLAN.json',dict(frozen_unix=now,coarse=rows,designs=designs,conditional=plan['conditional_rule']))
put('audit/PATH_ONLY_REBASE.json',dict(files=changed,semantics='path string relocation only; no builder/controller/certificate semantic changes'))
manifest={str(f.relative_to(P)):sha(f) for d in ['source','code','deps','weights','control','tests'] for f in (P/d).rglob('*') if f.is_file() and '__pycache__' not in f.parts}
put('EXECUTION_CODE_MANIFEST.json',dict(files=manifest,plan_sha256=sha(P/'CANDIDATE_PLAN.json'),motion_protocol_sha256=sha(P/'MOTION_ACCEPTANCE_PROTOCOL.json'),frozen_unix=time.time()))
print(json.dumps(dict(designs=[{k:v for k,v in d.items() if k!='archived_schedule'} for d in designs],rows=len(rows),source_files=len(manifest)),indent=2))
