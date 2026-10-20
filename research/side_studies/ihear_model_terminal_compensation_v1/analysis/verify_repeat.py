"""Read-only deterministic repeat gate; no simulation/controller imports."""
from pathlib import Path
import os,sys,json,ast,itertools,importlib.util,time,hashlib,shutil
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');sys.dont_write_bytecode=True
import numpy as np
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
spec=importlib.util.spec_from_file_location('arithmetic_only',P/'control/independent_recompute.py');checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
array_items=checker.array_items
src=(P/'control/base_campaign.py').read_text();tree=ast.parse(src)
exec(ast.get_source_segment(src,next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='compare_raw')))
results=[]
for arm in ['B','T','ER','H150']:
 a=P/'source/results'/('Dev_'+arm);b=P/'source/results'/('Ctrl_'+arm)
 assert (b/'summary.json').exists()
 result=compare_raw(a,b);results.append(dict(arm=arm,**result));assert result['status']=='PASS'
 print('REPEAT_PASS',arm,flush=True)
selection=json.loads((P/'NEW_FROZEN_SELECTION.json').read_text());plans=[json.loads((P/(g+'_PLAN.json')).read_text()) for g in ['Dev','Ctrl']]
candidates=[next(x for x in p['arms'] if x['id']=='H150') for p in plans]
assert candidates[0]==candidates[1]
out=dict(status='PASS',unix=time.time(),selection_frozen_before_repeat=True,selection_sha256=hashlib.sha256((P/'NEW_FROZEN_SELECTION.json').read_bytes()).hexdigest(),candidate_identity_exact=True,primary='H150',checks=results,meaning='Deterministic repeat from a fresh legal cold parent; not robustness or unseen-state evidence',wall_clock_profiling_excluded=True)
(P/'REPEAT_VERIFICATION.json').write_text(json.dumps(out,indent=2)+'\n');shutil.copy2(P/'REPEAT_VERIFICATION.json',R/'REPEAT_VERIFICATION.json')
