"""Finite conditional critic study; requires completed real myopia gate and frozen test inputs."""
from pathlib import Path
import os,sys,json,time,copy,subprocess,datetime,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1');sys.dont_write_bytecode=True
P=Path(__file__).resolve().parents[1];A=json.loads((P/'ACTIVATION.json').read_text());deadline=A['t0_unix']+6.8*3600;python=sys.executable
def put(n,x):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);tmp=f.with_suffix('.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');tmp.replace(f)
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def wait_json(rel,max_wait_s=None):
 limit=min(deadline,time.time()+max_wait_s) if max_wait_s else deadline
 for _ in range(max(1,int(limit-time.time())+1)):
  if time.time()>limit or (P/'STOP_REQUESTED').exists():raise TimeoutError('WAIT_LIMIT:'+rel)
  p=P/rel
  if p.exists():
   try:return json.loads(p.read_text())
   except json.JSONDecodeError:pass
  time.sleep(1)
 raise TimeoutError('NO_COMPLETE_JSON:'+rel)
def job(group):
 assert time.time()<deadline-600,'NO_TIME_FOR_BOUNDED_JOB'
 with (P/'logs'/(group+'_critic_supervisor.log')).open('w') as log:
  p=subprocess.Popen([python,'-B',str(P/'source/supervise_v2.py'),'experiments/'+group+'.json'],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
  put('owned/CRITIC_QUEUE_CURRENT.json',dict(pid=p.pid,group=group,deadline_unix=deadline));rc=p.wait(timeout=max(1,int(deadline-time.time())))
 assert rc==0,'CRITIC_STUDY_JOB_FAILED:'+group
 wait_json('models/'+group+'_TAIL_LABELS.json',120)
put('owned/CRITIC_QUEUE_START.json',dict(pid=os.getpid(),utc=utc(),deadline_unix=deadline,max_extra_physical_attempts=36,finite_job_pool=['TAILO2','TAILR2','TAILOT','TAILRT'],no_critic_fit_without_real_gate=True,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
reason='FINITE_CONDITIONAL_STUDY_COMPLETED';done=[]
try:
 gates={ph:wait_json('analysis/tail/'+g+'.json') for ph,g in [('OUTBOUND','TAILO1'),('RETURN','TAILR1')]};triggered={ph:g for ph,g in gates.items() if g['critic_gate_triggered']}
 decisions=[]
 for ph,g in gates.items():
  chosen=next((h for h in [.5,.25,1.] if any(r['trigger'] and abs(r['horizon_s']-h)<1e-9 for r in g['comparisons'])),None)
  decisions.append(dict(phase=ph,triggered=chosen is not None,selected_horizon_s=chosen,comparisons=g['comparisons'],rule='Prefer 0.5s, then0.25s, then1s among real trigger horizons; fixed before critic fit/test'))
 put('analysis/CRITIC_GATE_DECISION.json',dict(utc=utc(),decisions=decisions,train_authorized=bool(triggered),source='completed full registered single-decision real rolling menus, original-qualified candidates'))
 if not triggered:reason='NO_TRUE_MYOPIA_TRIGGER_CRITIC_NOT_RUN';sys.exit(0)
 end=wait_json('owned/BRANCH02_SUPERVISOR_END.json');assert end['worker_exit_code']==0,'PRIOR_PHYSICAL_BRANCH_FAILED'
 assert time.time()<deadline-5400,'INSUFFICIENT_TIME_FOR_TRAIN_AND_LOCKED_TEST'
 configs=[]
 for dec in decisions:
  if not dec['triggered']:continue
  phase=dec['phase'];prefix='O' if phase=='OUTBOUND' else 'R';g1='TAIL'+prefix+'1';g2='TAIL'+prefix+'2';gt='TAIL'+prefix+'T'
  configs.append(dict(id='COST'+prefix,gate_groups=[g1],train_groups=[g1,g2],test_groups=[gt],phases=[phase],horizon_s=dec['selected_horizon_s'],continuation='original B rolling/replan',gamma=1.,selection_and_eligibility='offline conditional diagnostic, actual future qualification shared and explicitly disclosed; no real-time/savings claim'))
  job(g2);done.append(g2)
 for cfg in configs:
  path='experiments/CRITIC_'+cfg['id']+'.json';put(path,cfg)
  with (P/'logs'/('CRITIC_'+cfg['id']+'_FIT.log')).open('w') as log:
   rc=subprocess.run([python,'-B',str(P/'source/v5_cost_critic.py'),path,'fit_only'],stdout=log,stderr=subprocess.STDOUT,timeout=300).returncode
  assert rc==0,'COMPONENT_CRITIC_FIT_FAILED';done.append(cfg['id']+'_FROZEN')
 for cfg in configs:
  job(cfg['test_groups'][0]);done.append(cfg['test_groups'][0]);path='experiments/CRITIC_'+cfg['id']+'.json'
  with (P/'logs'/('CRITIC_'+cfg['id']+'_TEST.log')).open('w') as log:
   rc=subprocess.run([python,'-B',str(P/'source/v5_cost_critic.py'),path,'evaluate_only'],stdout=log,stderr=subprocess.STDOUT,timeout=300).returncode
  assert rc==0,'FROZEN_COMPONENT_CRITIC_TEST_FAILED';done.append(cfg['id']+'_TESTED')
except BaseException as e:
 if not isinstance(e,SystemExit) or e.code not in (0,None):reason=type(e).__name__+':'+str(e)
 raise
finally:put('owned/CRITIC_QUEUE_END.json',dict(pid=os.getpid(),utc=utc(),reason=reason,completed=done))
