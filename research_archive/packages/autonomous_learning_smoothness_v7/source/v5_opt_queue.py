"""Finite authorized adaptive branch: frozen score selects start, then 2x12 trials + PPO check."""
from pathlib import Path
import os,sys,json,time,copy,datetime,subprocess,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1');sys.dont_write_bytecode=True
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'source'))
from optim_metrics_v1 import evaluate
from v5_search import objective
A=json.loads((P/'ACTIVATION.json').read_text());deadline=A['t0_unix']+7*3600;python=sys.executable
def put(n,d):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);tmp=f.with_suffix('.tmp');tmp.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n');tmp.replace(f)
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
put('owned/OPT_QUEUE_START.json',dict(pid=os.getpid(),utc=utc(),deadline_unix=deadline,finite_physics_budget=32,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),decision_rule='HANDOFF01 minimum original-qualified preregistered smoothness score; 12 own-data trials each PATTERN/BO, then fixed PPOCHECK; no other jobs generated'))
done=[];reason='FINITE_REGISTERED_BRANCH_COMPLETED'
try:
 for _ in range(max(1,int(deadline-time.time()))):
  f=P/'owned/HANDOFF01_SUPERVISOR_END.json'
  if f.exists():assert json.loads(f.read_text())['worker_exit_code']==0,'HANDOFF_BRANCH_FAILED';break
  if time.time()>deadline-7200 or (P/'STOP_REQUESTED').exists():raise TimeoutError('NO_TIME_FOR_COMPLETE_OPT_BRANCH')
  time.sleep(1)
 else:raise TimeoutError('HANDOFF_NOT_COMPLETED')
 base=json.loads((P/'experiments/HANDOFF01.json').read_text());strong=copy.deepcopy(next(r['action'] for r in base['actions'] if r['tag']=='BEST'));baseline=evaluate('HANDOFF01_BEST');rank=[]
 for f in (P/'attempts').glob('HANDOFF01_*_RESULT.json'):
  r=json.loads(f.read_text())
  if not r['qualified'] or r['action'].get('family')!='modal8_retimed':continue
  score,d=objective(r,baseline);rank.append(dict(id=r['id'],score=score,action=r['action'],JF=r['JF'],JM=r['JM']))
 assert rank,'NO_QUALIFIED_LEGAL_OPT_START';best=min(rank,key=lambda r:r['score'])
 cfg=copy.deepcopy(base);cfg.update(group='OPT01',worker='v5_opt_wrench_worker.py',algorithm='v5_search',search_dimensions=[6,7,4,5],start_parameters=[best['action']['x'][k] for k in [6,7,4,5]],strong_action=strong,search_seed=2026102305,arm_budget=12,actions=[],job_wall_cap_s=14400,public_start_selection=dict(rule='min preregistered S over completed HANDOFF01 original-qualified modal actions',source=best['id'],source_score=best['score'],shared_history_cost=7,history_advantage_same_for_both_arms=True))
 cfg['condition']['name']='OPT01';put('experiments/OPT01.json',cfg);put('runtime/OPT01_TEST_PLAN.json',cfg);put('analysis/optimization/START_SELECTION.json',dict(utc=utc(),rank=rank,selected=best,fixed_budget_per_arm=12,fixed_budget_checkpoints=[4,8,12],additional_improvement_target_score=.98*best['score']))
 with (P/'RESEARCH_DECISIONS.jsonl').open('a') as f:f.write(json.dumps(dict(utc=utc(),hypothesis='After execution-aware slow passing improves actual motion, traditional upper-level search may improve the motion/force/JF/JM tradeoff within the same legal four-coordinate domain.',experiment='OPT01: PATTERN vs GP BO, 12 true trials each, 4/8/12 checkpoints; common Handoff-derived start selection',result='FROZEN_BEFORE_OPT_START',diagnosis='Fit and proxy queries are not physical trials. Each arm sees only its own optimization outcomes; public historical start identical.',decision='Execute finite optimization then frozen PPO and PPO+rule comparison; no adaptive extension of fixed comparison.',evidence=['experiments/OPT01.json','analysis/optimization/START_SELECTION.json']),ensure_ascii=False)+'\n')
 for name in ['OPT01','PPOCHECK']:
  assert time.time()<deadline-900 and not (P/'STOP_REQUESTED').exists(),'QUEUE_DEADLINE_OR_STOP'
  with (P/'logs'/(name+'_adaptive_supervisor.log')).open('w') as log:
   p=subprocess.Popen([python,'-B',str(P/'source/supervise_v2.py'),'experiments/'+name+'.json'],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
   put('owned/OPT_QUEUE_CURRENT.json',dict(pid=p.pid,group=name,deadline_unix=deadline));rc=p.wait(timeout=max(1,int(deadline-time.time())))
  done.append(dict(group=name,exit_code=rc));assert rc==0,'REGISTERED_JOB_FAILED:'+name
except BaseException as e:reason=type(e).__name__+':'+str(e);raise
finally:put('owned/OPT_QUEUE_END.json',dict(pid=os.getpid(),utc=utc(),reason=reason,completed=done))
