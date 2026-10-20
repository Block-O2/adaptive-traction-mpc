"""Fake-clock bounded resource recovery; no real waits or resources altered."""
from pathlib import Path
import sys,json,tempfile,types
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
import resource_guard as g
GiB=2**30;checks=[]
def row(t=0,available=3*GiB,commit=3*GiB,swap=0,oom=0,disk=8*GiB):
 return dict(unix=t,mem_available=available,windows=dict(commit_headroom=commit,disk_c=disk),swap_in=swap,swap_out=0,oom_kill=oom,disk_free=disk)
assert not g.critical(row(available=.36*GiB));assert g.critical(row(available=.34*GiB));assert g.critical(row(commit=.34*GiB));assert g.critical(row(oom=1),row());checks.append('critical RAM, Windows commit and OOM increase')
assert not g.pressure([row(i*45,available=GiB,swap=100) for i in range(4)])
assert g.pressure([row(i*45,available=GiB,swap=i*2000) for i in range(4)])
assert not g.pressure([row(i*20,available=GiB,swap=i*2000) for i in range(4)]);checks.append('stable swap and cold spike versus sustained low RAM plus swap IO')
original=(g.S,g.time,g.footprint)
with tempfile.TemporaryDirectory(prefix='fast_guard_regression_') as temp:
 g.S=Path(temp);now=[0.];g.time=types.SimpleNamespace(time=lambda:now[0],sleep=lambda dt:now.__setitem__(0,now[0]+dt));g.footprint=lambda:0
 plan=dict(bytes_target=10*GiB,dispatch_cutoff_unix=10000)
 g.save(g.S/'RESOURCE_STATE.json',dict(status='PAUSE_DISPATCH',since=0,level=0,next_check_unix=300,healthy_samples=0))
 g.before_dispatch(plan,lambda **kw:row(now[0]));assert now[0]==315;assert json.loads((g.S/'RESOURCE_STATE.json').read_text())['status']=='HEALTHY';checks.append('four healthy samples plus minimum five-minute backoff')
 now[0]=0;g.save(g.S/'RESOURCE_STATE.json',dict(status='PAUSE_DISPATCH',since=0,level=0,next_check_unix=300,healthy_samples=0))
 try:g.before_dispatch(plan,lambda **kw:row(now[0],available=GiB,commit=GiB))
 except RuntimeError as e:assert str(e)=='RESOURCE_UNRECOVERED_60_MINUTES'
 else:raise AssertionError('missing closeout')
 state=json.loads((g.S/'RESOURCE_STATE.json').read_text());assert now[0]==3600 and state['status']=='HEAVY_CLOSEOUT_RESOURCE_UNRECOVERED' and state['level']==2;checks.append('5/10/20-minute escalation and sixty-minute bounded closeout')
 try:g.before_dispatch(plan,lambda **kw:row(now[0]))
 except RuntimeError as e:assert str(e)=='RESOURCE_UNRECOVERED_60_MINUTES_LATCHED_CLOSEOUT'
 else:raise AssertionError('closeout was not latched')
 checks.append('sixty-minute heavy closeout remains latched even if memory later recovers')
 now[0]=0;g.save(g.S/'RESOURCE_STATE.json',dict(status='PAUSE_DISPATCH',since=0,level=0,next_check_unix=300,healthy_samples=0))
 try:g.before_dispatch(plan|dict(dispatch_cutoff_unix=90),lambda **kw:row(now[0],available=GiB))
 except RuntimeError as e:assert str(e)=='DISPATCH_CUTOFF_DURING_RESOURCE_BACKOFF'
 else:raise AssertionError('missing deadline')
 checks.append('immutable dispatch cutoff takes precedence during recovery')
 g.save(g.S/'RESOURCE_STATE.json',dict(status='HEALTHY'))
 try:g.before_dispatch(plan,lambda **kw:row(disk=GiB-1))
 except RuntimeError as e:assert str(e)=='DATA_OR_CHECKPOINT_DISK_RESERVE_CLOSEOUT'
 else:raise AssertionError('missing reserve guard')
 checks.append('checkpoint disk reserve')
g.S,g.time,g.footprint=original
out=dict(status='PASS',checks=checks,physical_native_steps=0,real_wait_seconds=0,real_resource_state_unchanged=True)
g.save(S/'output/RESOURCE_GUARD_V2_LOCAL_REGRESSION.json',out);print(json.dumps(out))
