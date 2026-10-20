"""Second exposed condition full raw deterministic reproduction, no physics."""
from pathlib import Path
import os,sys,json,ast,itertools,time,importlib.util
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name;A=P.parent/'ihear_model_terminal_compensation_v1'
spec=importlib.util.spec_from_file_location('raw_arithmetic',P/'control/independent_recompute.py');ar=importlib.util.module_from_spec(spec);spec.loader.exec_module(ar)
source=(P/'control/base_campaign.py').read_text();tree=ast.parse(source);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='compare_raw')
namespace=dict(np=np,itertools=itertools,array_items=ar.array_items);exec(ast.get_source_segment(source,node),namespace)
checks=[]
for arm in ['B','H150']:
    check=namespace['compare_raw'](P/'source/results'/('D02_'+arm),A/'source/results'/('W2_'+arm));assert check['status']=='PASS',check;checks.append(check)
assert not any('mujoco' in n for n in sys.modules)
ar.put('audit/W2_FULL_RAW_REPRODUCTION.json',dict(status='PASS',unix=time.time(),checks=checks,physics_imports=False,condition_is_exposed_development=True))
print('W2_FULL_RAW_REPRODUCTION_PASS',flush=True)
