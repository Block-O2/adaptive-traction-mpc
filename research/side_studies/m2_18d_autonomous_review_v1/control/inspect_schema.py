from pathlib import Path
import json,numpy as np
Q=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_baseline_qualification_v1')
folder=Q/'source/results/N2_E'
with np.load(folder/'trace.npz') as z:print('TRACE',[(k,z[k].shape) for k in z.files if any(s in k for s in ['state','torque','wrench','reference','action'])])
s=json.loads((folder/'summary.json').read_text());r=s['learning_records'][3]
print('RECORD_KEYS',list(r));print('RECORD',json.dumps({k:v for k,v in r.items() if k not in ['selected_plan','evaluations','state_features']})[:4000]);print('PLAN_KEYS',list(r.get('selected_plan',{})));print('PLAN',json.dumps(r.get('selected_plan',{}))[:5000]);print('DECISION',json.dumps(s['decisions'][3])[:2500])
