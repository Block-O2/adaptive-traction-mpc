from pathlib import Path
import shutil,json,hashlib,time
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1');L=Path(__file__).resolve().parents[1]
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
m=json.loads((P/'EXECUTION_CODE_MANIFEST.json').read_text())['files']
for name,h in m.items():assert sha(P/name)==h,name
names=['research_sequence.py','diagnostic.py','inspect_progress.py','inspect_schema.py','install_analysis.py']
for n in names:
 assert 'control/'+n not in m
 shutil.copy2(L/'control'/n,P/'control'/n)
(P/'ORCHESTRATION_AND_ANALYSIS_MANIFEST.json').write_text(json.dumps(dict(frozen_unix=time.time(),before_N2_START=not (P/'N2_OWNER_ACTIVE.json').exists(),execution_manifest_unchanged=True,files={'control/'+n:sha(P/'control'/n) for n in names}),indent=2)+'\n')
print('SUPPLEMENTAL_MANIFEST_FROZEN')
