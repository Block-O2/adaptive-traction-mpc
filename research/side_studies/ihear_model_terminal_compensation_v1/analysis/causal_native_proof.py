from pathlib import Path
import os,sys,json,itertools
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name;sys.path[:0]=[str(P/'code')]
from stream_runtime_evidence import array_items
import numpy as np
group=sys.argv[1] if len(sys.argv)>1 else 'Dev'
a=P/'source/results'/(group+'_ER');b=P/'source/results'/(group+'_H150');z=np.load(a/'trace.npz');origin=z['time_s'][z['stage']=='TASK'][0]
gate=json.loads((P/'audit'/(group+'_H150_HIP_ONLY_CAUSAL_PROOF.json')).read_text());changed=gate['first_reference_difference_physics_s'];diff={};prior=[];count=0
keys=['qpos_evaluation_only','qvel_evaluation_only','command_torque_nm','contact_pairs_evaluation_only','command_id','native_step_index']
for i,(x,y) in enumerate(itertools.zip_longest(array_items(a/'runtime_artifacts.json.gz','native_states_evaluation_only'),array_items(b/'runtime_artifacts.json.gz','native_states_evaluation_only'))):
 assert x is not None and y is not None;assert abs(x['time_s']-y['time_s'])<1e-9;count+=1
 for k in keys:
  if x.get(k)!=y.get(k):
   diff.setdefault(k,dict(time_s=x['time_s'],task_s=x['time_s']-origin,index=i))
   if x['time_s']<=changed+1e-9:prior.append((i,k))
assert not prior
out=dict(status='PASS',pair=[str(a),str(b)],same_unchanged_knee_reference=gate['knee_reference_difference_max_rad']<1e-10,first_changed_reference_task_s=changed-origin,all_native_body_state_torque_contact_ownership_before_changed_command_exact=True,native_rows=count,first_differences=diff,mechanism='Changing only certified hip reference terminal timing caused a different knee physical response. This does not isolate anatomical inertia from robot/controller/cuff mediation.')
(P/'audit'/(group+'_FULL_NATIVE_CAUSAL_PROOF.json')).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
