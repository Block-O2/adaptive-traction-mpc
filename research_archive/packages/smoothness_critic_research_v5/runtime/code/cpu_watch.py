from pathlib import Path
import json,time,os
S=Path('/home/hank/ihear-lab/smoothness_critic_research_v5/runtime')
def main():
 plan=json.loads((S/'RUN_PLAN.json').read_text());pid=os.getpid()
 (S/'CPU_WATCH_READY.json').write_text(json.dumps(dict(pid=pid,unix=time.time(),start_ticks=Path('/proc/self/stat').read_text().split(') ',1)[1].split()[19],scope='Global CPU load/stat only; task-owned PSS and memory remain native campaign sampler scope.'),indent=2)+'\n')
 count=0
 while time.time()<plan['dispatch_cutoff_unix'] and not (S/'STOP_CPU_WATCH').exists():
  row=dict(unix=time.time(),pid=pid,load=os.getloadavg(),cpu_stat=Path('/proc/stat').read_text(),process_count=sum(p.name.isdigit() for p in Path('/proc').iterdir()))
  with (S/'output/CPU_WATCH.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
  count+=1
  for _ in range(45):
   if (S/'STOP_CPU_WATCH').exists():break
   time.sleep(1)
 (S/'CPU_WATCH_JOINED.json').write_text(json.dumps(dict(pid=pid,unix=time.time(),samples=count,stopped=True),indent=2)+'\n')
 print('CPU_WATCH_STOPPED',count,flush=True)
if __name__=='__main__':main()
