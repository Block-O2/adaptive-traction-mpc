"""Finite adaptive research workflow. One physics supervisor at a time, 40min closure reserve."""
from pathlib import Path
import os,sys,json,time,subprocess,hashlib,copy,traceback
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1');P=Path(__file__).resolve().parents[1];A=json.loads((P/'ACTIVATION.json').read_text());deadline=A['hard_stop_unix'];events=[]
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def put(n,x):f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def event(stage,**extra):
 row=dict(unix=time.time(),stage=stage,**extra);events.append(row);put('jobs/CAMPAIGN_PROGRESS.json',events);print('CAMPAIGN',stage,extra,flush=True)
def command(script,*args,timeout=900):
 with (P/'logs'/(Path(script).stem+'_'+str(int(time.time()))+'.log')).open('w') as f:
  rc=subprocess.run([sys.executable,'-B',str(P/'source'/script),*args],stdout=f,stderr=subprocess.STDOUT,env=dict(os.environ,ACL2_PACKAGE=str(P)),timeout=min(timeout,max(1,deadline-time.time()-2400))).returncode
 assert rc==0,script+' failed; inspect logs'
def job(c):
 g=c['group'];assert deadline-time.time()>2400+max(1000,len(c['actions'])*150),'NOT_ENOUGH_TIME_WITH_REVIEW_RESERVE'
 config='experiments/'+g+'.json';put(config,c);put('runtime/'+g+'_TEST_PLAN.json',dict(condition=c['condition'],arms=c['arms']))
 event('DISPATCH',group=g,config_sha256=sha(P/config))
 with (P/'logs'/(g+'_campaign_supervisor.log')).open('w') as f:
  rc=subprocess.run([sys.executable,'-B',str(P/'source/supervise_v2.py'),config],stdout=f,stderr=subprocess.STDOUT,timeout=max(1,deadline-time.time()-2400)).returncode
 event('PHYSICS_END',group=g,exit_code=rc)
 if rc:return False
 return True
def check_frozen_sources(model):
 for rel,h in model['source_sha256'].items():assert sha(P/rel)==h,'FROZEN_SOURCE_CHANGED:'+rel
