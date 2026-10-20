"""Separate raw arithmetic and command ownership implementation, no plant imports."""
from pathlib import Path
import os,sys,json,importlib.util,time,shutil
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
spec=importlib.util.spec_from_file_location('arithmetic_only',P/'control/independent_recompute.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
groups=sys.argv[1:] or ['Dev','Ctrl','W2'];results=[]
for group in groups:
 ids=[r['id'] for r in c.read(group+'_RESULTS.json')['rows']]
 if (P/(group+'_DONE.json')).exists():ids.insert(0,group+'_parent')
 for ident in ids:results.append(c.measure(ident))
forbidden=[n for n in sys.modules if 'mujoco' in n or 'planner' in n or n in ['study_common','campaign','sac_env','runner']];assert not forbidden
out=dict(status='PASS',unix=time.time(),groups=groups,checks=results,imports_physics_or_controller=False,method='Independent arithmetic implementation in a separate read-only process; same research agent, not an independent human or second agent',new_physical_starts=0)
c.put('audit/INDEPENDENT_'+('_'.join(groups))+'.json',out)
print(json.dumps(dict(status='PASS',groups=groups,complete_runs_recomputed=len(results))),flush=True)
