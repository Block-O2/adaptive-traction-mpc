from pathlib import Path
import json,hashlib,shutil,time
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
R=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name
assert json.loads((P/'PACKAGE_VERIFICATION.json').read_text())['status']=='PASS'
omit={'source','code','deps','weights','motion_series','tmp'};large={'audit/HISTORY_BEFORE.json','audit/GIT_BEFORE.json'};files={}
for f in sorted(P.rglob('*')):
 if not f.is_file():continue
 rel=f.relative_to(P)
 if rel.parts[0] in omit or str(rel) in large or '__pycache__' in rel.parts:continue
 dest=R/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
 h=hashlib.sha256(f.read_bytes()).hexdigest();assert hashlib.sha256(dest.read_bytes()).hexdigest()==h;files[str(rel)]=h
record=dict(status='PASS',unix=time.time(),canonical=str(P),review=str(R),files=files,not_raw_archive=True,raw_location=str(P/'source/results'),canonical_package_verification_sha256=hashlib.sha256((P/'PACKAGE_VERIFICATION.json').read_bytes()).hexdigest())
(R/'REVIEW_MIRROR_VERIFICATION.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(dict(status='PASS',review_files=len(files),canonical=str(P),review=str(R))),flush=True)
