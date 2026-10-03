"""Study-owned resource checks; read-only SAC state, never signals SAC."""
from pathlib import Path
import json,subprocess,time,os,shutil
from datetime import datetime,timezone
W=Path('<SIDE_STUDIES_ROOT>/lab-human-adaptation-contrast-v1')
SAC=Path('<PRIMARY_REPOSITORY>/stages/stage5_personalized_motion_learning/docs/single_human_sac_expert_v1/STATE.json')
def sample():
 m={k:int(v.split()[0]) for line in Path('/proc/meminfo').read_text().splitlines() for k,v in [line.split(':',1)]}
 result=subprocess.check_output(['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-NonInteractive','-Command','(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory'],text=True)
 state=json.loads(SAC.read_text());ps=subprocess.check_output(['ps','-eo','pid,ppid,rss,ni,args'],text=True)
 sac_processes=[s for s in ps.splitlines() if 'python' in s and ('single_human_sac' in s or 'adaptive-online-rl' in s)]
 phase=str(state.get('phase','')).upper()
 # Ambiguous qualification/benchmark state is intentionally not released by
 # absence of a substring. A release must contain an independent stage check.
 return {'utc':datetime.now(timezone.utc).isoformat(),'WSL_available_GiB':m['MemAvailable']/1048576,'Windows_available_GiB':int(result.strip())/1048576,'swap_used_KiB':m['SwapTotal']-m['SwapFree'],'SAC_state':state,'SAC_processes':sac_processes,'explicit_benchmark_phase':any(t in phase for t in ['THROUGHPUT','LATENCY','BENCHMARK']),'side_disk_free_bytes':shutil.disk_usage(W).free,'Windows_C_free_bytes':shutil.disk_usage('/mnt/c').free}
def gate_reasons(r,peak,verified,stage_confirmed):
 reasons=[]
 if not verified:reasons.append('NO_VERIFIED_AGGREGATE_PARENT_PLANNER_PEAK')
 if not stage_confirmed or r['explicit_benchmark_phase']:reasons.append('SAC_FORMAL_BENCHMARK_EXCLUSION_NOT_CONFIRMED')
 if r['WSL_available_GiB']<peak+2:reasons.append('WSL_RESERVE_BEYOND_SIDE_PEAK_LT_2GiB')
 # Retain Windows 4GiB during the projected side-study peak as well as at start.
 if r['Windows_available_GiB']<peak+4:reasons.append('WINDOWS_PROJECTED_RESERVE_LT_4GiB')
 if r['swap_used_KiB']>0:reasons.append('SWAP_USED_REQUIRES_TREND_REVIEW')
 return reasons
def verify_release(runtime_sha256):
 p=W/'RESOURCE_RELEASE.json'
 if not p.exists():raise RuntimeError('READY_WAITING_FOR_RESOURCES: no verified RESOURCE_RELEASE.json')
 release=json.loads(p.read_text())
 assert release['runtime_sha256']==runtime_sha256
 assert release['aggregate_parent_planner_peak_verified'] is True
 assert release['evidence_files'] and all(Path(p).is_file() for p in release['evidence_files'])
 age=(datetime.now(timezone.utc)-datetime.fromisoformat(release['observed_utc'])).total_seconds()
 assert 0<=age<=300,'SAC stage/resource release observation stale'
 r=sample();peak=float(release['conservative_peak_GiB']);assert peak>0
 reasons=gate_reasons(r,peak,True,release['SAC_not_in_formal_benchmark_confirmed'] is True)
 with (W/'RESOURCE_SAMPLES.jsonl').open('a') as out:out.write(json.dumps(r)+'\n')
 if reasons:raise RuntimeError('READY_WAITING_FOR_RESOURCES:'+','.join(reasons))
 return r
class ResourceStop:
 def __init__(self,initial):self.last=0.;self.initial_swap=initial['swap_used_KiB']
 def __call__(self):
  if time.monotonic()-self.last<30:return
  self.last=time.monotonic();r=sample()
  with (W/'RESOURCE_SAMPLES.jsonl').open('a') as out:out.write(json.dumps(r)+'\n')
  if ((W/'SIDE_STOP').exists() or r['WSL_available_GiB']<2 or r['Windows_available_GiB']<4 or r['swap_used_KiB']>self.initial_swap or r['explicit_benchmark_phase']):
   raise RuntimeError('SIDE_STUDY_RESOURCE_PAUSE: serialize partial evidence; SAC untouched')
