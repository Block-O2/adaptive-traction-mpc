from pathlib import Path
import json,hashlib,time,os,sys
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5');root=P.parent;start=time.time();cache={};rows=[];errors=[]
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as s:
  for b in iter(lambda:s.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
for name in ['constraint_geometry_learning_v4','representation_execution_v3','autonomous_coordination_learning_v2','learning_guided_motion_improvement_v1']:
 d=root/name;mf=d/'OUTPUT_MANIFEST.json';obj=json.loads(mf.read_text());files=obj['files'];bad=[]
 for rel,e in files.items():
  f=Path(rel) if Path(rel).is_absolute() else d/rel
  if not f.is_file():bad.append(dict(file=str(f),error='MISSING'));continue
  st=f.stat();key=(str(f),st.st_size,st.st_mtime_ns)
  if key not in cache:cache[key]=sha(f)
  expected=e if isinstance(e,str) else e['sha256']
  if cache[key]!=expected:bad.append(dict(file=str(f),error='SHA_MISMATCH',expected=expected,actual=cache[key]))
 rows.append(dict(package=name,manifest_sha256=sha(mf),verified_files=len(files),mismatches=bad));errors.extend(bad);print('HISTORY',name,len(files),'mismatches',len(bad),flush=True)
before=json.loads((P/'audit/PROTECTED_METADATA_BEFORE.json').read_text())['files'];changes=[]
for file,s in before.items():
 f=Path(file)
 if not f.exists():changes.append(dict(file=file,change='MISSING'));continue
 st=f.stat()
 if st.st_size!=s['size'] or st.st_mtime_ns!=s['mtime_ns']:changes.append(dict(file=file,change='METADATA_CHANGED'))
after=set()
for directory in ['constraint_geometry_learning_v4','representation_execution_v3','autonomous_coordination_learning_v2','learning_guided_motion_improvement_v1','rl_b_autonomous_stability_reward_v1']:
 for f in (root/directory).rglob('*'):
  if f.is_file() and '__pycache__' not in f.parts and '.git' not in f.parts:after.add(str(f))
added=sorted(after-set(before))
out=dict(status='PASS' if not errors and not changes and not added else 'FAIL',new_protected_files=added,rows=rows,metadata_files=len(before),metadata_changes=changes,wall_s=time.time()-start,zero_new_native_steps=True)
tag=sys.argv[1] if len(sys.argv)>1 else 'RECOVERY';f=P/'audit'/('HISTORY_'+tag+'_VERIFICATION.json');f.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print('HISTORY_ALL',out['status'],'metadata',len(before),'seconds',out['wall_s'],flush=True)
assert out['status']=='PASS','HISTORY_IDENTITY_FAILURE'
