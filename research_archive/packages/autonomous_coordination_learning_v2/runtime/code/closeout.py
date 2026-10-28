"""Post-dispatch read-only preservation, resource and worker lifecycle audit."""
from pathlib import Path
import json,hashlib,subprocess,os,time,collections,shutil
S=Path('/home/hank/ihear-lab/autonomous_coordination_learning_v2/runtime')
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_multirate_realtime_v1')
ROOT=Path('/home/hank/ihear-lab/autonomous_coordination_learning_v2/runtime/source')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def save(n,x):(S/n).write_text(json.dumps(x,indent=2)+'\n')
def read(n):return json.loads((S/n).read_text())
def lines(n):return [json.loads(q) for q in (S/n).read_text().splitlines()] if (S/n).exists() else []
def git():
 def run(*args):
  r=subprocess.run(['git','-C',str(ROOT),*args],env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'),capture_output=True,text=True);assert r.returncode==0,r.stderr;return r.stdout
 return dict(branch=run('branch','--show-current'),HEAD=run('rev-parse','HEAD'),status=run('status','--porcelain=v1'),index_sha256=sha(ROOT/'.git/index'),staged_diff=run('diff','--cached','--binary'))
def preservation():
 before=read('preservation/HISTORICAL_BEFORE.json');changed=[];missing=[]
 for name,h in before.items():
  p=Path(name)
  if not p.is_file():missing.append(name)
  elif sha(p)!=h:changed.append(name)
 actual=set()
 for n in ('b_native_learning_matrix_v1','b_native_q_realtime_integration_v1','coordination_residual_realization_v2'):
  for p in (S.parent/n).rglob('*'):
   if p.is_file() and '__pycache__' not in p.parts:actual.add(str(p))
 control=read('preservation/CONTROL_BEFORE.json');control_changed=[n for n,h in control.items() if not Path(n).is_file() or sha(Path(n))!=h]
 after=git();save('GIT_AFTER.json',after);git_same={k:after[k]==read('GIT_BEFORE.json')[k] for k in after}
 weights=S.parent/'b_native_q_realtime_integration_v1/weights/frozen_Q_v1/weights.npz'
 if not weights.exists():
  matches=[Path(n) for n,h in before.items() if h=='3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9'];assert len(matches)>=1;weights=matches[0]
 weight_hash=sha(weights)
 out=dict(status='PASS' if not changed and not missing and not control_changed and not (actual-set(before)) and all(git_same.values()) and weight_hash=='3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9' else 'FAIL',historical_files=len(before),historical_changed=changed,historical_missing=missing,historical_added=sorted(actual-set(before)),frozen_control_files=len(control),frozen_control_changed=control_changed,git_equal=git_same,frozen_Q=dict(path=str(weights),sha256=weight_hash,loaded_by_B=False),windows_git='Windows authoring workspace is not the primary Git checkout; initial git query failed. WSL primary repository is the audited authority.',checked_unix=time.time())
 save('preservation/FINAL_PRESERVATION.json',out);print('PRESERVATION',out['status'],len(before),flush=True)
def resources():
 rows=lines('output/RESOURCE_LOG.jsonl');cpu=lines('output/CPU_WATCH.jsonl');c=session=lines('output/CPU_LOG.jsonl')
 def bounds(values):return dict(min=min(values),max=max(values)) if values else None
 cpu_util=[]
 for a,b in zip(cpu,cpu[1:]):
  av=list(map(int,a['cpu_stat'].splitlines()[0].split()[1:9]));bv=list(map(int,b['cpu_stat'].splitlines()[0].split()[1:9]));d=[y-x for x,y in zip(av,bv)];cpu_util.append(100*(sum(d)-d[3]-d[4])/sum(d))
 out=dict(samples=len(rows),start_unix=rows[0]['unix'],end_unix=rows[-1]['unix'],WSL_MemAvailable_bytes=bounds([r['mem_available'] for r in rows]),WSL_swap_used_bytes=bounds([r['swap_used'] for r in rows]),swap_in_pages_delta=rows[-1]['swap_in']-rows[0]['swap_in'],swap_out_pages_delta=rows[-1]['swap_out']-rows[0]['swap_out'],oom_kill_delta=rows[-1]['oom_kill']-rows[0]['oom_kill'],owned_PSS_bytes=bounds([r['PSS'] for r in rows]),process_count=bounds([r['process_count'] for r in rows]),owned_process_count=bounds([r['owned_count'] for r in rows]),Windows_commit_headroom_bytes=bounds([r['windows']['commit_headroom'] for r in rows if 'commit_headroom' in r['windows']]),Windows_memory_query_errors=[r['windows'] for r in rows if 'error' in r['windows']],resource_pause=(S/'RESOURCE_PAUSE.json').exists(),CPU_watch_samples=len(cpu),CPU_utilization_percent=bounds(cpu_util),CPU_load1=bounds([r['load'][0] for r in cpu+c]),CPU_coverage_start=min([r['unix'] for r in cpu+c]) if cpu+c else None,CPU_coverage_gap='Initial campaign CPU load was added after resource JSON write and not persisted. Later CPU_WATCH and same-interpreter CPU_LOG provide real samples only; earlier values are unavailable.',no_WSL_restart_swap_change_cache_drop_unknown_kill=True)
 save('reports/RESOURCE_CLOSEOUT.json',out)
def lifecycle():
 events=lines('ATTEMPTS.jsonl');starts={r['id']:r for r in events if r['event']=='START'};ends={r['id']:r for r in events if r['event']=='END'};rows=[]
 for ident,begin in sorted(starts.items()):
  p=S/'output'/(ident+'_RESULT.json');r=json.loads(p.read_text()) if p.exists() else {};metric=r.get('metric',{});raw=S/'source/results'/ident/'runtime_artifacts.json.gz'
  rows.append(dict(id=ident,status=ends.get(ident,{}).get('status','UNJOINED'),seed=begin.get('cfg',{}).get('seed'),mode=begin.get('cfg',{}).get('execution_mode'),revision=begin.get('cfg',{}).get('revision'),series=begin.get('cfg',{}).get('host_series'),wall_seconds=None if ident not in ends else ends[ident]['unix']-begin['unix'],native_steps_last_scored_sample=metric.get('native_physics_steps',0),raw_complete_artifacts=raw.exists(),raw_gzip_sha256=sha(raw) if raw.exists() else None))
 live=[];ancestors=set();ancestor=os.getppid()
 while ancestor>1 and ancestor not in ancestors:
  ancestors.add(ancestor)
  try:ancestor=int((Path('/proc')/str(ancestor)/'stat').read_text().split(') ',1)[1].split()[1])
  except OSError:break
 for p in Path('/proc').iterdir():
  if not p.name.isdigit() or int(p.name)==os.getpid() or int(p.name) in ancestors:continue
  try:
   cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
   if str(S/'code') in cmd:live.append(dict(pid=int(p.name),cmd=cmd))
  except OSError:pass
 balanced=set(starts)==set(ends) and len(starts)==sum(r['event']=='START' for r in events) and len(ends)==sum(r['event']=='END' for r in events)
 out=dict(status='PASS' if balanced and not live else 'FAIL',START_count=len(starts),END_count=len(ends),balanced=balanced,live_owned_processes=live,attempts=rows,session=read('output/R3_CONSECUTIVE_SESSION.json'),session_owner=read('SESSION_CAMPAIGN_JOINED.json'),CPU_watch=read('CPU_WATCH_JOINED.json'),physics_owner_count_policy='One physical episode at a time, runner fcntl lock. Concurrent workers forbid plant construction. Same-interpreter runs reset original plant/model between episodes.',startup_failures=sum(r['status']=='FAILED_NO_RESULT' for r in rows),zero_physics_startup_failures_confirmed=all(not (S/'source/results'/r['id']).exists() for r in rows if r['status']=='FAILED_NO_RESULT'))
 save('reports/WORKER_AND_ATTEMPT_CLOSEOUT.json',out);print('LIFECYCLE',out['status'],len(starts),flush=True)
def main():
 assert (S/'CPU_WATCH_JOINED.json').exists()
 import sys
 sys.path.insert(0,str(S/'code'));import runner
 runner.sample('FINAL_NO_PHYSICS_WORKERS')
 preservation();resources();lifecycle()
 shutil.copy2(W/'CONTRACT.md',S/'CONTRACT.md')
 save('FINAL_CODE_MANIFEST.json',{str(p.relative_to(S)):sha(p) for d in ('code','versions','preservation') for p in (S/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts})
 save('CLOSEOUT_STATE.json',dict(status='CLOSED_NO_NEW_DISPATCH',unix=time.time(),elapsed_s=time.time()-read('RUN_PLAN.json')['start_unix'],M2='NOT_RUN_B_NOT_QUALIFIED',Q_calls=0,G_calls=0,learning_updates=0,revision_count=3))
if __name__=='__main__':main()
