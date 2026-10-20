import json,collections,sys
from pathlib import Path
import numpy as np
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_native_learning_matrix_v1')
rs=[json.loads(p.read_text()) for p in (R/'output').glob('*_DATA.json')]
rs=[r for r in rs if r['metric']['valid'] and r['metric']['status']=='COMPLETE']
def k(r):
 x=np.asarray(r['branch_start']['G_input'],np.float32)
 return np.round(x[np.r_[0:58,88:120]],4).tobytes()
by=collections.defaultdict(list)
for r in rs:by[k(r)].append(r)
for a in by.values():
 print('POOL',sorted(set(r['group'] for r in a)),sorted(set(r['child']['snapshot_hash'][:10] for r in a)),len(a),a[0]['branch_start']['context']['phase'],a[0]['branch_start']['context']['task_s'])
for r in rs:
 if r['group']=='v1_committed_attribution':
  print('DIAG',r['id'],r['remaining_J_F'],r['branch_start']['source'],r['child']['snapshot_hash'][:10],r['metric'].keys());break
print('first source dir',list((R/'source/results'/rs[0]['id']).glob('*')))
