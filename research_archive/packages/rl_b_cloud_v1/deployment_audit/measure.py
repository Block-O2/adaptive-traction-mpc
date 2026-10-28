"""External process-tree telemetry; never enters actor/controller or changes physics."""
import argparse,subprocess,time,pathlib,os,json,signal
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True);command=a.command[1:] if a.command[:1]==['--'] else a.command
assert command and not (out/'MEASURE_START.json').exists()
begin=time.monotonic();hz=os.sysconf('SC_CLK_TCK');page=os.sysconf('SC_PAGE_SIZE');samples=[];last_cpu=None;last_t=None
proc=subprocess.Popen(command)
(out/'MEASURE_START.json').write_text(json.dumps({'unix':time.time(),'pid':proc.pid,'command':command},indent=2))
try:
 while True:
  table={}
  for d in pathlib.Path('/proc').iterdir():
   if not d.name.isdigit():continue
   try:
    parts=(d/'stat').read_text().rsplit(')',1)[1].split();table[int(d.name)]={'ppid':int(parts[1]),'cpu_s':(int(parts[11])+int(parts[12]))/hz,'rss_bytes':int(parts[21])*page}
   except (OSError,ValueError,IndexError):pass
  owned={proc.pid}
  while True:
   new=owned|{pid for pid,x in table.items() if x['ppid'] in owned}
   if new==owned:break
   owned=new
  rows=[{'pid':pid,**table[pid]} for pid in sorted(owned) if pid in table];cpu=sum(x['cpu_s'] for x in rows);now=time.monotonic()
  mem={k:int(v.split()[0])*1024 for k,v in (x.split(':',1) for x in pathlib.Path('/proc/meminfo').read_text().splitlines())}
  row={'elapsed_s':now-begin,'unix':time.time(),'processes':rows,'sum_RSS_bytes':sum(x['rss_bytes'] for x in rows),'live_cpu_s':cpu,'cpu_percent':None if last_cpu is None else max(0.,100*(cpu-last_cpu)/(now-last_t)),'host_available_bytes':mem['MemAvailable']}
  with (out/'process_telemetry.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
  samples.append(row);last_cpu=cpu;last_t=now
  if proc.poll() is not None:break
  if now-begin>1800:
   proc.send_signal(signal.SIGINT);proc.wait(timeout=20);raise RuntimeError('MEASUREMENT_HARD_WALL')
  time.sleep(.5)
finally:
 if proc.poll() is None:
  proc.send_signal(signal.SIGINT)
  try:proc.wait(timeout=20)
  except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=5)
 result={'returncode':proc.returncode,'wall_s':time.monotonic()-begin,'samples':len(samples),'peak_sum_RSS_bytes':max((r['sum_RSS_bytes'] for r in samples),default=0),'minimum_host_available_bytes':min((r['host_available_bytes'] for r in samples),default=None),'mean_sampled_cpu_percent':sum(r['cpu_percent'] or 0 for r in samples)/max(1,len(samples)-1),'scope':'sum per-process RSS includes shared pages; sampled CPU is live process-tree counter delta'}
 (out/'MEASURE_END.json').write_text(json.dumps(result,indent=2))
 print(json.dumps(result),flush=True)
raise SystemExit(proc.returncode)
