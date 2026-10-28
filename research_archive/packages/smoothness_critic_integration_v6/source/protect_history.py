from pathlib import Path
import json,time,hashlib,sys
P=Path(__file__).resolve().parents[1];root=P.parent

def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as s:
  for b in iter(lambda:s.read(4*2**20),b''):h.update(b)
 return h.hexdigest()
def inventory():
 result={}
 for d in root.iterdir():
  if d==P or d.name=='RESEARCH_DECISION_JOURNAL.md':continue
  for f in (d.rglob('*') if d.is_dir() else [d]):
   if not f.is_file():continue
   st=f.stat();rel=str(f.relative_to(root));result[rel]={'bytes':st.st_size,'mtime_ns':st.st_mtime_ns,'mode':st.st_mode,'inode':st.st_ino}
 return result
if sys.argv[1]=='start':
 data=inventory();a=json.loads((P/'ACTIVATION.json').read_text());late=[r for r,v in data.items() if v['mtime_ns']/1e9>a['T0_unix']];critical={r:sha(root/r) for r in data if Path(r).suffix in ['.py','.pt','.pth','.pkl','.ckpt'] and '/.venv/' not in r}
 (P/'audit/HISTORY_PROTECTION_START.json').write_text(json.dumps({'recorded_unix':time.time(),'files':data,'critical_sha256':critical,'historical_files_modified_since_T0':late},indent=2)+'\n');print('HISTORY_START',len(data),'critical',len(critical),'late',late[:15],flush=True)
else:
 start=json.loads((P/'audit/HISTORY_PROTECTION_START.json').read_text());now=inventory();errors=[r for r,v in start['files'].items() if now.get(r)!=v];extra=sorted(set(now)-set(start['files']));hasherr=[r for r,h in start['critical_sha256'].items() if not (root/r).exists() or sha(root/r)!=h];out={'status':'PASS' if not errors and not extra and not hasherr and not start['historical_files_modified_since_T0'] else 'FAIL','checked_files':len(now),'metadata_changes':errors,'added_historical_files':extra,'critical_hash_mismatches':hasherr,'late_at_start':start['historical_files_modified_since_T0']};(P/'audit/HISTORY_PROTECTION_FINAL.json').write_text(json.dumps(out,indent=2)+'\n');print('HISTORY_FINAL',out['status'],flush=True)
