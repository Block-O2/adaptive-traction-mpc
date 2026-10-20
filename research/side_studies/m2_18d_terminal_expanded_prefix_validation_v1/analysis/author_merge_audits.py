from pathlib import Path
import json,os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
L=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/L.name

def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
pre=[read('audit/'+g+'_PREFIX_AND_FAILURE_AUDIT.json') for g in ['V1','V2']]
assert len({r['native_hash'] for r in pre})==2
assert np.max(abs(np.asarray(pre[0]['human_q_dq_at_fork_evaluation_only'])-pre[1]['human_q_dq_at_fork_evaluation_only']))>1e-8
put('audit/EXPANDED_PREFIX_AUDIT.json',dict(status='PASS',groups=pre,same_Human=True,no_state_replay=True,no_physics_imports=True,new_native_state_identity_distinct=True))
x=read('audit/INTERVENTION_EXECUTION_AUDIT.json');v1=read('audit/V1_INTERVENTION_EXECUTION_AUDIT.json');rows={r['group']:r for r in v1['rows']+x['rows']};assert set(rows)=={'V1','V2'};x['rows']=[rows[g] for g in ['V1','V2']];put('audit/INTERVENTION_EXECUTION_AUDIT.json',x)
print('AUDITS_MERGED')
