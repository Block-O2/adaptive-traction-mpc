import os,sys,json
from pathlib import Path
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');sys.dont_write_bytecode=True
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_early_return_motion_repair_v1')
OLD=S.parent/'m2_coordination_space_exploration_v1'
sys.path.insert(0,str(OLD/'code'))
from stream_runtime_evidence import array_items
import numpy as np
p=OLD/'source/results/005_return_history_scale_0.1'
s=json.loads((p/'summary.json').read_text())
print('summary',list(s));print('commissioning',list(s['commissioning']));print('commissioning fit',json.dumps({k:v for k,v in s['commissioning'].items() if 'history' not in k})[:7000]);print('decisions',json.dumps(s['decisions'][0])[:2500]);print('learning',json.dumps(s['learning_records'][0])[:2500])
with np.load(p/'trace.npz') as z:print('trace',[(k,z[k].shape,str(z[k].dtype)) for k in z.files]);print('first truth',z['evaluation_only_human_state_rad_rad_s'][0])
for key in ['native_states_evaluation_only','command_receipts']:
 row=next(array_items(p/'runtime_artifacts.json.gz',key));print(key,json.dumps(row)[:5000])
