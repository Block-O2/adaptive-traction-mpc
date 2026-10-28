from pathlib import Path
import json,time,os,shutil,datetime
r=Path(__file__).resolve().parents[1];start=time.time();(r/'audit/MONITOR_PID.json').write_text(json.dumps({'pid':os.getpid(),'start':start}))
while not (r/'audit/STOP_MONITOR').exists():
 mem={k:int(v.split()[0])*1024 for k,v in (s.split(':',1) for s in Path('/proc/meminfo').read_text().splitlines()) if v.strip().split() and v.strip().split()[0].isdigit()}
 row={'unix':time.time(),'available_ram_bytes':mem['MemAvailable'],'disk_free_bytes':shutil.disk_usage(r).free,'loadavg':os.getloadavg(),'cpu_ticks':Path('/proc/stat').read_text().splitlines()[0]}
 with (r/'audit/RESOURCE_SAMPLES.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
 if mem['MemAvailable']<6*1024**3:(r/'audit/RESOURCE_STOP').write_text(json.dumps(row))
 if time.time()-start>5*3600:break
 time.sleep(15)
(r/'audit/MONITOR_END.json').write_text(json.dumps({'pid':os.getpid(),'end':time.time()}))