start=time.time();put('owned/CAMPAIGN_DRIVER_V3_START.json',dict(pid=os.getpid(),started_unix=start,deadline_unix=deadline,source_sha256=sha(Path(__file__))))
try:
 groups=json.loads((P/'freeze/TRAIN_PLAN.json').read_text())['groups']
 while not (P/'jobs/COORD_QUEUE_DONE.json').exists() or not (P/'jobs/TRAIN_DATA_V2_DONE.json').exists():
  for g in groups:
   end=P/'owned'/(g+'_SUPERVISOR_END.json')
   if end.exists():assert json.loads(end.read_text())['worker_exit_code']==0,'TRAINING_JOB_FAILED:'+g
  assert time.time()<deadline-2400-7200,'RESERVE_FOR_FROZEN_STATES'
  time.sleep(4)
 command('recollect_training_v3.py',timeout=1800)
 command('v6_check_feature_audit.py')
 command('v6_identity_replay.py')
 command('v6_coordinated_identity.py')
 # The actual full-tail gate is inspected before fitting. TRAIN_O1 already shows >1 N.s regret.
 gap=json.loads((P/'analysis/TRAINING_DECISION_GAP.json').read_text());primary_gap=[r for r in gap if r['group'].startswith('TRAIN_')];assert any(r['half_regret_N_s'] is not None and r['half_regret_N_s']>.02 for r in primary_gap),'NO_DECISION_GAP_DO_NOT_EXPAND_CRITIC'
 command('v6_fit_freeze.py');frozen=json.loads((P/'models/COMMON_COMPOSE_FROZEN.json').read_text());check_frozen_sources(frozen)
 templates=json.loads((P/'freeze/TEST_INPUT_TEMPLATES_V2.json').read_text())['configs'];protocol=dict(frozen_unix=time.time(),model_sha256=sha(P/'models/COMMON_COMPOSE_FROZEN.json'),selection_source_sha256=sha(P/'source/v6_selection.py'),evaluation_source_sha256=sha(P/'source/v6_evaluate.py'),test_worker_sha256=sha(P/'source/v6_test_worker.py'),return_worker_sha256=sha(P/'source/v6_coordinated_return_worker.py'),test_groups=[c['group'] for c in templates],outcomes_seen=False,configs={})
 for c in templates:
  c.update(frozen_bundle='models/COMMON_COMPOSE_FROZEN.json',frozen_bundle_sha256=protocol['model_sha256']);put('experiments/'+c['group']+'.json',c);put('runtime/'+c['group']+'_TEST_PLAN.json',dict(condition=c['condition'],arms=c['arms']));protocol['configs'][c['group']]=sha(P/'experiments'/f"{c['group']}.json")
 put('freeze/PRIMARY_TEST_PROTOCOL_FROZEN.json',protocol);event('PRIMARY_MODEL_AND_TESTS_FROZEN')
 for c in templates:
  check_frozen_sources(frozen)
  if job(c):command('v6_evaluate.py',c['group'],'models/COMMON_COMPOSE_FROZEN.json',timeout=1200)
 # One fresh independent legacy-B repair state, never pooled with smooth-policy labels.
 c=json.loads((P/'experiments/LEGACY_NEW_O.json').read_text());put('freeze/LEGACY_NEW_TEST_FINAL.json',dict(frozen_unix=time.time(),config_sha256=sha(P/'experiments/LEGACY_NEW_O.json'),worker_sha256=sha(P/'source/v6_legacy_worker.py'),online_source_sha256=sha(P/'source/v6_online.py'),selection_source_sha256=sha(P/'source/v6_selection.py'),model_sha256=c['frozen_bundle_sha256'],outcomes_seen=False))
 if job(c):command('v6_evaluate.py',c['group'],c['frozen_bundle'],'legacy',timeout=1200)
 # Independent confirmation of the single targeted traditional interpolation, regardless of Critic outcome.
 for g in ['SMOOTH_A1','SMOOTH_A2']:
  c=json.loads((P/'experiments'/f'{g}.json').read_text())
  if job(c):command('v6_data.py',g,timeout=1200)
 event('CORE_FROZEN_AND_BLEND_STUDIES_COMPLETED')
 # Pre-state screening uses a strong transparent phase lookup; it does not smuggle measured H states into a proxy.
 from v6_prescreen import fit_proxy
 from v6_data import group as collect
 model=fit_proxy(groups);put('models/PRESTATE_PROXY_V1_FROZEN.json',model)
 temps=json.loads((P/'freeze/SCREEN_INPUT_TEMPLATES_V2.json').read_text())['configs'];frozen_screen=dict(frozen_unix=time.time(),source_sha256=sha(P/'source/v6_prescreen.py'),screen_worker_sha256=sha(P/'source/v6_screen_worker.py'),v1_sha256=sha(P/'models/PRESTATE_PROXY_V1_FROZEN.json'),development_groups=['SCREEN_S1','SCREEN_S2'],independent_groups=['SCREEN_S3','SCREEN_AUDIT'],none_of_these_outcomes_seen=True);put('freeze/SCREEN_PROTOCOL_V1_FROZEN.json',frozen_screen)
 development=[]
 for c in temps[:2]:
  c.update(frozen_proxy='models/PRESTATE_PROXY_V1_FROZEN.json',frozen_proxy_sha256=frozen_screen['v1_sha256'])
  if job(c):collect(c['group'],wrench=True);development.append(c['group'])
 assert len(development)==2,'SCREEN_DEVELOPMENT_INCOMPLETE'
 model=fit_proxy(groups,development);put('models/PRESTATE_PROXY_V2_FROZEN.json',model);v2sha=sha(P/'models/PRESTATE_PROXY_V2_FROZEN.json');put('freeze/SCREEN_PROTOCOL_V2_FROZEN.json',dict(frozen_unix=time.time(),model_sha256=v2sha,source_sha256=sha(P/'source/v6_prescreen.py'),development_groups=groups+development,test_groups=['SCREEN_S3','SCREEN_AUDIT'],test_outcomes_seen=False))
 for c in temps[2:]:
  c.update(frozen_proxy='models/PRESTATE_PROXY_V2_FROZEN.json',frozen_proxy_sha256=v2sha)
  if job(c):collect(c['group'],wrench=True)
 event('FINITE_SCREEN_WORKFLOW_COMPLETED')
 put('jobs/CAMPAIGN_DONE.json',dict(status='COMPLETED_REQUIRED_FINITE_BRANCHES',started_unix=start,ended_unix=time.time(),events=events))
except BaseException as e:
 event('REVIEW_REQUIRED',error=str(e));put('jobs/CAMPAIGN_ERROR.json',dict(error=str(e),traceback=traceback.format_exc(),unix=time.time()));raise
finally:put('owned/CAMPAIGN_DRIVER_V3_END.json',dict(pid=os.getpid(),ended_unix=time.time(),events=events))
