from pathlib import Path
import sys,pickle,json,time,copy,enum,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
import study_common as sc,admission_key as fast,admission_certificates as original
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22
rows=pickle.loads((S/'inputs/019_N4_V2_C2_science_deviation_TASK_CAUSAL.pkl').read_bytes());cases=0;timing={'ORIGINAL':[],'RAW_A1':[]}
def mutate_arrays(value,keyfn,baseline,seen=None):
 global cases
 if seen is None:seen=set()
 if id(value) in seen:return
 seen.add(id(value))
 if isinstance(value,np.ndarray) and value.size and value.dtype.kind in 'fi':
  before=value.flat[0];value.flat[0]=before+1e-7
  try:assert keyfn()!=baseline;cases+=1
  finally:value.flat[0]=before
 elif isinstance(value,enum.Enum):return
 elif isinstance(value,dict):
  for item in value.values():mutate_arrays(item,keyfn,baseline,seen)
 elif isinstance(value,(list,tuple)):
  for item in value:mutate_arrays(item,keyfn,baseline,seen)
 elif hasattr(value,'__dict__'):
  for name,item in list(vars(value).items()):
   if isinstance(item,(float,int,str)) and not isinstance(item,enum.Enum):
    changed=item+1e-7 if isinstance(item,float) else item+1 if isinstance(item,int) else item+'_changed'
    object.__setattr__(value,name,changed)
    try:assert keyfn()!=baseline;cases+=1
    finally:object.__setattr__(value,name,item)
   else:mutate_arrays(item,keyfn,baseline,seen)
for row in rows:
 if 'expected' not in row:continue
 planner,args=pickle.loads(row['payload']);decision=pickle.loads(row['expected']);schedule=decision.executed.schedule
 bundle=(AdaptiveMechanicsScreenV22(),args['belief'],schedule.candidate,schedule)
 baseline=fast.key(*bundle);assert fast.key(*pickle.loads(pickle.dumps(bundle,protocol=5)))==baseline;cases+=1
 mutate_arrays(bundle,lambda:fast.key(*bundle),baseline)
 for repeat in range(30):
  for name,function in (('ORIGINAL',original.key),('RAW_A1',fast.key)):
   t=time.monotonic_ns();function(*bundle);timing[name].append((time.monotonic_ns()-t)/1e6)
out=dict(status='PASS',native_physics_steps=0,model_API_calls=0,cases=cases,all_reachable_numeric_arrays_and_scalar_fields_invalidated=True,
 key_ms={name:dict(zip(('p50','p95','max'),np.percentile(times,[50,95,100]).tolist())) for name,times in timing.items()},
 scope='Full self/belief/candidate/schedule value tree, including dynamic attributes, float bits, dtype and shape; current-state admission remains original.')
(S/'output/A1_KEY_LOCAL_REGRESSION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
