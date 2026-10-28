"""Read-only SHA256 verifier for the portable source bundle."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent
def main():
 manifest=json.loads((R/'SHA256_MANIFEST.json').read_text());errors=[]
 for rel,record in manifest['files'].items():
  p=(R/rel).resolve()
  if not p.is_relative_to(R) or not p.is_file():errors.append({'path':rel,'error':'MISSING_OR_PATH'});continue
  h=hashlib.sha256()
  with p.open('rb') as f:
   for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
  if h.hexdigest()!=record['sha256'] or p.stat().st_size!=record['bytes']:errors.append({'path':rel,'error':'SHA_OR_SIZE'})
 out={'pass':not errors,'files':len(manifest['files']),'errors':errors,'scope':'portable source payload, not generated runs/venv/caches'};print(json.dumps(out))
 if errors:raise SystemExit(1)
if __name__=='__main__':main()
