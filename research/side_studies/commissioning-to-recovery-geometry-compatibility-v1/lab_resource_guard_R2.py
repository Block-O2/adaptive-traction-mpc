"""Side-owned resource observer: no peer mutations."""
from pathlib import Path
import json,subprocess,time,os
from datetime import datetime,timezone
W=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/commissioning-to-recovery-geometry-compatibility-v1')
def sample():
 m={k:int(v.split()[0]) for line in Path('/proc/meminfo').read_text().splitlines() for k,v in [line.split(':',1)]}
 vm=dict(x.split() for x in Path('/proc/vmstat').read_text().splitlines())
 free=subprocess.check_output(['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-NonInteractive','-Command','(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory'],text=True)
 entries=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   status=dict(x.split(':',1) for x in (p/'status').read_text().splitlines() if ':' in x)
   command=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
   entries.append(dict(pid=int(p.name),ppid=int(status['PPid']),rss_KiB=int(status.get('VmRSS','0 kB').split()[0]),peak_rss_KiB=int(status.get('VmHWM','0 kB').split()[0]),name=status['Name'].strip(),command=command))
  except (FileNotFoundError,ProcessLookupError,PermissionError):pass
 peers=[x for x in entries if 'python' in x['name'] and ('adaptive-traction-mpc-learning' in x['command'] or 'single_human_sac' in x['command'])]
 heavy=[x for x in peers if any(v in x['command'].lower() for v in ['throughput','benchmark','train']) and not any(v in x['command'].lower() for v in ['diagnos','replay'])]
 roots={x['pid'] for x in entries if 'python' in x['name'] and str(W) in x['command']}
 descendants=roots
 while True:
  expanded=descendants|{x['pid'] for x in entries if x['ppid'] in descendants}
  if expanded==descendants:break
  descendants=expanded
 side=[x for x in entries if x['pid'] in descendants]
 r=dict(utc=datetime.now(timezone.utc).isoformat(),WSL_available_GiB=m['MemAvailable']/1048576,Windows_available_GiB=int(free.strip())/1048576,swap_used_KiB=m['SwapTotal']-m['SwapFree'],oom_kill_count=int(vm.get('oom_kill',0)),CPU_load=Path('/proc/loadavg').read_text().strip(),SAC_workers=peers,SAC_heavy_workers=heavy,side_workers=side,side_aggregate_RSS_KiB=sum(x['rss_KiB'] for x in side))
 with (W/'RESOURCE_SAMPLES.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
 return r
def verify_release(runtime_sha256=None):
 r=sample()
 if r['SAC_heavy_workers'] or r['WSL_available_GiB']<3 or r['Windows_available_GiB']<2 or r['swap_used_KiB']>0:raise RuntimeError('READY_WAITING_FOR_RESOURCES:'+json.dumps(r))
 return r
class ResourceStop:
 def __init__(self,initial):
  self.last=0.;self.swap=initial['swap_used_KiB'];self.growth=0;self.oom=initial['oom_kill_count']
 def __call__(self):
  if time.monotonic()-self.last<30:return
  self.last=time.monotonic();r=sample()
  if r['SAC_heavy_workers']:
   s=json.loads((W/'STATE.json').read_text());s.update(pause_before_next=True,pause_reason='SAC_HEAVY_FINISH_CURRENT_THEN_PAUSE');(W/'STATE.json').write_text(json.dumps(s,indent=2)+'\n')
  self.growth=self.growth+1 if r['swap_used_KiB']-self.swap>65536 else 0;self.swap=r['swap_used_KiB']
  if r['WSL_available_GiB']<1 or r['Windows_available_GiB']<1 or self.growth>=2 or r['oom_kill_count']>self.oom:raise RuntimeError('SIDE_ONLY_COOPERATIVE_RESOURCE_STOP')
