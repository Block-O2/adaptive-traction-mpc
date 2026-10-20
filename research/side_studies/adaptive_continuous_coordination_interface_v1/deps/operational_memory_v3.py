"""Streaming artifact logging and lifecycle evidence; no rollout semantics changes."""
from pathlib import Path
import os,json,time,gc,inspect
import numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_interface_v1'); L=P/'output'
def phase(stage,**extra):
 row=dict(unix=time.time(),pid=os.getpid(),stage=stage,**extra)
 target=L/'OPERATIONAL_PHASE_36283.json'; tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(row));tmp.replace(target)
 return row
def evidence(stage,**extra):
 mem={}
 for name in ['status','smaps_rollup']:
  try:
   for line in Path('/proc/self/'+name).read_text().splitlines():
    if ':' in line:
     k,v=line.split(':',1)
     if k in ['VmRSS','Rss','Pss','Private_Dirty','Pss_Anon']:mem[k]=int(v.split()[0])*1024
  except FileNotFoundError:pass
 row=dict(unix=time.time(),pid=os.getpid(),stage=stage,memory=mem,**extra)
 with (L/'LIFECYCLE_36283.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
 return row
def chunks(value):
 # Match runtime._jsonable recursively without copying the complete payload or string.
 if isinstance(value,np.ndarray):value=value.tolist()
 if isinstance(value,np.generic):value=value.item()
 if isinstance(value,dict):
  yield '{'
  for i,(key,item) in enumerate(value.items()):
   if i:yield ','
   yield json.dumps(str(key));yield ':';yield from chunks(item)
  yield '}'
 elif isinstance(value,(tuple,list)):
  yield '['
  for i,item in enumerate(value):
   if i:yield ','
   yield from chunks(item)
  yield ']'
 else:
  if isinstance(value,float) and not np.isfinite(value):value=None
  yield json.dumps(value,allow_nan=False)
def stream_payload(output_dir,payload):
 previous=json.loads((L/'OPERATIONAL_PHASE_36283.json').read_text()).get('stage','RESTORED_IDLE')
 phase(previous+'_ARCHIVE');before=evidence('ARCHIVE_BEGIN',trace_rows=len(payload.get('trace',[])))
 path=Path(output_dir)/'runtime_artifacts.json';tmp=path.with_suffix('.json.tmp')
 with tmp.open('w') as f:
  # Bounded text buffering. Never materialize the whole JSON document.
  block=[];size=0
  for part in chunks(payload):
   block.append(part);size+=len(part)
   if size>=262144:f.write(''.join(block));block=[];size=0
  f.write(''.join(block));f.write('\n')
 tmp.replace(path);evidence('ARCHIVE_END',bytes=path.stat().st_size,begin_unix=before['unix'])
 phase(previous)
def install(rt):
 original=inspect.getsource(rt.persist_runtime_artifacts)
 old='(output_dir / "runtime_artifacts.json").write_text(\n        json.dumps(_jsonable(payload), indent=2, allow_nan=False) + "\\n")'
 assert original.count(old)==1,'SERIALIZER_SOURCE_CHANGED'
 revised=original.replace(old,'stream_payload(output_dir, payload)')
 namespace=dict(rt.__dict__,stream_payload=stream_payload)
 exec(compile(revised,'<versioned streaming runtime artifact serializer>','exec'),namespace)
 rt.persist_runtime_artifacts=namespace['persist_runtime_artifacts']
 evidence('STREAM_SERIALIZER_INSTALLED',original_json_fields_unchanged=True,formatting_only_compact=True)
def descendants(pid):
 rows=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   d=dict(x.split(':',1) for x in (p/'status').read_text().splitlines() if ':' in x)
   rows.append((int(p.name),int(d['PPid']),(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')))
  except (FileNotFoundError,ProcessLookupError,PermissionError):pass
 owned={pid}
 while True:
  new=owned|{p for p,parent,_ in rows if parent in owned}
  if new==owned:break
  owned=new
 return [dict(pid=p,ppid=parent,cmd=cmd) for p,parent,cmd in rows if p in owned and p!=pid]
