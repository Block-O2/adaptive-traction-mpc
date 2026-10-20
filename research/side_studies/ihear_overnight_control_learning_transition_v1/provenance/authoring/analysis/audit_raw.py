"""Recompute native metrics and receipts in a process without controller imports."""
from pathlib import Path
import sys,os,json,importlib.util,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
spec=importlib.util.spec_from_file_location('raw_arithmetic',P/'control/independent_recompute.py')
ar=importlib.util.module_from_spec(spec);spec.loader.exec_module(ar)
results=[]
for group in sys.argv[1:]:
    if group.startswith('@'):
        results.append(ar.measure(group[1:]));continue
    r=json.loads((P/(group+'_RESULTS.json')).read_text())
    ids=[row['id'] for row in r['rows']]
    if (P/(group+'_DONE.json')).exists():ids.insert(0,group+'_parent')
    for ident in ids:results.append(ar.measure(ident))
assert not [n for n in sys.modules if 'mujoco' in n or 'planner' in n or n in ['study_common','sac_env']]
ar.put('audit/RAW_'+('_'.join(sys.argv[1:]))+'.json',dict(status='PASS',unix=time.time(),groups=sys.argv[1:],checks=results,physics_imports=False,scope='separate raw arithmetic implementation and process; same agent, not independent personnel'))
print('AUDIT_PASS',len(results),'FULL_TASKS',flush=True)
