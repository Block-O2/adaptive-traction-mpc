from pathlib import Path
import ast, os, sys, json, time, subprocess, signal, fcntl, shutil, traceback
S=Path('/home/hank/ihear-lab/autonomous_coordination_learning_v2/runtime')
def load(n):return json.loads((S/n).read_text())
def put(n,x):
 p=S/n;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');t.replace(p)
def records():return [json.loads(l) for l in (S/'ATTEMPTS.jsonl').read_text().splitlines()]
def processes():
 matches=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit() or int(p.name)==os.getpid():continue
  try:
   cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
   if str(S)+'/code/' in cmd:matches.append(dict(pid=int(p.name),cmd=cmd))
  except (FileNotFoundError,PermissionError):pass
 return matches
lock=(S/'OWNER.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not processes(),'PREVIOUS_OWNED_PROCESS_STILL_ALIVE'
P=load('SEARCH_PROTOCOL.json');assert load('PIPELINE_ERROR.json')['error']=='OWNED_BATCH_TIMEOUT:reexplore3'
assert time.time()+3600<P['dispatch_cutoff_unix'],'NO_TIME_FOR_VALIDATION'
archive=S/'preservation/search_timeout';archive.mkdir(exist_ok=True)
for n in ['OWNER.json','OWNER_EXITED.json','PROGRESS.json','PACKAGE_VERIFICATION.json','FINALIZED.json','REPORT.md','PROFESSOR_BRIEF.md']:
 if (S/n).exists():shutil.copy2(S/n,archive/n)
ended={r['id'] for r in records() if r['event'] in ['END','FAIL','INTERRUPTED']}
missing=[r['id'] for r in records() if r['event']=='START' and r['id'] not in ended]
with (S/'ATTEMPTS.jsonl').open('a') as f:
 for ident in missing:f.write(json.dumps(dict(unix=time.time(),event='INTERRUPTED',id=ident,reason='OWNED_BATCH_TIMEOUT:reexplore3',evidence='pipeline worker JOIN plus /proc confirms entire owned group absent',full_task=False,actual_final_native_steps_unknown=True))+'\n')
put('VALIDATION_CONTINUATION_REGISTERED.json',dict(unix=time.time(),reason='skip remainder of timed-out search; execute already registered independent verification and V conditions',previous_owner_exit=load('OWNER_EXITED.json'),processes_absent=True,original_t0=P['t0_unix'],attempts_not_reset=True,no_wrapper_controller_or_threshold_change=True,third_wrapper_repair=False,remaining_search_skipped=True))
# Execute the exact previously registered selector, excluding its module-level main call.
sys.path.insert(0,str(S/'code'))
tree=ast.parse((S/'code/pipeline.py').read_text());assert isinstance(tree.body[-1],ast.Try);tree.body=tree.body[:-1]
ns={'__name__':'registered_selection_only'};exec(compile(tree,'registered_pipeline_definitions','exec'),ns)
assert not (S/'FROZEN_SELECTION.json').exists(),'SELECTION_ALREADY_EXISTS'
frozen=ns['choose_frozen']()
print(json.dumps(dict(frozen=[c['id'] for c in frozen['candidates']],attempts=sum(r['event']=='START' for r in records()))),flush=True)
def run(mode):
 assert not processes();assert time.time()+900<P['dispatch_cutoff_unix'];assert sum(r['event']=='START' for r in records())+len(frozen['candidates'])+3<=300
 with (S/'logs'/('validation_only_'+mode+'.log')).open('a') as log:
  p=subprocess.Popen([sys.executable,str(S/'code/worker.py'),mode],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
  put('OWNER.json',dict(pid=os.getpid(),active_pid=p.pid,active_pgid=p.pid,phase=mode,status='RUNNING',unix=time.time(),validation_only=True))
  try:rc=p.wait(timeout=min(1800,P['dispatch_cutoff_unix']-time.time()-600))
  except subprocess.TimeoutExpired:
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
   raise RuntimeError('VALIDATION_BATCH_TIMEOUT:'+mode)
  put('OWNER.json',dict(pid=os.getpid(),active_pid=None,phase=mode,status='JOINED',unix=time.time(),returncode=rc,validation_only=True))
  assert rc==0,'VALIDATION_FAILURE:'+mode
 print(json.dumps(dict(validation_phase_complete=mode,attempts=sum(r['event']=='START' for r in records()))),flush=True)
try:
 run('verify')
 for condition in P['validation_conditions']:run(condition['name'])
 put('VALIDATION_DONE.json',dict(unix=time.time(),candidate_parameters_unchanged_after_freeze=True,search_timeout_preserved=True,no_further_physics=True))
except BaseException as e:
 put('VALIDATION_CONTINUATION_ERROR.json',dict(unix=time.time(),error=str(e),traceback=traceback.format_exc(),no_new_dispatch=True))
finally:
 with (S/'logs/validation_only_finalize.log').open('a') as log:
  p=subprocess.Popen([sys.executable,str(S/'code/finalize.py')],stdout=log,stderr=subprocess.STDOUT)
  rc=p.wait(timeout=600)
 put('OWNER_EXITED.json',dict(pid=os.getpid(),unix=time.time(),elapsed_s=time.time()-P['t0_unix'],owned_workers_joined=not processes(),status='STOPPED',no_followup=True,validation_only=True,finalizer_returncode=rc))
 print(json.dumps(dict(validation_owner_exited=True,finalizer_returncode=rc)),flush=True)
