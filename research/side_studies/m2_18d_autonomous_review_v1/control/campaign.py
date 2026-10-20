"""Frozen reference qualification. Serial full-address-space forks; no search."""
from pathlib import Path
import os,sys,time,json,signal,random,traceback,fcntl,hashlib,shutil,itertools
P=Path(__file__).resolve().parents[1]
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TMPDIR=str(P/'tmp'),MPLCONFIGDIR=str(P/'tmp/mpl'))
sys.dont_write_bytecode=True;sys.path.insert(0,str(P/'code'))
import study_common as sc, matched_harness as mh, analyze_matched as am
from interfaces import TableInterface
from rich_planner import RichFreePlanner
from stream_runtime_evidence import array_items
import numpy as np
PLAN=json.loads((P/'RUN_PLAN.json').read_text());OLD=json.loads((P/'FROZEN_18D.json').read_text());NEW=json.loads((P/'CANDIDATE.json').read_text());REPAIR=json.loads((P/'BOUNDED_REPAIR.json').read_text())
GROUP=os.environ.get('STUDY_GROUP','reproduction')
H=P.parent/'ihear_overnight_research_retrospective_v1'
def put(n,x):mh.put(P/n,sc.clean(x))
def read(n):return json.loads((P/n).read_text())
def dispatch(ident,**extra):
 n=sum(r['event']=='START' for r in mh.records());now=time.time()
 assert n<PLAN['physics_budget'] and now<PLAN['dispatch_cutoff_unix']-PLAN['physical_timeout_s'],'BUDGET_OR_START_DEADLINE'
 assert not (P/'PHYSICS_STOP.json').exists(),'STOPPED'
 assert not any(r['event']=='START' and r['id']==ident for r in mh.records()),'DUPLICATE_START'
 assert shutil.disk_usage(P).free>15*2**30,'DISK_STOP'
 assert sum(f.stat().st_size for f in P.rglob('*') if f.is_file())<10*2**30,'PACKAGE_SIZE_STOP'
 mh.event('START',ident,code_manifest_sha256=sc.sha(P/'EXECUTION_CODE_MANIFEST.json'),plan_sha256=sc.sha(P/'RUN_PLAN.json'),group=GROUP,**extra)
 put('STATE.json',dict(phase='SERIAL_'+GROUP,owned_pids=[os.getpid()],physics_starts=n+1,last_start=ident,next_action='finish and evaluate current frozen arm'))
mh.dispatch=dispatch
def compare_raw(pa,pb):
 errors=[];fields={}
 with np.load(pa/'trace.npz') as a,np.load(pb/'trace.npz') as b:
  if set(a.files)!=set(b.files):errors.append('TRACE_SCHEMA')
  else:
   for k in a.files:
    same=a[k].shape==b[k].shape and (np.array_equal(a[k],b[k],equal_nan=True) if a[k].dtype.kind in 'fc' else np.array_equal(a[k],b[k]))
    fields[k]=bool(same)
    if not same:errors.append('TRACE:'+k)
 counts={}
 for array,keys in [('native_states_evaluation_only',['time_s','qpos_evaluation_only','qvel_evaluation_only','command_torque_nm','contact_pairs_evaluation_only','command_id','native_step_index']),('command_receipts',['receipt_index','applied','start_physics_s','end_physics_s','native_steps','source_sample_time_s','command_torque_nm','q_ref_rad','dq_ref_rad_s','reference_version','validation_model_version','plan_request_id','command_kind'])]:
  n=0
  for x,y in itertools.zip_longest(array_items(pa/'runtime_artifacts.json.gz',array),array_items(pb/'runtime_artifacts.json.gz',array)):
   n+=1
   if x is None or y is None:errors.append(array+':LENGTH');break
   for k in keys:
    if x.get(k)!=y.get(k):errors.append(array+':'+k)
  counts[array]=n
 return dict(status='PASS' if not errors else 'FAIL',a=str(pa),b=str(pb),trace_fields=fields,errors=sorted(set(errors)),counts=counts,wall_profiling_excluded=True,scope='every trace field plus native body/contact/applied torque and scientific receipt/reference/source/ownership fields')
