from pathlib import Path
import sys,pickle,time,json
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
import study_common as sc
row=pickle.loads((S/'inputs/012_N3_R2_science_nominal_FULL_CONTROLLER_CAUSAL.pkl').read_bytes())[0]
runtime,kw,public=pickle.loads(row['inputs'])
for name,value in runtime.items():
 if name in ('model','allocator','observer'):print(name,type(value),list(vars(value)),len(pickle.dumps(value,protocol=5)))
from traction_mpc_stage5.architecture_recovery_v2 import functional_benchmark as f
from traction_mpc_stage4 import estimator_v2 as e
import inspect
for obj in (f._state_residual_features,type(runtime['model']),type(runtime['model'].geometry)):
 print(inspect.getsource(obj))
print((S/'output/019_N4_V2_C2_science_deviation_TASK_FAST_WORKER_PROFILE.txt').read_text())
