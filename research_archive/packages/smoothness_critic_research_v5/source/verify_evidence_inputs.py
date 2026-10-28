from pathlib import Path
import json,hashlib,time
P=Path(__file__).resolve().parents[1];O=Path('/home/hank/ihear-lab/smoothness_critic_research_v5');t0=time.time();manifest=json.loads((O/'OUTPUT_MANIFEST.json').read_text());bad=[];n=0;size=0
for rel,row in manifest['files'].items():
 f=O/rel
 if not f.exists():bad.append({'path':rel,'reason':'MISSING'});continue
 h=hashlib.sha256()
 with f.open('rb') as z:
  for b in iter(lambda:z.read(4*1024*1024),b''):h.update(b)
 n+=1;size+=f.stat().st_size
 if h.hexdigest()!=row['sha256'] or f.stat().st_size!=row['size']:bad.append({'path':rel,'reason':'SHA_OR_SIZE'})
out={'status':'PASS' if not bad else 'FAIL','files':n,'bytes':size,'mismatches':bad,'wall_s':time.time()-t0,'manifest_sha256':hashlib.sha256((O/'OUTPUT_MANIFEST.json').read_bytes()).hexdigest()};(P/'audit/PRIOR_MANIFEST_REVERIFIED.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
