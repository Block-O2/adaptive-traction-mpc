"""Read-only full-content binding for every historical file in the protected inventory."""
from pathlib import Path
import json,hashlib,time,os
P=Path(__file__).resolve().parents[1];root=P.parent;start=time.time();before=json.loads((P/'audit/HISTORY_PROTECTION_START.json').read_text());output={};errors=[];total=0;status='IN_PROGRESS'
def meta(f):
 st=f.stat();return {'bytes':st.st_size,'mtime_ns':st.st_mtime_ns,'mode':st.st_mode,'inode':st.st_ino}
def save(status):
 q=P/'audit/HISTORY_CONTENT_HASH_START.json';t=q.with_suffix('.tmp');t.write_text(json.dumps({'status':status,'started_unix':start,'updated_unix':time.time(),'initial_inventory_recorded_unix':before['recorded_unix'],'files':output,'errors':errors,'bytes_hashed':total,'scope':'Full content snapshot after initial execution identity binding; original metadata unchanged since protection inventory, source/model identities separately bound earlier','pid':os.getpid()},indent=2)+'\n');t.replace(q)
try:
 for i,(rel,m) in enumerate(before['files'].items()):
  f=root/rel
  try:
   if meta(f)!=m:errors.append({'file':rel,'error':'METADATA_CHANGED_BEFORE_FULL_HASH'});continue
   h=hashlib.sha256()
   with f.open('rb') as s:
    for b in iter(lambda:s.read(4*2**20),b''):h.update(b)
   if meta(f)!=m:errors.append({'file':rel,'error':'FILE_CHANGED_WHILE_HASHING'});continue
   output[rel]=h.hexdigest();total+=m['bytes']
  except OSError as e:errors.append({'file':rel,'error':str(e)})
  if i%10000==0:save('IN_PROGRESS')
 status='PASS' if not errors else 'REVIEW_REQUIRED'
finally:save(status if len(output)==len(before['files']) else 'PARTIAL_PRESERVED')
print('HISTORICAL_FULL_HASH',status,len(output),'bytes',total,'wall',time.time()-start,flush=True)
