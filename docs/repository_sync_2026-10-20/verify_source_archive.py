"""Read-only verification of exactly the preserved source payload; no imports of research."""
import csv,hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[2]
manifest=Path(__file__).resolve().parent/'manifests/source_origin_manifest.csv'
errors=[];count=0
with manifest.open(newline='') as f:
 for r in csv.DictReader(f):
  p=root/r['git_path'];h=hashlib.sha256()
  if not p.is_file():errors.append({'path':r['git_path'],'error':'MISSING'});continue
  with p.open('rb') as stream:
   for b in iter(lambda:stream.read(1048576),b''):h.update(b)
  if p.stat().st_size!=int(r['bytes']) or h.hexdigest()!=r['sha256']:errors.append({'path':r['git_path'],'error':'SIZE_OR_SHA'})
  count+=1
print(json.dumps({'pass':not errors,'files':count,'errors':errors,'physics':'NOT_RUN','training':'NOT_RUN'}))
raise SystemExit(bool(errors))
