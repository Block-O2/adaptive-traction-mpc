"""Meaningful stdlib-only failure/cap/recovery tests. No physics/gradients."""
from pathlib import Path
import os,sys,tempfile,datetime,json,importlib.util,time,ast
from research_common import ROOT,atomic,now
T=ROOT/'unattended/template/scripts';sys.path.insert(0,str(T))
from finite_engine import run_finite,GlobalStop,BranchFailure,classify
checks={};history=[]
jobs=[dict(id='a1',branch='A'),dict(id='a2',branch='A'),dict(id='b1',branch='B')]
def execute(j):
 if j['id']=='a1':raise BranchFailure('safe bounded branch failed')
 return dict(task_success=True)
r=run_finite(jobs,execute,history.append);checks['branch_fail_skips_its_descendants_but_continues_B']=[x['status'] for x in r]==['BRANCH_FAIL','SKIPPED_FAILED_BRANCH','COMPLETE']
r=run_finite(jobs,lambda j:dict(task_success=False),lambda x:None);checks['ordinary_task_fail_does_not_stop_queue']=len(r)==3 and all(x['status']=='SCIENTIFIC_FAIL' for x in r)
def globalbad(j):raise GlobalStop('actual safety integrity lost')
r=run_finite(jobs,globalbad,lambda x:None);checks['global_integrity_stops_queue']=len(r)==1 and r[0]['status']=='GLOBAL_STOP'
checks['unknown_worker_failure_never_silently_continues']=classify(dict(success=False,error='unknown'))=='GLOBAL'
checks['audited_safe_branch_failure_classifies_locally']=classify(dict(success=False,safe_branch_failure=True,worker_end=dict(owner_joined=True),child_joined=True))=='BRANCH'
checks['audit_failure_is_global']=classify(dict(success=False,error='INDEPENDENT_AUDIT_FAILED'))=='GLOBAL'
with tempfile.TemporaryDirectory(prefix='std_scheduler_',dir='/tmp') as tmp:
 root=Path(tmp);current=datetime.datetime.now(datetime.timezone.utc);(root/'START.json').write_text(json.dumps(dict(hard_stop_utc=(current+datetime.timedelta(hours=8)).isoformat(),no_new_training_utc=(current+datetime.timedelta(hours=6)).isoformat(),limits=dict(training_attempts=5,evaluation_attempts=5,native_steps=14*165000))))
 prior=os.environ.get('IHEAR_RESEARCH_ROOT');os.environ['IHEAR_RESEARCH_ROOT']=str(root)
 spec=importlib.util.spec_from_file_location('future_budget_test',T/'research_common.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 if prior is None:os.environ.pop('IHEAR_RESEARCH_ROOT')
 else:os.environ['IHEAR_RESEARCH_ROOT']=prior
 original=m.resources;m.resources=lambda:dict(unix=time.time(),available_bytes=8*1024**3,disk_free_bytes=20*1024**3)
 first,_=m.reserve('training','A',root/'fake1',1)
 try:m.reserve('training','B',root/'fake2',1);checks['single_physics_reservation']=False
 except RuntimeError as e:checks['single_physics_reservation']='CONCURRENT_PHYSICS' in str(e)
 m.settle(first,165000,1,0,'SYNTHETIC_CONTROL_TEST_NO_PHYSICS')
 second,_=m.reserve('training','A',root/'fake2',2);m.settle(second,165000,1,0,'SYNTHETIC_CONTROL_TEST_NO_PHYSICS')
 try:m.reserve('training','A',root/'fake3',3);checks['holdout_native_reserve_protected']=False
 except RuntimeError as e:checks['holdout_native_reserve_protected']='NATIVE_RESERVATION' in str(e)
 last,_=m.reserve('evaluation','LOCKED_FINAL_1',root/'fakefinal',1);m.settle(last,1,1,0,'SYNTHETIC_CONTROL_TEST_NO_PHYSICS')
 checks['reserved_holdout_admitted']=m.read(root/'LEDGER.json')['evaluation_attempts']==1
 m.resources=lambda:dict(unix=time.time(),available_bytes=5*1024**3,disk_free_bytes=20*1024**3)
 try:m.check_resources();checks['RAM_below6GiB_denied']=False
 except RuntimeError:checks['RAM_below6GiB_denied']=True
 m.resources=original;m.HARD_STOP=time.time()-1
 try:m.check_resources();checks['expired_deadline_denied']=False
 except RuntimeError:checks['expired_deadline_denied']=True
 ident=m.pid_identity(os.getpid());checks['reused_PID_starttime_rejected']=m.same_pid(ident) and not m.same_pid(dict(ident,start_ticks='0'))
 state=dict(status='OLD',phase='A');m.atomic(root/'STATE.json',dict(state,status='NEW',phase='B'));checks['duplicate_status_bug_regression']=m.read(root/'STATE.json')==dict(status='NEW',phase='B')
 checks['all_synthetic_reservations_closed']=all(x['settled'] for x in m.read(root/'LEDGER.json')['attempts'])
checks['all_inactive_sources_parse']=all(ast.parse(p.read_text()) is not None for p in T.glob('*.py'))
result=dict(time_utc=now(),checks=checks,pass_=all(checks.values()),new_physics=0,Adam=0,scope='Synthetic scheduler/control tests plus syntax; not end-to-end PPO training validation')
atomic(ROOT/'audit/UNATTENDED_CONTROL_TESTS.json',result);print(json.dumps(result));assert result['pass_']
