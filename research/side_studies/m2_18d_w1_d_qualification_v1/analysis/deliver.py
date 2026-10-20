from pathlib import Path
import json,hashlib,shutil,time,os
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
R=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as s:
  for x in iter(lambda:s.read(2**20),b''):h.update(x)
 return h.hexdigest()
def put(f,x):f.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
assert json.loads((P/'PACKAGE_VERIFICATION.json').read_text())['status']=='PASS'
needed=['REPORT.md','W1_FAILURE_DIAGNOSIS.md','FROZEN_EXPERIMENT_PROTOCOL.md','EXPERIMENT_RESULTS.json','ATTEMPT_ACCOUNTING.json','VALIDATION_RESULTS.json','PACKAGE_VERIFICATION.json','NEXT_RESEARCH_DECISION.md','figures/W1_failure_timeline.png']
assert all((P/n).is_file() for n in needed)
exclude={'EVIDENCE_MANIFEST.json','REVIEW_MIRROR_MANIFEST.json','DELIVERY_VERIFICATION.json'}
files={}
for f in sorted(P.rglob('*')):
 if not f.is_file() or '__pycache__' in f.parts or f.relative_to(P).parts[0]=='tmp' or f.name in exclude:continue
 files[str(f.relative_to(P))]=dict(size=f.stat().st_size,sha256=sha(f))
put(P/'EVIDENCE_MANIFEST.json',dict(status='PASS',created_unix=time.time(),files=files,scope='canonical full evidence including compressed native/receipt raw and frozen execution closure; self and derived delivery manifests excluded'))
mirror={}
for f in sorted(P.rglob('*')):
 if not f.is_file():continue
 rel=f.relative_to(P);top=rel.parts[0]
 if top in ['source','deps','code','weights','motion_series','tmp'] or '__pycache__' in f.parts or f.name in ['HISTORY_BEFORE.json','GIT_BEFORE.json','REVIEW_MIRROR_MANIFEST.json','DELIVERY_VERIFICATION.json']:continue
 dest=R/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest);h=sha(f);assert sha(dest)==h;mirror[str(rel)]=dict(size=f.stat().st_size,sha256=h)
put(P/'REVIEW_MIRROR_MANIFEST.json',dict(status='PASS',files=mirror,canonical=str(P),review=str(R),raw_location=str(P/'source/results'),review_not_complete_execution_closure=True,excluded='source/code/deps/weights/motion_series/tmp and large protected-history/Git-before maps; complete canonical originals retained',local_authoring_and_preview_extras=[str(f.relative_to(R)) for f in R.rglob('*') if f.is_file() and str(f.relative_to(R)) not in mirror and f.name not in ['REVIEW_MIRROR_MANIFEST.json','DELIVERY_VERIFICATION.json']]))
shutil.copy2(P/'REVIEW_MIRROR_MANIFEST.json',R/'REVIEW_MIRROR_MANIFEST.json')
for rel,r in mirror.items():assert sha(R/rel)==r['sha256']
out=dict(status='PASS',unix=time.time(),required_deliverables=needed,required_all_present=True,canonical_manifest_sha256=sha(P/'EVIDENCE_MANIFEST.json'),mirror_manifest_sha256=sha(P/'REVIEW_MIRROR_MANIFEST.json'),review_files_verified=len(mirror),canonical_raw_retained=True,physical_START=json.loads((P/'ATTEMPT_ACCOUNTING.json').read_text())['physical_START'],physical_END=json.loads((P/'ATTEMPT_ACCOUNTING.json').read_text())['physical_END'],STOP=True)
put(P/'DELIVERY_VERIFICATION.json',out);put(R/'DELIVERY_VERIFICATION.json',out)
print(json.dumps(out),flush=True)
