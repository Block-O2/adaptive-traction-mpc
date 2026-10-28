"""Finite locked validation after all development: freeze choices, then four new legal prefixes."""
from pathlib import Path
import os,sys,json,time,copy,hashlib,datetime,subprocess
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1');sys.dont_write_bytecode=True
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'source'))
from v5_search import objective
from optim_metrics_v1 import evaluate
A=json.loads((P/'ACTIVATION.json').read_text());deadline=A['hard_stop_unix']-2700;python=sys.executable
def put(n,x):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);tmp=f.with_suffix('.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');tmp.replace(f)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def wait_json(rel):
 for _ in range(max(1,int(deadline-time.time())+1)):
  if time.time()>=deadline or (P/'STOP_REQUESTED').exists():raise TimeoutError('VALIDATION_DEADLINE_WAIT:'+rel)
  f=P/rel
  if f.exists():
   try:return json.loads(f.read_text())
   except json.JSONDecodeError:pass
  time.sleep(1)
 raise TimeoutError('MISSING:'+rel)
put('owned/VALIDATION3_QUEUE_START.json',dict(pid=os.getpid(),utc=utc(),deadline_unix=deadline,maximum_validation_attempts=40,conditions_file='experiments/LOCKED_VALIDATION_INPUTS.json',conditions_sha256=sha(P/'experiments/LOCKED_VALIDATION_INPUTS.json'),no_new_conditions_or_algorithms_generated=True))
completed=[];reason='FINITE_LOCKED_VALIDATION_COMPLETED'
try:
 optend=wait_json('owned/OPT2_QUEUE_END.json');assert optend['reason']=='FINITE_REGISTERED_BRANCH_COMPLETED','OPT_DEVELOPMENT_NOT_CLOSED'
 branchend=wait_json('owned/BRANCH02_SUPERVISOR_END.json');assert branchend['worker_exit_code']==0,'BRANCH_STRESS_FAILED'
 criticend=wait_json('owned/CRITIC_QUEUE_END.json');assert criticend['reason'] in ['FINITE_CONDITIONAL_STUDY_COMPLETED','NO_TRUE_MYOPIA_TRIGGER_CRITIC_NOT_RUN'],'CRITIC_STUDY_REQUIRES_REVIEW'
 from v5_phase_composition import prepare as prepare_composition
 compose=prepare_composition()
 if compose:
  assert time.time()<deadline-5400,'NO_TIME_FOR_EXTRA_COMPOSITION_AND_LOCKED_VALIDATION'
  with (P/'logs/COMPOSE01_adaptive_supervisor.log').open('w') as log:
   child=subprocess.Popen([python,'-B',str(P/'source/supervise_v2.py'),'experiments/COMPOSE01.json'],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
   put('owned/VALIDATION3_QUEUE_CURRENT.json',dict(pid=child.pid,group='COMPOSE01',deadline_unix=deadline));rc=child.wait(timeout=max(1,int(deadline-time.time())))
  assert rc==0,'ADAPTIVE_COMPOSITION_FAILED'
 allrows=[json.loads(f.read_text()) for f in (P/'attempts').glob('*_RESULT.json')];by={r['id']:r for r in allrows};base=json.loads((P/'experiments/CORE01.json').read_text());strong=by['CORE01_BEST']['action'];baseline=evaluate('CORE01_BEST');selected={}
 def choose(label,ids,fallback=None):
  use=[by[i] for i in ids if i in by and by[i]['qualified']]
  if use:
   ranked=[(objective(r,baseline)[0],r) for r in use];score,r=min(ranked,key=lambda z:z[0]);selected[label]=dict(development_id=r['id'],score=score,action=r['action'],fallback=False)
  elif fallback is not None:selected[label]=dict(development_id='NO_QUALIFIED_'+label,score=None,action=copy.deepcopy(fallback),fallback=True)
 choose('HANDOFF',[r['id'] for r in allrows if r['id'].startswith('HANDOFF01_') and r['action'].get('family')=='modal8_retimed'])
 choose('REFERENCE',[r['id'] for r in allrows if r['id'].startswith('STRICT01_REF')])
 choose('ANTICIPATORY',['STRICT01_ANT'],strong)
 for label,arm in [('PATTERN','PATTERN'),('BO','BO')]:
  data=json.loads((P/f'analysis/optimization/OPT01_{arm}.json').read_text());assert data['completed']==12,'FIXED_OPT_BUDGET_NOT_COMPLETED';choose(label,[r['id'] for r in data['rows']],strong)
 choose('COMPOSE',[r['id'] for r in allrows if r['id'].startswith('COMPOSE01_') and r['action'].get('family')=='modal8_retimed'])
 assert 'HANDOFF' in selected,'NO_LEGAL_HANDOFF_CANDIDATE'
 ppo={r['tag']:r['action'] for r in json.loads((P/'experiments/PPOCHECK.json').read_text())['actions']}
 inputs=json.loads((P/'experiments/LOCKED_VALIDATION_INPUTS.json').read_text());frozen=utc();configs=[]
 for idx,condition in enumerate(inputs['conditions'],1):
  group=condition['name'];cfg=copy.deepcopy(base);cfg.update(group=group,mode='validation',worker='v5_bounded_worker.py',actions=[],job_wall_cap_s=7200,local_stop_unix=A['hard_stop_unix']-3600);cfg['condition']=condition
  cfg['actions']=[dict(tag='B',action={'family':'B'},category='locked_validation'),dict(tag='BEST',action=copy.deepcopy(strong),category='locked_validation')]
  for label in ['HANDOFF','REFERENCE','ANTICIPATORY','PATTERN','BO','COMPOSE']:
   if label in selected:cfg['actions'].append(dict(tag=label,action=copy.deepcopy(selected[label]['action']),category='locked_validation',selected_development_id=selected[label]['development_id']))
  if idx in [1,3]:
   cfg['actions'] += [dict(tag='PPO_MEAN',action=copy.deepcopy(ppo['FROZEN_MEAN']),category='locked_frozen_PPO'),dict(tag='PPO_RULE',action=copy.deepcopy(ppo['FROZEN_PLUS_RULE']),category='locked_frozen_PPO_plus_rule')]
  # Identical frozen controller actions share one actual validation; aliases are not extra trials.
  requested_labels=[r['tag'] for r in cfg['actions']];unique=[];seen={};aliases={}
  for entry in cfg['actions']:
   key=json.dumps(entry['action'],sort_keys=True,separators=(',',':'))
   if key not in seen:seen[key]=entry['tag'];unique.append(entry)
   aliases[entry['tag']]=seen[key]
  cfg['actions']=unique;cfg['validation_method_aliases']=aliases;cfg['requested_method_labels']=requested_labels
  put(f'experiments/{group}.json',cfg);put(f'runtime/{group}_TEST_PLAN.json',cfg);configs.append(dict(group=group,config_sha256=sha(P/f'experiments/{group}.json'),actions=[r['tag'] for r in cfg['actions']],method_aliases=aliases,requested_method_labels=requested_labels,condition=condition,attempt_cap=len(cfg['actions'])+1))
 put('analysis/LOCKED_VALIDATION_SELECTION.json',dict(frozen_utc=frozen,frozen_unix=time.time(),selected=selected,configs=configs,total_attempt_cap=sum(r['attempt_cap'] for r in configs),conditions_frozen_utc=inputs['frozen_utc'],selection_rule='min original-qualified preregistered S within each named development method; explicit strong fallback if no qualified optimizer/anticipatory candidate; no validation feedback',all_configs_locked_before_first_new_prefix_START=True,same_Human_not_cross_patient=True,exact_action_aliases_share_one_actual_trial=True,no_alias_is_counted_as_a_new_physical_attempt=True))
 with (P/'RESEARCH_DECISIONS.jsonl').open('a') as f:f.write(json.dumps(dict(utc=utc(),hypothesis='Development motion/wrench gains and force/moment tradeoffs may or may not persist at independently frozen legal prefixes.',experiment='VAL01..VAL04, fixed source/config/candidates before first new-prefix START',result='FROZEN_BEFORE_VALIDATION',diagnosis='No qualification filters or action changes based on validation feedback; same nominal Human, not cross-patient.',decision='Execute finite locked tests, retain every failure/partial, then independent raw/scorer/source/ownership audit and STOP.',evidence=['analysis/LOCKED_VALIDATION_SELECTION.json','experiments/LOCKED_VALIDATION_INPUTS.json']),ensure_ascii=False)+'\n')
 for item in configs:
  group=item['group'];assert time.time()<deadline-1800 and not (P/'STOP_REQUESTED').exists(),'INSUFFICIENT_COMPLETE_VALIDATION_AND_AUDIT_TIME'
  with (P/'logs'/(group+'_locked_supervisor.log')).open('w') as log:
   child=subprocess.Popen([python,'-B',str(P/'source/supervise_v2.py'),'experiments/'+group+'.json'],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
   put('owned/VALIDATION3_QUEUE_CURRENT.json',dict(pid=child.pid,group=group,deadline_unix=deadline));rc=child.wait(timeout=max(1,int(deadline-time.time())))
  assert rc==0,'LOCKED_VALIDATION_JOB_FAILED:'+group;completed.append(group)
 put('queue/READY_FOR_FINAL_AUDIT.json',dict(utc=utc(),all_locked_groups_completed=completed,required_next='Stop analysis services after final raw/scorer catch-up; independent receipt/native/source/history audits, journal end and END seal; no next research round.'))
except BaseException as error:reason=type(error).__name__+':'+str(error);raise
finally:put('owned/VALIDATION3_QUEUE_END.json',dict(pid=os.getpid(),utc=utc(),reason=reason,completed=completed))
