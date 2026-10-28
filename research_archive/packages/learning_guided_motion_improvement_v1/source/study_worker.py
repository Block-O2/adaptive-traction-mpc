"""Single native owner, serial full-state forks, isolated adaptive three arms."""
from pathlib import Path
import os,sys,json,time,signal,random,traceback,fcntl,hashlib,datetime,copy
P=Path(__file__).resolve().parents[1];R=P/'runtime';GROUP='OPTIMIZATION'
os.environ.update(STUDY_GROUP=GROUP,STUDY_MODE='development',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TMPDIR=str(R/'tmp'),MPLCONFIGDIR=str(R/'tmp/mpl'))
sys.dont_write_bytecode=True;sys.path[:0]=[str(P/'source'),str(R/'control'),str(R/'code')]
import campaign_v6 as frozen
import study_common as sc,matched_harness as mh,analyze_matched as am
from optimizers import ArmOptimizer,worst_ratio,METHODS
import numpy as np
PLAN=json.loads((R/'RUN_PLAN.json').read_text());CONFIG=json.loads((R/(GROUP+'_TEST_PLAN.json')).read_text());INITIAL=12
CATEGORY='engineering'
def put(n,x):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);tmp=f.with_suffix(f.suffix+'.tmp');tmp.write_text(json.dumps(sc.clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n');tmp.replace(f)
def native_used():
 total=0
 for row in mh.records():
  if row['event']!='START':continue
  ident=row['id'];data=R/'output'/(ident+'_DATA.json');partial=R/'output'/(ident+'_PARTIAL_COMPUTE.json')
  if data.exists():total+=int(json.loads(data.read_text())['metric']['actual_new_native_physics_steps'])
  elif partial.exists():total+=int(json.loads(partial.read_text()).get('actual_new_native_physics_steps') or 0)
 return total

def dispatch(ident,**kw):
 rs=mh.records();starts=[r for r in rs if r['event']=='START'];assert len(starts)<80,'TOTAL_START_CAP'
 assert not any(r['id']==ident for r in starts),'DUPLICATE'
 assert time.time()<PLAN['dispatch_cutoff_unix']-PLAN['physical_timeout_s'],'FINAL_45_MIN_RESERVE'
 assert native_used()+360000<=8000000,'NATIVE_RESERVE_CAP'
 assert not (P/'STOP_REQUESTED').exists(),'STOP_REQUESTED'
 for rel,h in json.loads((P/'CAMPAIGN_SOURCE_MANIFEST.json').read_text())['files'].items():assert sc.sha(P/rel)==h,'SOURCE_CHANGED:'+rel
 count=sum(r.get('category')==CATEGORY for r in starts)
 if CATEGORY=='optimization':assert count<60,'OPTIMIZATION_CAP'
 elif CATEGORY=='validation':assert count<12,'VALIDATION_CAP'
 elif CATEGORY=='engineering':assert count<8,'ENGINEERING_CAP'
 mh.event('START',ident,category=CATEGORY,source_sha256=sc.sha(P/'CAMPAIGN_SOURCE_MANIFEST.json'),**kw)
mh.dispatch=dispatch

class Study(frozen.Campaign):
 def __init__(self):
  super().__init__(CONFIG['condition']);self.active_x=[0.,0.];self.arm_rows={a:[] for a in 'ABC'};self.metrics=[];self.causal=[];self.current_prediction=None;self.counter_wall=0;self.closed_native=0;self.baseline=None;self.locked={}
 def control(self,b):
  super().control(b)
  if self.current is not None and self.current['base']=='T':
   x=np.asarray(frozen.bc.OLD['free_parameters'],float).copy();x[[1,6]]+=.002*np.asarray(self.active_x)
   assert np.all(np.abs(self.active_x)<=np.ones(2)+1e-12),'PARAMETER_DOMAIN'
   b['planner'].free_parameters=x
 def boundary(self,b):
  super().boundary(b)
  if time.time()-self.counter_wall>2:
   self.counter_wall=time.time();current=round(float(b['physical_now'])/.00025)-(0 if self.child is None else self.child['physics_step_at_fork']);used=self.closed_native+current
   assert used+160000<=8000000,'LIVE_NATIVE_CAP';assert current<=180000,'ATTEMPT_NATIVE_CAP'
   mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines());assert int(mem['MemAvailable'].split()[0])*1024>=6*2**30,'RAM_FLOOR';assert not (P/'STOP_REQUESTED').exists(),'STOP_REQUESTED'
   put('audit/LIVE_PHYSICS_COUNTERS.json',{'unix':time.time(),'pid':os.getpid(),'id':self.condition['name']+'_parent' if self.child is None else self.child['label']+'_'+self.child['kind'],'closed_native_at_dispatch':self.closed_native,'actual_new_native_live':current,'budget_upper_with_parent_reserve':used+160000})
  if self.child is not None:
   self.causal.append({'time_s':float(b['physical_now']),'phase':b['task_state'].phase.value,'estimated_q_dq':b['observation'].as_array(),'reference_q_dq':np.r_[b['reference'].q_rad,b['reference'].dq_rad_s],'measured_force':b['interface'].measured_force_world_n,'measured_moment':b['interface'].measured_moment_world_nm,'source_sample_time_s':b['request'].source_sample_time_s,'truth_used':False})
 def finish(self,env,metric):
  super().finish(env,metric);put('history/'+metric['name']+'_CAUSAL_HISTORY.json',self.causal)
  put('attempts/'+metric['name']+'_EXECUTION_BINDING.json',{'x':self.active_x,'proposal':self.current_prediction,'actual_free_parameters':(np.asarray(frozen.bc.OLD['free_parameters'])+np.eye(18)[[1,6]].T@(.002*np.asarray(self.active_x))).tolist(),'base_candidate':self.current,'native_final_authority':True,'model_future_truth_used':False})
 def run_branch(self,b,tag,candidate,x,category,prediction=None):
  global CATEGORY
  CATEGORY=category;self.closed_native=native_used();self.current_prediction=prediction
  ident=GROUP+'_'+tag
  if prediction is not None:
   prediction.update(id=ident,created_unix=time.time(),causal_parent_hash=self.manifest(b)['hash'],causal_state_path='audit/OPTIMIZATION_FORK_CONTEXT.json');put('predictions/'+ident+'.json',prediction)
  failed=None
  try:
   if self.fork(b,tag,np.zeros((2,5,3))):
    self.current=copy.deepcopy(candidate);self.active_x=list(x);self.references={};self.sample_rows=[];self.terminal_intent=None;self.causal=[];self.counter_wall=0.;signal.alarm(600);return True
  except AssertionError as error:
   if not (str(error).startswith('CHILD_FAILED:') or str(error).startswith('NATIVE_PHYSICAL_FAILURE:')):raise
   assert self.active_owned_child_pid is None and self.parent_checks[-1]['unchanged'],'PARENT_MUTATED_AFTER_FAILURE';failed=str(error)
  row={'id':ident,'x':list(x),'category':category,'complete':False,'qualified':False,'prediction':prediction,'error':failed,'metrics_path':None}
  data=R/'output'/(ident+'_DATA.json');part=R/'output'/(ident+'_PARTIAL_COMPUTE.json')
  if data.exists():row['actual_new_native_steps']=json.loads(data.read_text())['metric']['actual_new_native_physics_steps']
  elif part.exists():row['partial_compute']=json.loads(part.read_text());row['actual_new_native_steps']=row['partial_compute']['actual_new_native_physics_steps']
  if failed is None:
   m=am.measure(ident);B=m if tag=='B' else json.loads((R/'reports/OPTIMIZATION_B_MEASURED.json').read_text());comp=am.compare(m,B)
   timing=m['axes']['LEGACY_R2_MATCHED']=='PASS';qualified=bool(comp['acceptance_pass'] and timing and m['native_physical_audit']['pass_'] and m['axes']['PHYSICAL_TASK_VALID']=='PASS' and m['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID']=='PASS')
   summary=json.loads((R/'source/results'/ident/'summary.json').read_text());execution=[]
   expected=np.asarray(frozen.bc.OLD['free_parameters'],float).copy();expected[[1,6]]+=.002*np.asarray(x)
   for lr in summary['learning_records']:
    meta=lr.get('selected_plan',{}).get('execution_screen',{}).get('free_trajectory')
    if not meta:continue
    assert np.max(abs(np.asarray(meta['parameters'])-expected))<1e-12,'EXECUTED_PARAMETER_IDENTITY'
    di=lr.get('decision_index');decision=summary['decisions'][di] if di is not None else {}
    execution.append({'phase':lr.get('phase',decision.get('phase')),'metadata':meta,'activated':lr.get('selected_plan_activated')})
   row['free_parameter_execution']=execution
   row['proposed_parameters_identity_checked']=True
   row.update(complete=True,qualified=qualified,JF=m['J_F_N_s'],JM=m['moment_integral_Nm_s'],worst_ratio=worst_ratio(m,B,comp),motion_vs_B=comp,axes=m['axes'],metrics_path=str((R/'reports'/(ident+'_MEASURED.json')).relative_to(P)),branch=m['branch'],actual_new_native_steps=m['actual_new_native_steps'])
  self.metrics.append(row);put('attempts/'+ident+'_RESULT.json',row);put('THREE_ARM_PROGRESS.json',{'rows':self.arm_rows,'all_physical_rows':self.metrics,'locked':self.locked})
  print('BRANCH_END',ident,'complete',row['complete'],'qualified',row['qualified'],'JF',row.get('JF'),'JM',row.get('JM'),'x',x,'error',failed,flush=True)
  self.last_row=row;return False
 def decision_boundary(self,b):
  if self.child is None and not self.fork_done and b['task_state'].phase.value=='OUTBOUND' and self.count['OUTBOUND']>=1:
   self.fork_done=True;signal.alarm(max(1,int(PLAN['physics_hard_stop_unix']-time.time())))
   put('audit/OPTIMIZATION_FORK_CONTEXT.json',{'physical_s':b['physical_now'],'task_s':b['physical_now']-b['task_start_time'],'causal_estimated_state':b['observation'].as_array(),'commissioned_belief':b['belief'].value_state_record(),'phase':b['task_state'].phase.value,'count':self.count,'source':'complete cold native + original D01R legal prefix; no reconstruction'})
   nativeB=copy.deepcopy(CONFIG['arms'][0]);H=copy.deepcopy(CONFIG['arms'][1])
   for tag,c in [('B',nativeB),('H150',H)]:
    if self.run_branch(b,tag,c,[0,0],'validation'):return self.control(b)
    assert self.last_row['qualified'],'CURRENT_STRONG_BASELINE_NOT_QUALIFIED'
    historical=R/'source/results'/('RECOVERY_'+tag);gate=frozen.bc.compare_raw(R/'source/results'/(GROUP+'_'+tag),historical);put('audit/OPTIMIZATION_'+tag+'_RECOVERY_RAW_GATE.json',gate);assert gate['status']=='PASS','COMMON_ANCHOR_RAW_MISMATCH'
   ref=self.last_row;B=self.metrics[-2];self.baseline={'JF':ref['JF'],'JM':ref['JM'],'worst_ratio':ref['worst_ratio'],'B_JM':B['JM'],'id':ref['id']};put('BASELINE_LOCK.json',self.baseline)
   optim={a:ArmOptimizer(a,self.baseline) for a in 'ABC'}
   for n in range(12):
    for arm in 'ABC':
     x,pred=optim[arm].propose(self.arm_rows[arm]);tag=arm+'_%03d'%(n+1)
     if self.run_branch(b,tag,H,x,'optimization',pred):return self.control(b)
     self.last_row['arm']=arm;self.arm_rows[arm].append(self.last_row);put('THREE_ARM_PROGRESS.json',{'rows':self.arm_rows,'all_physical_rows':self.metrics,'locked':self.locked})
   eligible=[a for a in 'ABC' if any(r['qualified'] and self.baseline['JF']-r['JF']>.01 for r in self.arm_rows[a])];put('EXTENSION_ALLOCATION_LOCK.json',{'eligible_arms':eligible,'first12_fixed':True,'rule':'at least one qualified >0.01 N s gain','created_unix':time.time()})
   for n in range(12,20):
    for arm in eligible:
     x,pred=optim[arm].propose(self.arm_rows[arm]);tag=arm+'_%03d'%(n+1)
     if self.run_branch(b,tag,H,x,'optimization',pred):return self.control(b)
     self.last_row['arm']=arm;self.arm_rows[arm].append(self.last_row);put('THREE_ARM_PROGRESS.json',{'rows':self.arm_rows,'all_physical_rows':self.metrics,'locked':self.locked})
   for arm in 'ABC':
    q=[r for r in self.arm_rows[arm] if r['qualified']];self.locked[arm]=min(q,key=lambda r:r['JF']) if q else None
   put('FINAL_SELECTION_BEFORE_VALIDATION.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'locked':self.locked,'candidate_model_updates_after_this_lock':False,'primary12':{a:min([r for r in self.arm_rows[a][:12] if r['qualified']],key=lambda r:r['JF'],default=None) for a in 'ABC'}})
   for arm in 'ABC':
    selected=self.locked[arm]
    if selected is None:continue
    if self.run_branch(b,'FROZEN_'+arm,H,selected['x'],'validation',copy.deepcopy(selected['prediction'])):return self.control(b)
    assert self.last_row['qualified'],'LOCKED_CANDIDATE_REPEAT_FAILED'
    gate=frozen.bc.compare_raw(R/'source/results'/selected['id'],R/'source/results'/self.last_row['id']);put('audit/FROZEN_'+arm+'_RAW_REPEAT_GATE.json',gate);assert gate['status']=='PASS','FROZEN_REPEAT_RAW_MISMATCH'
   put('THREE_ARM_RESULTS.json',{'status':'EXECUTED_WITH_REPORTED_QUALIFICATIONS','baseline':self.baseline,'rows':self.arm_rows,'all_physical_rows':self.metrics,'locked':self.locked,'all_parent_unchanged':all(x['unchanged'] for x in self.parent_checks),'same_patient_same_state_only':True})
  self.control(b)

def main():
 assert json.loads((P/'audit/RECOVERY_DONE.json').read_text())['status']=='PASS','RECOVERY_REQUIRED'
 lock=(P/'PHYSICS.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('OWNED_WALL_TIMEOUT')));signal.alarm(max(1,int(PLAN['physics_hard_stop_unix']-time.time())))
 it=Study();ident=GROUP+'_parent';start=time.time();dispatch(ident,kind='LEGAL_COLD_PARENT');random.seed(CONFIG['condition']['seed']);np.random.seed(CONFIG['condition']['seed'])
 try:
  m=sc.run(ident,it,execution_mode='SCIENTIFIC_SIMULATION')
  if it.child is not None:os._exit(0)
  mh.event('END',ident,returncode=0,joined=True,native_steps=m['actual_new_native_physics_steps'],wall_seconds=time.time()-start)
  am.measure(ident);gate=frozen.bc.compare_raw(R/'source/results'/ident,R/'source/results/OPTIMIZATION_B');put('audit/OPTIMIZATION_PARENT_RAW_GATE.json',gate);assert gate['status']=='PASS','PARENT_B_RAW_DIFFERENCE'
  put('audit/OPTIMIZATION_DONE.json',{'status':'PASS_EXECUTED','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'all_children_joined':True,'wall_s':time.time()-start,'parent_checks':it.parent_checks})
 except BaseException as error:
  actual=ident if it.child is None else it.child['label']+'_'+it.child['kind'];put('audit/'+actual+'_ERROR.json',{'error':str(error),'traceback':traceback.format_exc()})
  if it.child is not None:os._exit(1)
  if not any(r['event']=='END' and r['id']==ident for r in mh.records()):mh.event('END',ident,returncode=1,joined=True,error=str(error))
  put('audit/OPTIMIZATION_DONE.json',{'status':'FAILED_PRESERVED','error':str(error),'wall_s':time.time()-start,'arm_rows':it.arm_rows});raise
 finally:
  if it.child is None:signal.alarm(0);put('audit/OPTIMIZATION_OWNER_EXIT.json',{'pid':os.getpid(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'active_child':getattr(it,'active_owned_child_pid',None)})
if __name__=='__main__':main()
