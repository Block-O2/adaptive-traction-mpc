"""Separate completeness and evidence-hash verification after report closeout."""
from pathlib import Path
import json,hashlib,time,shutil,ast
P=Path(__file__).resolve().parents[1];L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as s:
  for block in iter(lambda:s.read(2**20),b''):h.update(block)
 return h.hexdigest()
def read(n):return json.loads((P/n).read_text())
rows=[json.loads(l) for l in (P/'EXPLORATION_RESULTS.jsonl').read_text().splitlines()];analyzed=read('ALL_ANALYZED_RESULTS.json')['rows'];assert [r['id'] for r in rows]==[r['id'] for r in analyzed]
ac=read('ATTEMPT_ACCOUNTING.json');assert ac['physical_START']==ac['physical_END'] and not ac['active_owned'] and ac['native_steps_exact']
assert read('STATE.json')['status']=='STOP';assert read('FROZEN_SELECTION.json')['PRIMARY'] is None;assert read('VALIDATION_RESULTS.json')['new_pairs']==0
checks=[]
for r in rows:
 if r['status']!='COMPLETE':continue
 ident=r['id'];m=read('reports/'+ident+'_MEASURED.json');a=read('audit/'+ident+'_REFERENCE_RECEIPT_AUDIT.json')
 assert a['status']=='PASS'
 for f,h in m['sources'].items():assert sha(Path(f))==h,'RAW_HASH_CHANGED:'+f
 checks.append(dict(id=ident,raw_hashes=True,receipt_and_certificate_audit=True,task=m['axes']['PHYSICAL_TASK_VALID'],motion=r['motion_pass']))
for p in (P/'control').glob('*.py'):ast.parse(p.read_text(),filename=str(p))
required=['REPORT.md','HISTORICAL_18D_MECHANISM.md','FORCE_MOTION_DIAGNOSTIC.md','INTERVENTION_PROTOCOL.md','EXPLORATION_RESULTS.jsonl','ATTEMPT_ACCOUNTING.json','FROZEN_SELECTION.json','VALIDATION_RESULTS.json','CODE_MANIFEST.json','PACKAGE_VERIFICATION.json','NEXT_RESEARCH_DECISION.md','BASELINE_REPRODUCTION.json','figures/18d_mechanism_timeline.png']
assert all((P/n).is_file() for n in required)
repeat=read('REPEAT_GATES.json');assert repeat['status']=='PASS' and len(repeat['rows'])==4
files={}
for f in P.rglob('*'):
 if f.is_file() and not f.is_symlink() and 'tmp' not in f.relative_to(P).parts and f.name not in ['EVIDENCE_MANIFEST.json','FINAL_INDEPENDENT_AUDIT.json','REVIEW_MIRROR_MANIFEST.json']:
  files[str(f.relative_to(P))]=dict(bytes=f.stat().st_size,sha256=sha(f))
out=dict(status='PASS',unix=time.time(),scope='independent arithmetic/identity/hash script checks, not an independent person or independent agent',candidate_rows=len(rows),complete_rows=len(checks),all_raw_hashes_verified=True,required_files_present=True,repeat_gates=repeat,physics_starts=ac['physical_START'],new_physics_in_audit=0,rows=checks)
(P/'FINAL_INDEPENDENT_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n');(P/'EVIDENCE_MANIFEST.json').write_text(json.dumps(dict(files=files,excluded='self-reference, tmp, and symlinked historical fixtures; historical archive inputs separately SHA bound'),indent=2)+'\n')
for n in ['FINAL_INDEPENDENT_AUDIT.json','EVIDENCE_MANIFEST.json']:shutil.copy2(P/n,L/n)
mirror=dict(canonical=str(P),mirror=str(L),full_raw_mirrored=False,files={str(f.relative_to(L)):sha(f) for f in L.rglob('*') if f.is_file() and f.name!='REVIEW_MIRROR_MANIFEST.json'})
(P/'REVIEW_MIRROR_MANIFEST.json').write_text(json.dumps(mirror,indent=2)+'\n');shutil.copy2(P/'REVIEW_MIRROR_MANIFEST.json',L/'REVIEW_MIRROR_MANIFEST.json')
print('FINAL_INDEPENDENT_AUDIT_PASS',len(rows),len(checks),len(files))
