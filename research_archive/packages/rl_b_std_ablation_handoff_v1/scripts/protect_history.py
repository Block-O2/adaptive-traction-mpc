from pathlib import Path
import hashlib,json,time,sys
R=Path(__file__).resolve().parents[1];H=R.parent/'rl_b_autonomous_stability_reward_v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
mode=sys.argv[1];start=time.time()
if mode=='start':
 old=json.loads((H/'audit/HISTORICAL_PROTECTION_START.json').read_text())['files']
 data={x['path']:{'path':x['path'],'sha256':x['sha256'],'bytes':x['bytes']} for x in old}
 latest=json.loads((H/'OUTPUT_MANIFEST.json').read_text())['files']
 for x in latest:data[str(H/x['path'])]=dict(x,path=str(H/x['path']))
 for name in ['OUTPUT_MANIFEST.json','PACKAGE_VERIFICATION.json']:
  p=H/name;data[str(p)]=dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
 rows=list(data.values());mismatches=[]
 for x in rows:
  p=Path(x['path'])
  if not p.is_file() or p.stat().st_size!=x['bytes'] or sha(p)!=x['sha256']:mismatches.append(str(p))
 write(R/'audit/HISTORICAL_PROTECTION_START.json',dict(files=rows,files_checked=len(rows),mismatches=mismatches,pass_=not mismatches,wall_s=time.time()-start,scope='Previous 69384 protected historical scientific files plus all sealed latest-package files, excluding inherited Git metadata scope'))
else:
 rows=json.loads((R/'audit/HISTORICAL_PROTECTION_START.json').read_text())['files'];bad=[]
 for x in rows:
  p=Path(x['path'])
  if not p.is_file() or p.stat().st_size!=x['bytes'] or sha(p)!=x['sha256']:bad.append(str(p))
 write(R/'audit/HISTORICAL_PROTECTION_END.json',dict(files_checked=len(rows),mismatches=bad,pass_=not bad,wall_s=time.time()-start))
print(mode,len(rows),'mismatches',len(mismatches if mode=='start' else bad),'wall',time.time()-start,flush=True)
