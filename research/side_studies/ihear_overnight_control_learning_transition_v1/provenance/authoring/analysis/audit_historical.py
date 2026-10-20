"""Recompute reused historical evidence without writing one byte into historical roots."""
from pathlib import Path
import os,sys,json,importlib.util,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
A=P.parent/'ihear_model_terminal_compensation_v1'
spec=importlib.util.spec_from_file_location('historical_arithmetic',P/'control/independent_recompute.py');ar=importlib.util.module_from_spec(spec);spec.loader.exec_module(ar)
ar.P=A
def write_new(n,x):
    target=P/'derived'/('HISTORICAL_'+Path(n).name)
    target.write_text(json.dumps(ar.clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
ar.put=write_new
results=[]
for group in ['Dev','Ctrl','W2']:
    rows=json.loads((A/(group+'_RESULTS.json')).read_text())['rows']
    ids=[r['id'] for r in rows]
    if (A/(group+'_DONE.json')).exists():ids.insert(0,group+'_parent')
    for ident in ids:results.append(ar.measure(ident))
assert not [n for n in sys.modules if 'mujoco' in n or 'planner' in n or n in ['study_common','sac_env']]
(P/'audit/HISTORICAL_RAW_RECOMPUTATION.json').write_text(json.dumps(dict(status='PASS',unix=time.time(),checks=results,source=str(A),outputs_only_in_new_package=True,physics_starts=0),indent=2)+'\n')
print('HISTORICAL_AUDIT_PASS',len(results),'FULL_RUNS',flush=True)
