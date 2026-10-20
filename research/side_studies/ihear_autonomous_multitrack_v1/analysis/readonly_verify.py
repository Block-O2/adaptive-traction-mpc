"""Read-only sealed package verifier. Never imports controller or starts physics."""
from pathlib import Path
import json,hashlib,sys
P=Path(__file__).resolve().parents[1]
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as src:
  for b in iter(lambda:src.read(2**20),b''):h.update(b)
 return h.hexdigest()
manifest=json.loads((P/'EVIDENCE_MANIFEST.json').read_text());errors=[]
for rel,row in manifest['files'].items():
 p=P/rel
 if not p.is_file() or p.stat().st_size!=row['size'] or sha(p)!=row['sha256']:errors.append(rel)
print(json.dumps(dict(status='PASS' if not errors else 'FAIL',files=len(manifest['files']),errors=errors,new_physics_START=0),indent=2))
sys.exit(bool(errors))
