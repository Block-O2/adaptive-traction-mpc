from pathlib import Path
import os,time,json,shutil
from acl2_shared import P,put,read,append,sha,utc
A=read('ACTIVATION.json');deadline=A['t0_unix']+9.333333*3600
put('owned/RESOURCE_MONITOR_START.json',dict(utc=utc(),pid=os.getpid(),deadline_unix=deadline,source_sha256=sha(__file__),scope='Resource telemetry from this UTC onward; earlier live snapshots and native RAM-floor assertions remain separate.'))
for _ in range(20000):
 if time.time()>deadline or (P/'CLOSURE_START.json').exists() or (P/'END.json').exists():break
 mem=dict(s.split(':',1) for s in Path('/proc/meminfo').read_text().splitlines());procs=[]
 for f in Path('/proc').glob('[0-9]*/environ'):
  try:
   if ('ACL2_OWNER='+A['identity']).encode()+b'\0' not in f.read_bytes():continue
   s=(f.parent/'stat').read_text();tail=s[s.rfind(')')+2:].split();procs.append(dict(pid=int(f.parent.name),ppid=int(tail[1]),state=tail[0],rss_bytes=int(tail[21])*os.sysconf('SC_PAGE_SIZE'),CPU_user_ticks=int(tail[11]),CPU_system_ticks=int(tail[12]),start_ticks=int(tail[19])))
  except (OSError,ValueError):pass
 append('RESOURCE_TELEMETRY.jsonl',dict(utc=utc(),elapsed_h=(time.time()-A['t0_unix'])/3600,available_ram_gib=int(mem['MemAvailable'].split()[0])/2**20,free_disk_gib=shutil.disk_usage(P).free/2**30,owned_processes=procs))
 time.sleep(10)
put('owned/RESOURCE_MONITOR_END.json',dict(utc=utc(),pid=os.getpid(),status='STOP'))
