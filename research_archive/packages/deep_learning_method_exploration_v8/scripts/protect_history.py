from pathlib import Path
import json,hashlib,time,os,sys,signal
P=Path(__file__).resolve().parents[1]; ROOT=P.parent
mode=sys.argv[1]; started=time.time(); signal.alarm(1800)
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as s:
  for b in iter(lambda:s.read(4*2**20),b''): h.update(b)
 return h.hexdigest()
def meta(f):
 s=f.stat();return dict(bytes=s.st_size,mtime_ns=s.st_mtime_ns,mode=s.st_mode,inode=s.st_ino)
def inventory():
 out={}
 for d in sorted(ROOT.iterdir()):
  if d==P or d.name=='RESEARCH_DECISION_JOURNAL.md':continue
  for f in sorted(d.rglob('*')) if d.is_dir() else [d]:
   if f.is_file():out[str(f.relative_to(ROOT))]=meta(f)
 return out
def put(n,x):
 f=P/'audit'/n;q=f.with_suffix('.tmp');q.write_text(json.dumps(x,ensure_ascii=False)+'\n');q.replace(f)
ident=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),started_unix=started,source_sha256=sha(Path(__file__)))
put('HISTORY_'+mode.upper()+'_PROCESS_START.json',ident)
errors=[];total=0;content={}
try:
 now=inventory()
 if mode=='start':
  a=json.loads((P/'ACTIVATION.json').read_text());late=[r for r,m in now.items() if m['mtime_ns']/1e9>a['t0_unix']]
  put('HISTORY_PROTECTION_START.json',dict(recorded_unix=time.time(),files=now,modified_since_t0=late))
  for i,(r,m) in enumerate(now.items()):
   f=ROOT/r
   if meta(f)!=m:errors.append(dict(file=r,error='CHANGED_BEFORE_HASH'));continue
   content[r]=sha(f);total+=m['bytes']
   if meta(f)!=m:errors.append(dict(file=r,error='CHANGED_DURING_HASH'))
   if i%20000==0:print('HASH_PROGRESS',i,len(now),total,flush=True)
  put('HISTORY_CONTENT_START.json',dict(recorded_unix=time.time(),files=content,bytes_hashed=total,errors=errors,status='PASS' if not errors and not late else 'REVIEW_REQUIRED',started_unix=started,scope='Full content snapshot at recorded time; metadata checked against T0, not claimed exact T0 content'))
 else:
  old=json.loads((P/'audit/HISTORY_PROTECTION_START.json').read_text());before=json.loads((P/'audit/HISTORY_CONTENT_START.json').read_text())
  errors += [dict(file=r,error='METADATA_CHANGE') for r,m in old['files'].items() if now.get(r)!=m]
  errors += [dict(file=r,error='ADDED_HISTORICAL_FILE') for r in set(now)-set(old['files'])]
  for r,h in before['files'].items():
   f=ROOT/r
   if not f.exists() or sha(f)!=h:errors.append(dict(file=r,error='CONTENT_CHANGE'))
   else:total+=f.stat().st_size
  put('HISTORY_PROTECTION_FINAL.json',dict(recorded_unix=time.time(),status='PASS' if not errors else 'FAIL',files_checked=len(before['files']),bytes_hashed=total,errors=errors))
 put('HISTORY_'+mode.upper()+'_PROCESS_END.json',dict(**ident,ended_unix=time.time(),wall_s=time.time()-started,status='PASS' if not errors else 'REVIEW_REQUIRED'))
 print('HISTORY_DONE',mode,len(now),total,len(errors),time.time()-started,flush=True)
except BaseException as e:
 put('HISTORY_'+mode.upper()+'_PROCESS_END.json',dict(**ident,ended_unix=time.time(),status='FAILED_PRESERVED',error=str(e)));raise
