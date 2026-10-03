"""R2 side-owned resource coordination. No SAC writes/signals/configuration."""
from pathlib import Path
import json,subprocess,time,os,shutil
from datetime import datetime,timezone
W=Path('<SIDE_STUDIES_ROOT>/lab-human-adaptation-contrast-v1')
SAC=Path('<PRIMARY_REPOSITORY>/stages/stage5_personalized_motion_learning/docs/single_human_sac_expert_v1/STATE.json')
def utc():return datetime.now(timezone.utc).isoformat()
def sample():
 m={k:int(v.split()[0]) for line in Path('/proc/meminfo').read_text().splitlines() for k,v in [line.split(':',1)]}
 vm={k:int(v) for k,v in [x.split() for x in Path('/proc/vmstat').read_text().splitlines()]}
 free=subprocess.check_output(['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-NonInteractive','-Command','(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory'],text=True)
 state=json.loads(SAC.read_text())
 entries=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   status=dict(x.split(':',1) for x in (p/'status').read_text().splitlines() if ':' in x)
   command=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
   entries.append(dict(pid=int(p.name),ppid=int(status['PPid']),rss_KiB=int(status.get('VmRSS','0 kB').split()[0]),name=status['Name'].strip(),command=command))
  except (FileNotFoundError,ProcessLookupError,PermissionError):pass
 workers=[x for x in entries if 'python' in x['name'] and ('adaptive-traction-mpc-learning' in x['command'] or 'single_human_sac' in x['command']) and 'lab-human-adaptation-contrast-v1' not in x['command']]
 # Physical SAC/qualification workers cannot be assumed to be static report work.
 heavy_workers=[x for x in workers if any(t in x['command'].lower() for t in ['throughput','train','rollout','profile','benchmark','qualification'])]
 phase=str(state.get('phase','')).upper()
 state_heavy=any(t in phase for t in ['THROUGHPUT','TRAINING','ROLLOUT','LATENCY','PROFIL','BENCHMARK'])
 roots=[x['pid'] for x in entries if any(n in x['command'] for n in ['human_qualification_R2.py','serial_campaign_R2.py','postprocess_lab_run_R2.py','supplement_run_evidence_R2.py','oracle_C5_R2.py']) and 'python' in x['name']]
 descendants=set(roots)
 while True:
  expanded=descendants|{x['pid'] for x in entries if x['ppid'] in descendants}
  if expanded==descendants:break
  descendants=expanded
 side=[x for x in entries if x['pid'] in descendants]
 try:gpu=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True,timeout=8).strip()
 except Exception as e:gpu='UNAVAILABLE:'+type(e).__name__
 r=dict(utc=utc(),WSL_available_GiB=m['MemAvailable']/1048576,Windows_available_GiB=int(free.strip())/1048576,swap_used_KiB=m['SwapTotal']-m['SwapFree'],oom_kill_count=vm.get('oom_kill'),memory_pressure=Path('/proc/pressure/memory').read_text(),CPU_load=Path('/proc/loadavg').read_text().strip(),GPU_memory_MiB_util_percent=gpu,SAC_state=state,SAC_state_mtime_utc=datetime.fromtimestamp(SAC.stat().st_mtime,timezone.utc).isoformat(),SAC_python_workers=workers,heavy_workers=heavy_workers,SAC_heavy_observed=bool(state_heavy or heavy_workers),side_workers=side,side_parent_children_RSS_KiB=sum(x['rss_KiB'] for x in side),side_disk_free_bytes=shutil.disk_usage(W).free,Windows_C_free_bytes=shutil.disk_usage('/mnt/c').free)
 with (W/'RESOURCE_SAMPLES_R2.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
 return r
def gate_reasons(r,peer,qualification):
 reasons=[]
 if r['SAC_heavy_observed']:reasons.append('SAC_HEAVY_WORKER_OR_PHASE')
 if not peer:reasons.append('NO_FRESH_SAC_PHASE_OBSERVATION')
 else:
  age=(datetime.now(timezone.utc)-datetime.fromisoformat(peer['utc'])).total_seconds()
  if not 0<=age<=300:reasons.append('SAC_PHASE_OBSERVATION_STALE')
  if peer['heavy_or_imminent_formal_measurement']:reasons.append('SAC_FORMAL_MEASUREMENT_OR_TRAINING_RESERVED')
 if r['Windows_available_GiB']<2 or r['WSL_available_GiB']<3:reasons.append('OBSERVED_LOW_MEMORY_HEADROOM')
 if r['swap_used_KiB']>0:reasons.append('SWAP_PRESENT_NEEDS_TREND_REVIEW')
 if qualification and qualification.get('qualification_pass') is not True:reasons.append('FIRST_RESOURCE_QUALIFICATION_NOT_PASSED')
 return reasons
def verify_release(runtime_sha256):
 c=json.loads((W/'CONTRACT_R2.json').read_text())
 import hashlib
 runtime=W/'snapshot/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py'
 assert hashlib.sha256(runtime.read_bytes()).hexdigest()==runtime_sha256
 peerfile=W/'SAC_PHASE_OBSERVATION_R2.json';peer=json.loads(peerfile.read_text()) if peerfile.exists() else None
 state=json.loads((W/'STATE_R2.json').read_text())
 qualification=json.loads((W/'RESOURCE_DYNAMIC_QUALIFICATION.json').read_text()) if state['primary_attempts']>0 else None
 r=sample();reasons=gate_reasons(r,peer,qualification)
 if reasons:raise RuntimeError('READY_WAITING_FOR_RESOURCES:'+','.join(reasons))
 assert c['hard_active_hours']==6
 return r
class ResourceStop:
 def __init__(self,initial):
  self.last=0.;self.previous_swap=initial['swap_used_KiB'];self.swap_growth_samples=0;self.initial_oom=initial['oom_kill_count']
 def __call__(self):
  if time.monotonic()-self.last<30:return
  self.last=time.monotonic();r=sample()
  if r['SAC_heavy_observed']:
   p=W/'STATE_R2.json';s=json.loads(p.read_text());s.update(pause_before_next=True,pause_reason='SAC_HEAVY_STARTED_FINISH_CURRENT_ONLY');p.write_text(json.dumps(s,indent=2)+'\n')
  self.swap_growth_samples=self.swap_growth_samples+1 if r['swap_used_KiB']-self.previous_swap>65536 else 0
  self.previous_swap=r['swap_used_KiB']
  oom=r['oom_kill_count'] is not None and self.initial_oom is not None and r['oom_kill_count']>self.initial_oom
  if (W/'SIDE_STOP_R2').exists() or r['WSL_available_GiB']<1 or r['Windows_available_GiB']<1 or self.swap_growth_samples>=2 or oom:
   raise RuntimeError('SIDE_STUDY_RESOURCE_PRESSURE_STOP: cooperative own callback; preserve partial evidence; SAC untouched')
