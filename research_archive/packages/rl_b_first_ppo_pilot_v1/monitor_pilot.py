"""Owned host observer; no control/physics writes."""
from pathlib import Path
import json,time,os,subprocess,shutil
r=Path(__file__).resolve().parent;cfg=json.loads((r/'PPO_TRAINING_CONFIG.json').read_text());start=time.time()
(r/'audit/MONITOR_START.json').write_text(json.dumps({'pid':os.getpid(),'unix':start}))
try:
 while time.time()<cfg['hard_stop_unix'] and not (r/'OBSERVER_STOP').exists():
  lines=subprocess.check_output(['ps','-eo','pid,ppid,pcpu,rss,etime,args'],text=True).splitlines();owned=[]
  for line in lines[1:]:
   if any(x in line for x in ['pilot_run.py','resource_guard.py','monitor_pilot.py']) and 'ps -eo' not in line and '/bin/bash -lc' not in line:
    fields=line.split(None,5)
    if len(fields)==6:owned.append({'pid':int(fields[0]),'ppid':int(fields[1]),'cpu_pct':float(fields[2]),'rss_KiB':int(fields[3]),'elapsed':fields[4],'command':fields[5]})
  mem={k:int(v.split()[0])*1024 for k,v in (s.split(':',1) for s in Path('/proc/meminfo').read_text().splitlines())}
  checkpoint_bytes=sum(p.stat().st_size for p in (r/'checkpoints').glob('*') if p.is_file())
  row={'unix':time.time(),'owned':owned,'available_ram_bytes':mem['MemAvailable'],'disk_free_bytes':shutil.disk_usage(r).free,'checkpoint_bytes':checkpoint_bytes,'loadavg':os.getloadavg()}
  with (r/'audit/HOST_RESOURCE_SAMPLES.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
  time.sleep(15)
finally:(r/'audit/MONITOR_END.json').write_text(json.dumps({'pid':os.getpid(),'unix':time.time(),'stop_file':(r/'OBSERVER_STOP').exists()}))
