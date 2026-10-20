"""Verified CPU forks with direct executed remaining-cost labels, no P labels."""
from study_common import *
from interfaces import TableInterface
from native_core import feature,candidates
from accounting import record,attempts
import fork_core as fc
import random,gc,traceback
class BranchInterface(TableInterface):
 def __init__(self,request):
  super().__init__(request.get('table'));self.request=request;self.group=request['group'];self.split=request['split'];self.targets=request.get('targets',[['OUTBOUND',0],['OUTBOUND',2],['OUTBOUND',4],['RETURN',1]]);self.n=request.get('candidates',6);self.finished=[];self.branch_output_dir=None;self.value_rows=[];self.branch_records=[];self.carry=self.table.copy();self.branch_start=None
 def manifest(self,b):
  m=fc.state_manifest(b,self);state=dict(table=self.table,count=self.count,previous=self.previous,labels=self.labels,model_hash=self.model_hash,carry=self.carry)
  m['interface_state']=clean(state);m['hash']=digest(dict(native=m['manifest'],interface=state));return m
 def collect(self,b,c):
  self.value_rows.append(dict(input=feature(c,self.table,self.count,self.carry),G_input=feature(c,np.zeros((2,5,3)),self.count,self.carry),context=c,count=self.count.copy(),prefix_J_F=float(b['sac_hooks'].force_integral),prefix_M=float(b['sac_hooks'].moment_integral)))
 def make_plans(self,b,c,label):
  return candidates(c,self.count,self.carry,int.from_bytes(hashlib.sha256(label.encode()).digest()[:4],'little'),self.n)
 def choose(self,b,c):
  phase=c['phase'];idx=self.count[phase];label=self.group+'_'+phase+'_'+str(idx)
  if self.child is None and [phase,idx] in self.targets and label not in self.finished:
   self.finished.append(label);fc.quiesce(b);gc.collect();assert 'torch' not in sys.modules,'CPU_QUIESCENT_FORK_ONLY'
   before=self.manifest(b);save(label+'_SNAPSHOT.json',before)
   plans=self.make_plans(b,c,label)
   assert self.manifest(b)['hash']==before['hash'],'CANDIDATES_MUTATED_NATIVE_STATE'
   for j,(table,source) in enumerate(plans):
    guard();assert attempts()<(240 if self.split in ('test','evaluation','diagnostic') else 160),'PHYSICS_CAP_WITH_INDEPENDENT_RESERVE'
    name=label+'_candidate'+str(j);config=dict(group=self.group,split=self.split,snapshot=label,snapshot_hash=before['hash'],table=table.tolist(),source=source,continuation='native-certified-committed-K3-suffix-v1',information='B estimated commissioned belief',version=1)
    completed=L/(name+'_DATA.json')
    if completed.exists():
     prior=read(completed.name);assert digest(prior['branch_start']['context'])==digest(c),'RESUME_PREFIX_CHANGED';self.branch_records.append(dict(id=name,skipped_completed=True));continue
    if (O/name).exists():
     n=1
     while (O/(name+'_retry'+str(n))).exists():n+=1
     name+='_retry'+str(n)
    output=O/name;output.mkdir(exist_ok=False);record('START',name,config=config,input_hash=digest(config))
    python_rng=random.getstate();numpy_rng=np.random.get_state();pid=os.fork()
    if pid==0:
     random.setstate(python_rng);np.random.set_state(numpy_rng)
     try:
      restored=self.manifest(b);assert restored['hash']==before['hash'],'FORK_RESTORE_HASH'
      self.child=dict(label=label,kind=name[len(label)+1:],snapshot_hash=before['hash'],start_J_F=float(b['sac_hooks'].force_integral),start_M=float(b['sac_hooks'].moment_integral),physical_time_at_fork=float(b['physical_now']),physics_step_at_fork=round(float(b['physical_now'])/rt.NOMINAL_PHYSICS_DT_S))
      from traction_mpc_stage4 import estimator_v2 as ma
      self.child.update(main_api_counter_at_fork=getattr(ma,'RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS',0),native_api_counter_at_fork=native_model_calls(getattr(b['lifecycle'],'_events',{})))
      self.table=table.copy();self.branch_output_dir=output;b['sac_hooks'].episode_dir=output;self.value_rows=[];self.branch_start=dict(context=c,counts=self.count.copy(),input=feature(c,table,self.count,self.carry),G_input=feature(c,np.zeros((2,5,3)),self.count,self.carry),source=source,carry=self.carry.copy());self.collect(b,c);super().choose(b,c);self.carry=table.copy();return
     except BaseException as e:save(name+'_BRANCH_ERROR.json',dict(error=str(e),traceback=traceback.format_exc()));os._exit(1)
    _,status=os.waitpid(pid,0);code=os.waitstatus_to_exitcode(status)
    result=read(name+'_DATA.json') if (L/(name+'_DATA.json')).exists() else dict(status='FAILED',exitcode=code)
    after=self.manifest(b);equal=after['hash']==before['hash'];record('END',name,status=result.get('status'),valid=result.get('metric',{}).get('valid',False),returncode=code,parent_hash_equal=equal)
    if not equal:save(name+'_PARENT_MISMATCH.json',dict(before=before,after=after));raise RuntimeError('PARENT_CHANGED_AFTER_BRANCH')
    self.branch_records.append(dict(id=name,exitcode=code,valid=result.get('metric',{}).get('valid'),parent_hash_equal=equal));save(self.group+'_BRANCH_PROGRESS.json',self.branch_records)
   self.action={};b['planner'].residual_spec={}
  if self.child is not None:self.collect(b,c)
  super().choose(b,c)
 def finish(self,env,metric):
  if self.child is not None:
   metric['actual_new_simulation_seconds']=max(0.,metric['simulation_seconds']-self.child['physical_time_at_fork']);metric['actual_new_native_physics_steps']=metric['native_physics_steps']-self.child['physics_step_at_fork']
  super().finish(env,metric)
  if self.child is not None:
   for row in self.value_rows:
    row['remaining_J_F']=metric['J_F']-row['prefix_J_F'];row['feasible_success']=bool(metric['valid'] and metric['status']=='COMPLETE')
   save(metric['name']+'_DATA.json',dict(id=metric['name'],status='COMPLETE',group=self.group,split=self.split,child=self.child,branch_start=self.branch_start,table=self.table,metric=metric,remaining_J_F=metric['J_F']-self.child['start_J_F'],remaining_M=metric['moment_integral']-self.child['start_M'],value_rows=self.value_rows,continuation='native-certified-committed-K3-suffix-v1',P_full_performance_calls=0))
  else:save(metric['name']+'_PARENT.json',dict(group=self.group,split=self.split,metric=metric,branches=self.branch_records))
