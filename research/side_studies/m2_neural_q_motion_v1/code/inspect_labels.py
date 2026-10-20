exec(Path(__file__).with_name('inspect_inputs.py').read_text().split("if not (OUT/")[0]) if False else None
import os,sys,json,collections
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
import numpy as np
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_native_learning_matrix_v1')
rs=[json.loads(p.read_text()) for p in sorted((R/'output').glob('*_DATA.json'))]
print('COUNTS',collections.Counter((r['group'],r['split'],r['metric']['valid']) for r in rs))
for group in sorted(set(r['group'] for r in rs)):
 a=[r for r in rs if r['group']==group];print('GROUP',group,'pools',len(set(r['child']['snapshot_hash'] for r in a)),'rows',sum(len(r['value_rows']) for r in a),'example',a[0]['id'])
print('EXAMPLE',json.dumps(rs[0],indent=2)[:7000])
print('SNAPSHOT',json.dumps(json.loads(next((R/'output').glob('*_SNAPSHOT.json')).read_text()))[:3500])
print('SOURCES',list((R/'source/results').glob('*candidate*'))[:3])
for pkg in ['b_fast_jitter_m2_host_v1','m2_host_generalization_attribution_v1']:
 base=R.parent/pkg;j=json.loads((base/'PAIRED_RESULTS.json').read_text());print('PAIRS',pkg,[(p['B_id'],p['M2_id'],p['status']) for p in j['pairs']])
 z=np.load(base/'source/results'/j['pairs'][0]['B_id']/'trace.npz');idx=z['stage']=='TASK';t=z['time_s'][idx]
 print('TRACE_DT',np.quantile(np.diff(t),[0,.5,1]),'acc_valid',np.mean(z['actual_human_acceleration_valid'][idx]))
 print('ACC_COMPARISON',np.max(np.abs(np.gradient(z['evaluation_only_human_state_rad_rad_s'][idx,2:],t,axis=0)-z['actual_human_acceleration_rad_s2'][idx]),axis=0))
print('TORCH')
import torch
print(torch.__version__,torch.cuda.is_available())
