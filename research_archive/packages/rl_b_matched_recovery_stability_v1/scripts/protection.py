from pathlib import Path
import json,hashlib,time,sys
r=Path('/home/hank/ihear-lab/rl_b_matched_recovery_stability_v1'); root=r.parent
names=['rl_b_cloud_v1','rl_b_cloud_g4_repair_v1','rl_b_g4_closure_ppo_readiness_v1','rl_b_first_ppo_pilot_v1','rl_b_autonomous_replication_v1']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
if sys.argv[1]=='start':
 entries=[]
 paths=[p for n in names for p in (root/n).rglob('*') if p.is_file() and '.venv' not in p.parts and 'venv' not in p.parts]
 paths += list(root.glob('*.zip'))+list(root.glob('*ARCHIVE_VERIFICATION.json'))+[Path('/home/hank/ihear_rl_b_cpu_cloud_v1.zip')]
 for p in sorted(set(paths)):
  st=p.stat();entries.append({'path':str(p),'bytes':st.st_size,'sha256':sha(p),'mtime_ns':st.st_mtime_ns})
 (r/'audit/HISTORICAL_PROTECTION_START.json').write_text(json.dumps({'created_unix':time.time(),'exclude':'Existing virtual environments excluded; all study evidence, source, checkpoints, raw and ZIPs included.','files':entries},indent=2))
 print('START',len(entries),sum(e['bytes'] for e in entries))
else:
 a=json.loads((r/'audit/HISTORICAL_PROTECTION_START.json').read_text());out=[]
 for e in a['files']:
  p=Path(e['path']);s=sha(p) if p.exists() else None
  if s!=e['sha256']:out.append({'path':str(p),'expected':e['sha256'],'actual':s})
 (r/'audit/HISTORICAL_PROTECTION_END.json').write_text(json.dumps({'files_verified':len(a['files']),'mismatches':out,'pass':not out,'verified_unix':time.time()},indent=2));print('END',len(a['files']),len(out))
