from pathlib import Path
import json,hashlib,shutil,time
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
assert json.loads((P/'PACKAGE_VERIFICATION.json').read_text())['status']=='PASS'
files=[]
for f in P.iterdir():
 if f.is_file() and f.suffix in ['.md','.json','.jsonl']:files.append(f)
for folder in ['control','analysis','figures','provenance','audit','derived','reports']:
 for f in (P/folder).rglob('*'):
  if not f.is_file() or '__pycache__' in f.parts:continue
  if f.name in ['HISTORY_BEFORE.json','GIT_BEFORE.json']:continue
  files.append(f)
for f in (P/'logs').glob('*.log'):files.append(f)
manifest={}
for f in files:
 rel=f.relative_to(P);dest=R/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest);a=hashlib.sha256(f.read_bytes()).hexdigest();b=hashlib.sha256(dest.read_bytes()).hexdigest();assert a==b
 manifest[str(rel)]=dict(sha256=a,size=dest.stat().st_size)
(R/'REVIEW_MIRROR_VERIFICATION.json').write_text(json.dumps(dict(status='PASS',unix=time.time(),canonical=str(P),review=str(R),copied_files=manifest,raw_native_retained_in_canonical=True,excludes=['source/results','motion_series','source/code/deps/weights closure','audit/HISTORY_BEFORE.json','audit/GIT_BEFORE.json'],scientific_scope='Review mirror, not a complete raw-data backup'),indent=2)+'\n')
print(json.dumps(dict(status='PASS',files=len(files),review=str(R))),flush=True)
