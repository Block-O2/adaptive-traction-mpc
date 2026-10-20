"""Compare original B/H150 every trace field, native state and scientific receipt."""
from pathlib import Path
import sys,os,json,ast,itertools,time,importlib.util
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
A=P.parent/'ihear_model_terminal_compensation_v1'
spec=importlib.util.spec_from_file_location('raw_arithmetic',P/'control/independent_recompute.py');ar=importlib.util.module_from_spec(spec);spec.loader.exec_module(ar)
source=(P/'control/base_campaign.py').read_text();tree=ast.parse(source)
namespace=dict(np=np,itertools=itertools,array_items=ar.array_items)
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='compare_raw')
exec(ast.get_source_segment(source,node),namespace)
out=[]
for arm in ['B','H150']:
    check=namespace['compare_raw'](P/'source/results'/('D01R_'+arm),A/'source/results'/('Ctrl_'+arm))
    assert check['status']=='PASS',check
    out.append(check)
features=[]
for arm in ['H150','HIP','KNEE','ZERO']:
    features.append(json.loads((P/'output'/('D01R_'+arm+'_CAUSAL_STATE.json')).read_text())['features'])
assert all(np.array_equal(features[0],x) for x in features[1:])
ar.put('audit/H150_REPRODUCTION.json',dict(status='PASS',unix=time.time(),raw_comparisons=out,live_learning_states_equal_before_intervention=True,physics_imports=False))
print('RAW_REPRODUCTION_PASS; CAUSAL_CONTEXT_MATCH_PASS',flush=True)
