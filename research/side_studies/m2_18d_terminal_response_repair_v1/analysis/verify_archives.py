"""Independent arithmetic/receipt reconstruction, output exclusively new study."""
from pathlib import Path
import types,json,sys,time
P=Path(__file__).resolve().parents[1];S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies');A=S/'m2_18d_autonomous_review_v1';Q=S/'m2_18d_baseline_qualification_v1'
module=types.ModuleType('archived_arithmetic');module.__file__=str(A/'control/independent_recompute.py')
exec(compile((A/'control/independent_recompute.py').read_text(),module.__file__,'exec'),module.__dict__)
def put(n,x):
 path=P/'derived'/('ARCHIVE_'+str(module.P.name)+'__'+Path(n).name);path.write_text(json.dumps(module.clean(x),indent=2,ensure_ascii=False)+'\n')
module.put=put
rows=[]
for root,ids in [(A,['N2_B','N2_E','N2_C','N2_R']),(Q,['N1_B','N1_E'])]:
 module.P=root
 for ident in ids:rows.append(dict(root=str(root),result=module.measure(ident)))
assert not any(n in sys.modules for n in ['mujoco','study_common','sac_env','runner'])
(P/'audit/ARCHIVED_RAW_INDEPENDENT.json').write_text(json.dumps(dict(status='PASS',unix=time.time(),rows=rows,new_physics=0,controller_imports=False,method='existing independent arithmetic source loaded without main; only read root and output sink rebound'),indent=2)+'\n')
