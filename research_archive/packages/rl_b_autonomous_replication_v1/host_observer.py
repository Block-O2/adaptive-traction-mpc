"""Owned read-only host telemetry, with fail-closed resource-stop file."""
from pathlib import Path
import json,time,os,subprocess,shutil,signal
R=Path(__file__).resolve().parent;cfg=json.loads((R/'PPO_TRAINING_CONFIG.json').read_text());start=time.time()
def put(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
put(R/'audit/OBSERVER_START.json',{'unix':start,'pid':os.getpid()})
try:
 while not (R/'OBSERVER_STOP').exists():
  now=time.time();mem={k:int(v.split()[0])*1024 for k,v in (s.split(':',1) for s in Path('/proc/meminfo').read_text().splitlines())};process=[]
  for line in subprocess.check_output(['ps','-eo','pid,ppid,pcpu,rss,etimes,args'],text=True).splitlines()[1:]:
   v=line.split(None,5)
   if len(v)==6 and str(R) in v[5] and v[5].startswith((str(R.parent/'rl_b_cloud_v1/.venv/bin/python'),'python')):process.append({'pid':int(v[0]),'ppid':int(v[1]),'cpu_pct':float(v[2]),'rss_KiB':int(v[3]),'elapsed_s':int(v[4]),'command':v[5]})
  size=sum(p.stat().st_size for p in R.rglob('*') if p.is_file());row={'unix':now,'available_ram_bytes':mem['MemAvailable'],'disk_free_bytes':shutil.disk_usage(R).free,'package_bytes':size,'owned_processes':process,'loadavg':os.getloadavg()}
  with (R/'audit/HOST_RESOURCE_SAMPLES.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
  reason='HARD_STOP_8H' if now>=cfg['hard_stop_unix'] else 'PACKAGE_DISK_BUDGET' if size>cfg['max_output_GiB']*1024**3 else 'RAM_RESERVE' if mem['MemAvailable']<6*1024**3 else None
  if reason:
   (R/'RESOURCE_STOP').write_text(reason+'\n');put(R/'audit/OBSERVER_RESOURCE_STOP.json',{'unix':now,'reason':reason})
   if now>=cfg['hard_stop_unix']:
    for p in process:
     if p['pid']!=os.getpid():
      try:os.kill(p['pid'],signal.SIGTERM)
      except ProcessLookupError:pass
    break
  time.sleep(15)
finally:put(R/'audit/OBSERVER_END.json',{'unix':time.time(),'pid':os.getpid(),'wall_s':time.time()-start})
