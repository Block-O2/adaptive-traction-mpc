from pathlib import Path
import json, sys
sys.path.insert(0,'/home/hank/coding/adaptive-traction-mpc-side-studies/m2_host_generalization_attribution_v1/code')
import numpy as np
from stream_runtime_evidence import array_items
B=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_jitter_m2_host_v1')
p=B/'source/results/008_nominal_pair1_B'
s=json.loads((p/'summary.json').read_text())
print('SUMMARY_TOP_KEYS',list(s))
for k in s:
    if any(word in k.lower() for word in ('commission','fit','model','calib','ident')):
        print('COMMISSION',k,json.dumps(s[k])[:4000])
with np.load(p/'trace.npz') as z:
    print('TRACE_KEYS',[(k,z[k].shape,str(z[k].dtype)) for k in z.files])
print('FIRST_LEARNING_RECORD',json.dumps(s['learning_records'][0])[:6500])
print('FIRST_DECISION',json.dumps(s['decisions'][0])[:4500])
for key in ('command_receipts','native_states_evaluation_only'):
    print('FIRST_RUNTIME',key,json.dumps(next(array_items(p/'runtime_artifacts.json.gz',key)))[:2500])
a=json.loads((B/'reports/008_nominal_pair1_B_AXES.json').read_text())
print('METRIC_KEYS',list(a['metric']))
print('SCORER',json.dumps(a['metric']['physical_audit']['unchanged_evaluator']['raw_scorer_v2'])[:7000])
