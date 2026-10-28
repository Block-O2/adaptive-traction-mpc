from pathlib import Path
import os,time,json,signal,datetime,shutil
P=Path(__file__).resolve().parents[1];start=json.loads((P/'START.json').read_text());deadline=datetime.datetime.fromisoformat(start['deadline_utc']).timestamp();known={};reason=None
while not (P/'MONITOR_STOP').exists():
 mem={k:int(v.split()[0])*1024 for k,v in (r.split(':',1) for r in Path('/proc/meminfo').read_text().splitlines())};owned=[]
 for proc in Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try:
   argv=(proc/'cmdline').read_bytes().split(b'\0');cmd=[a.decode(errors='replace') for a in argv if a]
   if cmd and 'python' in Path(cmd[0]).name and any(a in [str(P/'source/recovery_worker.py'),str(P/'source/study_worker.py'),str(P/'source/validation_worker.py')] for a in cmd):
    pid=int(proc.name);stamp=(proc/'stat').read_text().split()[21];owned.append({'pid':pid,'start_ticks':stamp,'argv':cmd});known[pid]=stamp
  except (FileNotFoundError,PermissionError,ProcessLookupError):pass
 row={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'unix':time.time(),'available_ram_bytes':mem['MemAvailable'],'disk_free_bytes':shutil.disk_usage(P).free,'owned_physics':owned}
 with (P/'audit/RESOURCE_SAMPLES.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
 if time.time()>=deadline:reason='HARD_7_HOUR_DEADLINE'
 elif mem['MemAvailable']<6*2**30:reason='RAM_BELOW_6_GIB'
 elif shutil.disk_usage(P).free<12*2**30:reason='DISK_BELOW_12_GIB'
 if reason:
  (P/'STOP_REQUESTED').write_text(reason)
  for proc in owned:
   try:
    if Path('/proc/'+str(proc['pid'])+'/stat').read_text().split()[21]==proc['start_ticks']:os.kill(proc['pid'],signal.SIGINT)
   except (ProcessLookupError,FileNotFoundError):pass
  break
 time.sleep(5)
(P/'audit/MONITOR_END.json').write_text(json.dumps({'pid':os.getpid(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reason':reason or 'ORDERLY_STOP','known_owned':known},indent=2)+'\n')
