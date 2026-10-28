from pathlib import Path
import json,hashlib,time,sys
P=Path(__file__).resolve().parents[1];start=time.time();out=[]
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as z:
  for b in iter(lambda:z.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
for name in ['representation_execution_v3','autonomous_coordination_learning_v2','learning_guided_motion_improvement_v1']:
 root=P.parent/name;man=root/'OUTPUT_MANIFEST.json';obj=json.loads(man.read_text());bad=[];size=0;n=0
 for rel,row in obj['files'].items():
  f=Path(rel) if Path(rel).is_absolute() else root/rel;expected=row if isinstance(row,str) else row['sha256']
  if not f.is_file():bad.append(dict(path=rel,reason='MISSING'));continue
  size+=f.stat().st_size;n+=1
  if sha(f)!=expected:bad.append(dict(path=rel,reason='SHA256'))
 out.append(dict(root=str(root),manifest_sha256=sha(man),files=n,bytes=size,mismatches=bad,status='PASS' if not bad else 'FAIL'))
result=dict(status='PASS' if all(r['status']=='PASS' for r in out) else 'FAIL',rows=out,wall_s=time.time()-start)
f=P/'audit/PROTECTED_MANIFEST_REVERIFICATION.json';f.write_text(json.dumps(result,indent=2)+'\n');print(result)
