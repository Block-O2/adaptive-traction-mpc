from pathlib import Path
import os,sys,json,time,hashlib,ast,importlib
P=Path(__file__).resolve().parents[1]
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TMPDIR=str(P/'tmp'),MPLCONFIGDIR=str(P/'tmp/mpl'))
sys.dont_write_bytecode=True;sys.path.insert(0,str(P/'code'))
import study_common as sc, matched_harness as mh, analyze_matched as am
from rich_planner import RichFreePlanner
import numpy as np
errors=[];imports=[]
for name,module in list(sys.modules.items()):
 f=getattr(module,'__file__',None)
 if f and '/home/hank/coding/' in f:
  imports.append(dict(module=name,path=f))
  if not Path(f).resolve().is_relative_to(P):errors.append(dict(external_import=f))
assert not errors,errors
assert sc.STUDY==P and mh.PACKAGE==P and am.S==P
instance=mh.MatchedInterface(dict(name='preflight',seed=2026101303,prefix={}))
assert instance.count=={'OUTBOUND':0,'RETURN':0}
frozen=json.loads((P/'FROZEN_18D.json').read_text());hist=json.loads((P.parent/'ihear_overnight_research_retrospective_v1/FROZEN_SELECTION.json').read_text())['best']['candidate']
assert frozen==hist and len(frozen['free_parameters'])==18
assert np.allclose(np.asarray(frozen['normalized_parameters'])*np.array([.015,.025,.025,.2,.2,.015,.025,.025,.2,.2,.015,.015,.025,.2,.015,.015,.025,.2]),frozen['free_parameters'],rtol=0,atol=1e-16)
assert sc.sha(P/'MOTION_ACCEPTANCE_PROTOCOL.json')==sc.sha(P.parent/'ihear_overnight_research_retrospective_v1/MOTION_ACCEPTANCE_PROTOCOL.json')
for d in ['source','code','deps','control']:
 for f in (P/d).rglob('*.py'):ast.parse(f.read_text(),filename=str(f))
# Meaningful no-physics numeric identity: all zeros leave original, normalized axes recover c/d signs.
x=np.asarray(frozen['free_parameters']);rows=[]
for m in [0,.1,.3,.5,.8,1.]:
 for j,k in [(0,10),(5,14)]:
  e=np.sin(np.pi*m)**2;u=2*m-1;c=e*(x[j]+x[k]*u+x[k+1]*u*u);d=e*(x[j+1]+x[j+2]*u+x[k+2]*u*u)
  shift=np.array([c+d,c-d]);assert abs(shift.mean()-c)<1e-15 and abs((shift[0]-shift[1])/2-d)<1e-15
  rows.append(dict(m=m,phase='OUTBOUND' if j==0 else 'RETURN',common=c,differential=d,normalized_shift=shift.tolist()))
for a in ['reproduction_B','reproduction_E']:
 old='development_repair2_B0_original' if a.endswith('B') else 'development_repair2_quality_NATIVE_SCALAR_18_063'
 for n in ['trace.npz','summary.json','runtime_artifacts.json.gz']:assert (P.parent/'ihear_overnight_research_retrospective_v1/source/results'/old/n).is_file()
manifest={str(f.relative_to(P)):sc.sha(f) for d in ['source','code','deps','weights','control'] for f in (P/d).rglob('*') if f.is_file() and '__pycache__' not in f.parts and 'results' not in f.parts}
manifest.update({n:sc.sha(P/n) for n in ['RUN_PLAN.json','FROZEN_18D.json','MOTION_ACCEPTANCE_PROTOCOL.json','METHOD_DEFINITION.md','PARAMETER_MAP.json','SOURCE_AND_RESULT_LINEAGE.md']})
manifest['output/SHARED_COORDINATION_ACTION_CONTRACT.json']=sc.sha(P/'output/SHARED_COORDINATION_ACTION_CONTRACT.json')
mh.put(P/'EXECUTION_CODE_MANIFEST.json',dict(files=manifest,frozen_unix=time.time(),imports=imports))
mh.put(P/'PREPHYSICAL_CHECKS.json',dict(status='PASS',unix=time.time(),imports_within_closure=True,parameter_identity=True,motion_protocol_byte_identity=True,math_rows=rows,source_audit_before_physics=True,no_physics_started=not (P/'ATTEMPTS.jsonl').exists(),no_direct_state_write_in_campaign=True))
print(json.dumps(dict(status='PASS',files=len(manifest),imports=len(imports))))
