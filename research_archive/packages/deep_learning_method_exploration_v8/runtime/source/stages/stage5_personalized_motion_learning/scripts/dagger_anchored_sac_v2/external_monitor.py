"""Lightweight read-only reuse of the existing monitor for the active campaign tree."""
from pathlib import Path
import sys,os,json,time,subprocess
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc');P=W/'dagger_anchored_sac_v2';L=P/'output';D=Path('/home/hank/ihear-lab/deep_learning_method_exploration_v8/runtime/source/stages/stage5_personalized_motion_learning/docs/dagger_anchored_sac_v2')
sys.dont_write_bytecode=True;sys.path.insert(0,str(W/'single_human_sac_memory'));import memory_test_v1 as m
roots=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  raw=(p/'cmdline').read_bytes();cmd=raw.replace(b'\0',b' ').decode(errors='replace');executable=raw.split(b'\0')[0].decode(errors='replace')
  if executable.endswith('/bin/python') and str(P/'train.py') in cmd:roots.append(int(p.name))
 except (FileNotFoundError,PermissionError,ProcessLookupError):pass
assert len(roots)==1,roots
original=m.os.getpid;m.os.getpid=lambda:roots[0]
try:proc=m.processes()
finally:m.os.getpid=original
mem=m.memfile('/proc/meminfo');win=m.windows();base=json.loads((L/'RESOURCE_BASE.json').read_text())['swap_bytes'];swap=mem['SwapTotal']-mem['SwapFree'];reasons=[]
if proc['other_heavy_python']:reasons.append('OTHER_HEAVY_PYTHON')
if win['ExternalVideoRender']:reasons.append('EXTERNAL_VIDEO_RENDER')
if mem['MemAvailable']<1.5*2**30:reasons.append('LOW_WSL_MEMORY')
if win['CommitLimit']-win['CommittedBytes']<2*2**30:reasons.append('LOW_COMMIT_HEADROOM')
if swap-base>128*2**20:reasons.append('NEW_SWAP_OVER_128_MIB')
gpu=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip();row=dict(unix=time.time(),tag='EXTERNAL_ACTIVE_TREE',campaign_pid=roots[0],processes=proc,wsl=mem,windows=win,swap_bytes=swap,gpu=gpu,reasons=reasons)
for folder in (L,D):
 with (folder/'RESOURCE_EXTERNAL.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
print(json.dumps(dict(safe=not reasons,reasons=reasons,main_PSS_MiB=proc['owned'][0]['Pss']/2**20,owned_processes=len(proc['owned']),available_GiB=mem['MemAvailable']/2**30,swap_MiB=swap/2**20,GPU=gpu,commit_headroom_GiB=(win['CommitLimit']-win['CommittedBytes'])/2**30)),flush=True)
