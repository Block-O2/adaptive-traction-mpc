"""Durable 45s resource observation, 5/10/20m backoff, no unrelated kills."""
from pathlib import Path
import json,time,os
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
def save(p,x):
 temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(x,indent=2)+'\n');temp.replace(p)
def critical(row,prior=None):
 return row['mem_available']<.35*2**30 or row['windows'].get('commit_headroom',2**40)<.35*2**30 or (prior is not None and row['oom_kill']>prior['oom_kill'])
def pressure(history):
 return len(history)>=4 and history[-1]['unix']-history[-4]['unix']>=120 and all(r['mem_available']<1.25*2**30 for r in history[-4:]) and history[-1]['swap_in']+history[-1]['swap_out']-history[-4]['swap_in']-history[-4]['swap_out']>4096
def footprint():
 total=0
 for root,dirs,files in os.walk(S,followlinks=False):
  dirs[:]=[name for name in dirs if not (Path(root)/name).is_symlink()]
  for name in files:
   p=Path(root)/name
   if not p.is_symlink():total+=p.stat().st_size
 return total
def healthy(row):
 return row['mem_available']>=1.25*2**30 and row['windows'].get('commit_headroom',0)>=1.25*2**30
def before_dispatch(plan,sample):
 state_path=S/'RESOURCE_STATE.json';state=json.loads(state_path.read_text()) if state_path.exists() else {'status':'HEALTHY'}
 if state.get('status')=='HEAVY_CLOSEOUT_RESOURCE_UNRECOVERED':raise RuntimeError('RESOURCE_UNRECOVERED_60_MINUTES_LATCHED_CLOSEOUT')
 row=sample(owner='RESOURCE_DISPATCH_GUARD')
 data=footprint();save(S/'DATA_BUDGET_CURRENT.json',dict(unix=time.time(),bytes=data,target_bytes=plan['bytes_target'],old_symlink_targets_not_counted=True,linux_disk_free=row['disk_free'],windows_disk_c=row['windows'].get('disk_c')))
 if data>plan['bytes_target'] or row['disk_free']<2**30 or row['windows'].get('disk_c',2**40)<2**30:raise RuntimeError('DATA_OR_CHECKPOINT_DISK_RESERVE_CLOSEOUT')
 if critical(row) and state.get('status')!='PAUSE_DISPATCH':state=dict(status='PAUSE_DISPATCH',since=time.time(),level=0,next_check_unix=time.time()+300,healthy_samples=0,row=row);save(state_path,state)
 if state.get('status')!='PAUSE_DISPATCH':return row
 state.setdefault('level',0);state.setdefault('next_check_unix',state['since']+300);state.setdefault('healthy_samples',0)
 while True:
  now=time.time()
  if now>=plan['dispatch_cutoff_unix']:raise RuntimeError('DISPATCH_CUTOFF_DURING_RESOURCE_BACKOFF')
  if now-state['since']>=3600:save(state_path,state|dict(status='HEAVY_CLOSEOUT_RESOURCE_UNRECOVERED'));raise RuntimeError('RESOURCE_UNRECOVERED_60_MINUTES')
  state['healthy_samples']=state['healthy_samples']+1 if healthy(row) else 0
  if state['healthy_samples']>=4 and now>=state['next_check_unix']:
   save(state_path,dict(status='HEALTHY',unix=now,healthy_samples=state['healthy_samples'],previous_pause_since=state['since']));return row
  if now>=state['next_check_unix']:
   state['level']=min(2,state['level']+1);state['next_check_unix']=now+[300,600,1200][state['level']]
  state.update(row=row,updated_unix=now);save(state_path,state)
  print('RESOURCE_BACKOFF',json.dumps({k:state[k] for k in ('since','level','next_check_unix','healthy_samples')}),flush=True)
  time.sleep(45);row=sample(owner='RESOURCE_BACKOFF')