class Qualification(mh.MatchedInterface):
 def __init__(self,condition):
  super().__init__(condition);self.arm=None;self.results=[]
 def choose(self,b,c):
  if self.arm not in ['E','C','C_repeat','R','R_repeat']:return TableInterface.choose(self,b,c)
  ph=c['phase'];i=self.count[ph];self.count[ph]+=1
  spec=OLD.get('phases',{}).get(ph,[None]*5)[i] if i<5 else None
  if spec is None:
   self.apply(b,c,np.zeros(3),np.zeros(3));self.labels[-1].update(native_index=i,search_candidate=OLD['id']);return
  assert max(abs(np.asarray(spec['values'])))<=.2+1e-12
  start=c['start_m'];lo,hi=spec['support'];fraction=np.r_[lo,lo+(hi-lo)*np.asarray(spec['knots']),hi]
  knots=start+(1-start)*fraction;values=np.r_[0.,spec['values'],0.];pairs=np.column_stack([knots,values]).tolist()
  if pairs[0][0]>0:pairs=[[0.,0.]]+pairs
  if pairs[-1][0]<1:pairs=pairs+[[1.,0.]]
  a=np.asarray(pairs);assert a[0].tolist()==[0.,0.] and a[-1].tolist()==[1.,0.] and np.all(np.diff(a[:,0])>0)
  self.action={ph:pairs};b['planner'].residual_spec=self.action
  self.labels.append(dict(**c,action=[0.,0.,0.],teacher_label=[0.,0.,0.],graph=self.action,expected_delta=float(np.interp(c['nominal_m'],a[:,0],a[:,1])),native_index=i,search_candidate=OLD['id'],raw_v2=True,registered_spec=spec));self.previous=np.zeros(3)
 def control(self,b):
  planner=b['planner']
  if self.arm in ['E','C','C_repeat','R','R_repeat']:
   if not isinstance(planner,RichFreePlanner):planner.__class__=RichFreePlanner
   planner.free_parameters=np.asarray((NEW if self.arm in ['C','C_repeat'] else REPAIR if self.arm in ['R','R_repeat'] else OLD)['free_parameters'],float)
  # Parent/B remain the native historical planner, never receive richer intent.
  return mh.MatchedInterface.control(self,b)
 def decision_boundary(self,b):
  phase=b['task_state'].phase.value;needed=0 if GROUP in ['reproduction','development'] else 1
  if self.child is None and not self.fork_done and phase=='OUTBOUND' and self.count[phase]>=needed:
   self.fork_done=True
   put('audit/'+GROUP+'_FORK_CONTEXT.json',dict(phase=phase,physical_s=b['physical_now'],task_s=b['physical_now']-b['task_start_time'],count=self.count.copy(),condition=self.condition,source='actual native execution, complete live address-space fork, no state replay',state_manifest=self.manifest(b)))
   arms=['B','E'] if GROUP=='reproduction' else ['B','E','C','C_repeat'] if GROUP=='N2' else ['B','E',read('DEVELOPMENT_SELECTION.json')['selected']]
   if GROUP=='development':arms.append(arms[-1]+'_repeat')
   for arm in arms:
    if self.fork(b,arm,np.zeros((2,5,3))):
     self.arm=arm;signal.alarm(min(PLAN['physical_timeout_s'],max(1,int(PLAN['physics_hard_stop_unix']-time.time()))));return self.control(b)
    ident=GROUP+'_'+arm;m=am.measure(ident);baseline=m if arm=='B' else read('reports/'+GROUP+'_B_MEASURED.json');comp=am.compare(m,baseline)
    r=dict(id=ident,arm=arm,J_F_N_s=m['J_F_N_s'],phase_cost=m['phase_cost'],phase_durations=m['phase_durations'],motion=comp,task=m['axes']['PHYSICAL_TASK_VALID'],receipt=m['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID'],absolute_safety=bool(m['native_physical_audit']['pass_']),native_physical_audit=m['native_physical_audit'],tracking_RMS_deg=m['tracking_RMS_deg'],clearance=m['clearance'],moment_integral_Nm_s=m['moment_integral_Nm_s'],actual_new_native_steps=m['actual_new_native_steps'],branch=m['branch'],metrics_path='reports/'+ident+'_MEASURED.json',complete_task=True)
    assert r['absolute_safety'] and r['task']=='PASS' and r['receipt']=='PASS','ABSOLUTE_TASK_SAFETY_OR_RECEIPT_STOP'
    self.results.append(r);put(GROUP+'_RESULTS.json',dict(condition=self.condition,rows=self.results,no_reselection=True))
    print(json.dumps(dict(id=ident,J_F=m['J_F_N_s'],gain=comp['gain_percent'],motion=comp['acceptance_pass'],failed=comp['failed_requirements'])),flush=True)
    if GROUP=='N2' and arm=='C_repeat':
     cr=next(x for x in self.results if x['arm']=='C')
     if not (cr['motion']['acceptance_pass'] and cr['motion']['gain_percent']>=1.):
      put('audit/C_FIRST_FAILURE.json',dict(classification='SCIENTIFIC_HYPOTHESIS_FAILURE',implementation_contract='PASS',failed=cr['motion']['failed_requirements'],bounded_repair='Predeclared full OUTBOUND half scale; same live parent, new attempts, no threshold changes'));arms.extend(['R','R_repeat'])
    if GROUP=='reproduction':
     oldid='development_repair2_B0_original' if arm=='B' else 'development_repair2_quality_NATIVE_SCALAR_18_063'
     gate=compare_raw(P/'source/results'/ident,H/'source/results'/oldid);put('audit/'+ident+'_ARCHIVE_GATE.json',gate)
     assert gate['status']=='PASS' and comp['acceptance_pass'],'REPRODUCTION_GATE_FAIL'
   bdata=read('output/'+GROUP+'_B_DATA.json');edata=read('output/'+GROUP+'_E_DATA.json')
   for row in self.results:
    assert read('output/'+row['id']+'_DATA.json')['branch_start']['full_hash']==bdata['branch_start']['full_hash'],'UNMATCHED_CANDIDATE'
   for candidate in ['C','R']:
    if any(x['arm']==candidate+'_repeat' for x in self.results):
     repeat=compare_raw(P/'source/results'/(GROUP+'_'+candidate),P/'source/results'/(GROUP+'_'+candidate+'_repeat'));put('audit/'+GROUP+'_'+candidate+'_REPEAT.json',repeat);assert repeat['status']=='PASS','CANDIDATE_REPEAT_FAIL'
   assert bdata['branch_start']['full_hash']==edata['branch_start']['full_hash'],'UNMATCHED_PAIR'
   put(GROUP+'_PAIR_GATE.json',dict(status='PASS',full_hash=bdata['branch_start']['full_hash'],native_hash=bdata['branch_start']['native_hash'],parent_unchanged=all(x['unchanged'] for x in self.parent_checks),parameter_sha256=sc.sha(P/'FROZEN_18D.json')))
  self.control(b)
def main():
 pre=read('PREPHYSICAL_CHECKS.json');assert pre['status']=='PASS'
 if GROUP!='reproduction':assert read('BASELINE_REPRODUCTION.json')['status']=='PASS','REPRODUCTION_REQUIRED'
 lock=(P/'PHYSICS.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 cond=dict(name=GROUP,seed=PLAN['seed'],prefix={}) if GROUP in ['reproduction','development'] else next(c for c in PLAN['validation_conditions'] if c['name']==GROUP)
 it=Qualification(cond);ident=GROUP+'_parent'
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('OWNED_PHYSICAL_TIMEOUT')))
 signal.alarm(max(1,min(2400,int(PLAN['physics_hard_stop_unix']-time.time()))))
 dispatch(ident,kind='LEGAL_COLD_PARENT',condition=cond);random.seed(cond['seed']);np.random.seed(cond['seed'])
 try:
  m=sc.run(ident,it,execution_mode='SCIENTIFIC_SIMULATION')
  if it.child is not None:os._exit(0)
  mh.event('END',ident,returncode=0,joined=True,task_valid=m['task_valid']);assert m['task_valid'],'PARENT_TASK_INVALID'
  am.measure(ident);gate=compare_raw(P/'source/results'/ident,P/'source/results'/(GROUP+'_B'));put(GROUP+'_PARENT_GATE.json',gate);assert gate['status']=='PASS','PARENT_B_DIFFERENCE'
  put(GROUP+'_DONE.json',dict(status='PASS',unix=time.time(),all_children_joined=True,rows=it.results))
  if GROUP=='reproduction':put('BASELINE_REPRODUCTION.json',dict(status='PASS',clock='SCIENTIFIC_SIMULATION',evidence_level='PHYSICAL_LEVEL1',rows=it.results,parent_gate=gate,pair_gate=read(GROUP+'_PAIR_GATE.json'),archive_gates=[read('audit/reproduction_'+a+'_ARCHIVE_GATE.json') for a in ['B','E']],historical_report_values=dict(B=1438.613498467,E=1400.697221153),host_clock_qualified=False))
 except BaseException as e:
  actual=ident if it.child is None else it.child['label']+'_'+it.child['kind'];put('reports/'+actual+'_ERROR.json',dict(error=str(e),traceback=traceback.format_exc(),unix=time.time()))
  if it.child is not None:os._exit(1)
  if not any(r['event']=='END' and r['id']==ident for r in mh.records()):mh.event('END',ident,returncode=1,joined=True,error=str(e))
  put('PHYSICS_STOP.json',dict(reason=str(e),unix=time.time()))
  if GROUP=='reproduction':put('BASELINE_REPRODUCTION.json',dict(status='FAIL',error=str(e),new_state_physics_allowed=False))
  raise
 finally:
  if it.child is None:
   signal.alarm(0);put(GROUP+'_WORKER_EXIT.json',dict(pid=os.getpid(),unix=time.time(),active_child=getattr(it,'active_owned_child_pid',None)))
if __name__=='__main__':main()
