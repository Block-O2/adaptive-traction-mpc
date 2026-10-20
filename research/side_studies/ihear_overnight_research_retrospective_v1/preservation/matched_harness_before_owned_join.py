from study_common import *
from interfaces import TableInterface
import fork_core as fc
import random,gc,traceback,signal
from native_method import NativeInterface
PACKAGE=STUDY
def put(path,value):
 path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(clean(value),indent=2,ensure_ascii=False,allow_nan=False)+'\n');tmp.replace(path)
def event(event_kind,ident,**extra):
 with (PACKAGE/'ATTEMPTS.jsonl').open('a') as f:f.write(json.dumps(clean(dict(unix=time.time(),event=event_kind,id=ident,pid=os.getpid(),**extra)))+'\n')
def records():return [json.loads(x) for x in (PACKAGE/'ATTEMPTS.jsonl').read_text().splitlines()] if (PACKAGE/'ATTEMPTS.jsonl').exists() else []
def dispatch(ident,**extra):
 guard();assert sum(r['event']=='START' for r in records())<18,'ATTEMPT_CAP';assert not any(r['event']=='START' and r['id']==ident for r in records()),'NO_REPEAT_DISPATCH';event('START',ident,**extra)
def complete_gate(a,b):
 from stream_runtime_evidence import array_items
 pa=O/a;pb=O/b;errors={};mismatch=None
 with np.load(pa/'trace.npz') as za,np.load(pb/'trace.npz') as zb:
  assert set(za.files)==set(zb.files),'TRACE_SCHEMA'
  for k in za.files:
   x=za[k];y=zb[k]
   if x.shape!=y.shape:errors[k]=dict(shape_a=x.shape,shape_b=y.shape);mismatch=mismatch or dict(variable=k,reason='shape');continue
   equal=np.array_equal(x,y,equal_nan=True) if x.dtype.kind in 'fc' else np.array_equal(x,y)
   errors[k]=dict(exact_equal=equal,max_abs_error=float(np.max(abs(x-y),initial=0)) if x.dtype.kind in 'fiu' else float(np.any(x!=y)) if x.dtype.kind=='b' else None)
   if not equal and mismatch is None:
    bad=np.flatnonzero((x!=y).reshape(len(x),-1).any(axis=1));i=int(bad[0]);mismatch=dict(variable=k,row=i,physics_s=float(za['time_s'][min(i,len(za['time_s'])-1)]),error=errors[k]['max_abs_error'])
 native_keys=['time_s','qpos_evaluation_only','qvel_evaluation_only','command_torque_nm','contact_pairs_evaluation_only','command_id','native_step_index']
 native_n=0
 import itertools
 for i,(x,y) in enumerate(itertools.zip_longest(array_items(pa/'runtime_artifacts.json.gz','native_states_evaluation_only'),array_items(pb/'runtime_artifacts.json.gz','native_states_evaluation_only'))):
  native_n+=1
  if x is None or y is None:mismatch=mismatch or dict(variable='native_states',row=i,reason='length');break
  for k in native_keys:
   if x.get(k)!=y.get(k):mismatch=mismatch or dict(variable='native.'+k,row=i,physics_s=x['time_s'],a=x.get(k),b=y.get(k))
 receipts_keys=['receipt_index','applied','start_physics_s','end_physics_s','native_steps','source_sample_time_s','command_torque_nm','q_ref_rad','dq_ref_rad_s','reference_version','validation_model_version','plan_request_id','command_kind']
 receipt_n=0
 for i,(x,y) in enumerate(itertools.zip_longest(array_items(pa/'runtime_artifacts.json.gz','command_receipts'),array_items(pb/'runtime_artifacts.json.gz','command_receipts'))):
  receipt_n+=1
  if x is None or y is None:mismatch=mismatch or dict(variable='receipts',row=i,reason='length');break
  for k in receipts_keys:
   if x.get(k)!=y.get(k):mismatch=mismatch or dict(variable='receipt.'+k,row=i,physics_s=x.get('start_physics_s'),a=x.get(k),b=y.get(k))
 ma=read(a+'.json');mb=read(b+'.json');integral_error=ma['J_F']-mb['J_F'];moment_error=ma['moment_integral']-mb['moment_integral']
 if integral_error!=0 or moment_error!=0:mismatch=mismatch or dict(variable='integrals',force_error=integral_error,moment_error=moment_error)
 out=dict(status='PASS' if mismatch is None else 'FAIL',clock='SCIENTIFIC_SIMULATION',host_clock_causal_qualification=False,branches=[a,b],trace_fields=errors,native_rows_compared=native_n,receipts_compared=receipt_n,first_mismatch=mismatch,force_integral_error_N_s=integral_error,moment_integral_error_Nm_s=moment_error,os_schedule_forked=False,opaque_handles='inherited through complete address-space fork, never rebuilt from hashes')
 put(PACKAGE/'MATCHED_STATE_VALIDATION.json',out)
 (PACKAGE/'MATCHED_STATE_VALIDATION.md').write_text('# 完整活状态复现门限\n\n'+json.dumps(clean(out),indent=2,ensure_ascii=False)+'\n')
 return out
class MatchedInterface(TableInterface):
 def __init__(self,condition,validation=False):
  super().__init__();self.condition=condition;self.validation=validation;self.carry=self.table.copy();self.fork_done=False;self.return_fork_done=False;self.branch_output_dir=None;self.policy=None;self.branch_start=None;self.parent_checks=[];self.quiescent_ready=False
 def manifest(self,b):
  m=fc.state_manifest(b,self);native=m['hash'];state=dict(table=self.table,count=self.count,previous=self.previous,labels=self.labels,skips=self.skips,model_hash=self.model_hash,carry=self.carry,last_physical_time_s=getattr(self,'last_physical_time_s',None),prefix=self.condition.get('prefix',{}))
  m['interface_scientific_state']=clean(state);m['native_hash']=native;m['hash']=digest(dict(native=m['manifest'],interface=state));return m
 def fork(self,b,tag,table=None):
  fc.quiesce(b)
  if not self.quiescent_ready:gc.collect();self.quiescent_ready=True
  assert 'torch' not in sys.modules,'SINGLE_CPU_PARENT_NO_TORCH'
  before=self.manifest(b);ident=self.condition['name']+'_'+tag;put(PACKAGE/'reports'/(ident+'_SNAPSHOT.json'),before)
  dispatch(ident,kind='RETURN_BRANCH' if tag.startswith('RETURN_entry') else 'FULL_TASK_FORK',clock='SCIENTIFIC_SIMULATION',snapshot_hash=before['hash'],seed=self.condition['seed'],table=None if table is None else np.asarray(table).tolist())
  output=O/ident;output.mkdir(exist_ok=False);prng=random.getstate();nrng=np.random.get_state();pid=os.fork()
  if pid==0:
   try:
    random.setstate(prng);np.random.set_state(nrng);restored=self.manifest(b);assert restored['hash']==before['hash'],'FORK_HASH_MISMATCH'
    put(PACKAGE/'reports'/(ident+'_FORK_RESTORED.json'),dict(status='PASS',before=before['hash'],after=restored['hash'],native_state_count=before['native_state_count'],opaque_fork_preserved=before['opaque_fork_preserved']))
    from traction_mpc_stage4 import estimator_v2 as ma
    self.child=dict(label=self.condition['name'],kind=tag,snapshot_hash=before['hash'],start_J_F=float(b['sac_hooks'].force_integral),start_M=float(b['sac_hooks'].moment_integral),physical_time_at_fork=float(b['physical_now']),physics_step_at_fork=round(float(b['physical_now'])/rt.NOMINAL_PHYSICS_DT_S),main_api_counter_at_fork=getattr(ma,'RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS',0),native_api_counter_at_fork=native_model_calls(getattr(b['lifecycle'],'_events',{})))
    self.branch_output_dir=output;b['sac_hooks'].episode_dir=output;self.branch_start=dict(clock='SCIENTIFIC_SIMULATION',phase=b['task_state'].phase.value,physical_time_s=float(b['physical_now']),native_hash=before['native_hash'],full_hash=before['hash'],native_state_mask=before['native_state_mask'],count=self.count.copy(),commissioned_beta=b['belief'].beta.copy(),commissioned_residual=b['belief'].state_residual_weights_nm.copy(),prefix=self.condition.get('prefix',{}))
    if tag=='Frozen_M2':self.policy=NativeInterface(dict(method='M2',seed=self.condition['seed'],weights=str(PACKAGE/'weights/frozen_Q_v1'),delay_replay=False,prefix=self.condition.get('prefix',{})))
    else:self.table=np.asarray(table,float).copy()
    self.action={};b['planner'].residual_spec={};return True
   except BaseException as e:
    put(PACKAGE/'reports'/(ident+'_BRANCH_ERROR.json'),dict(error=str(e),traceback=traceback.format_exc()));os._exit(1)
  _,status=os.waitpid(pid,0);code=os.waitstatus_to_exitcode(status)
  after=self.manifest(b);same=before['hash']==after['hash'];self.parent_checks.append(dict(id=ident,unchanged=same,before=before['hash'],after=after['hash'],child_exitcode=code));put(PACKAGE/'reports'/(self.condition['name']+'_PARENT_CHECKS.json'),self.parent_checks)
  event('END',ident,returncode=code,joined=True,parent_hash_equal=same)
  assert same,'PARENT_MUTATED';assert code==0,'CHILD_FAILED:'+ident
  data=read(ident+'_DATA.json');assert data['metric']['task_valid'],'NATIVE_PHYSICAL_FAILURE:'+ident
  return False
 def decision_boundary(self,b):
  phase=b['task_state'].phase.value
  if self.child is None and not self.fork_done and phase=='OUTBOUND':
   self.fork_done=True
   if self.validation:
    selection=json.loads((PACKAGE/'CANDIDATE_SELECTION.json').read_text());tag=selection['selected']
    if self.fork(b,tag,self.tables[tag]):return self.control(b)
   else:
    if not self.condition.get('prevalidated_route',False):
     for tag in ['B0_repeat_1','B0_repeat_2']:
      if self.fork(b,tag,self.tables['B0']):return self.control(b)
     gate=complete_gate('discovery_B0_repeat_1','discovery_B0_repeat_2')
    else:gate=json.loads((PACKAGE/'MATCHED_STATE_VALIDATION.json').read_text())
    assert gate['status']=='PASS','MATCHED_REPRODUCTION_FAIL'
    for tag in ['O','R','OR','Frozen_M2']:
     if self.fork(b,tag,self.tables.get(tag)):return self.control(b)
  if self.child is None and not self.validation and not self.return_fork_done and phase=='RETURN':
   self.return_fork_done=True;self.quiescent_ready=False
   for tag,table in [('RETURN_entry_zero',self.tables['B0']),('RETURN_entry_R',self.tables['R'])]:
    if self.fork(b,tag,table):return self.control(b)
  self.control(b)
 def control(self,b):
  if self.policy is not None:
   self.policy.decision_boundary(b);self.action=self.policy.action;self.labels=self.policy.labels;self.skips=self.policy.skips;self.count=self.policy.count;self.previous=self.policy.previous;self.model_hash=self.policy.model_hash;return
  phase=b['task_state'].phase.value;i=self.count.get(phase,5);prefix=self.condition.get('prefix',{})
  if phase in prefix and i<len(prefix[phase]):
   self.last_physical_time_s=float(b['physical_now']);c,reason=self.context(b)
   if c is None:raise RuntimeError('PREFIX_CONTEXT_REJECTED:'+str(reason))
   self.count[phase]+=1;self.apply(b,c,np.asarray(prefix[phase][i]),np.zeros(3));self.labels[-1].update(native_index=i,legal_shared_prefix=True);return
  super().decision_boundary(b)
 def finish(self,env,metric):
  TableInterface.finish(self,env,metric)
  if self.child is not None:
   metric['actual_new_simulation_seconds']=metric['simulation_seconds']-self.child['physical_time_at_fork'];metric['actual_new_native_physics_steps']=metric['native_physics_steps']-self.child['physics_step_at_fork']
  put(L/(metric['name']+'_DATA.json'),dict(id=metric['name'],status='COMPLETE',condition=self.condition,clock='SCIENTIFIC_SIMULATION',child=self.child,branch_start=self.branch_start,table=self.table,metric=metric,remaining_J_F=None if self.child is None else metric['J_F']-self.child['start_J_F'],remaining_M=None if self.child is None else metric['moment_integral']-self.child['start_M'],truth_firewall='fixed registered tables or frozen historical Q, evaluation truth unused for action'))
  if self.policy is not None:put(L/(metric['name']+'_SELECTIONS.json'),dict(method='Frozen_M2',rows=self.policy.search_rows,Q_calls=self.policy.network.Q_calls,Q_updates=0,G_calls=0))
def main():
 protocol=json.loads((PACKAGE/'EXPERIMENT_PROTOCOL.json').read_text());validation=len(sys.argv)>1 and sys.argv[1] not in ['discovery','discovery_continue','discovery_final']
 condition=next(r for r in protocol['validation']['conditions'] if r['name']==sys.argv[1]) if validation else dict(name='matched_discovery' if sys.argv[1]=='discovery_final' else 'discovery',seed=protocol['discovery']['seed'],prefix={},prevalidated_route=sys.argv[1]!='discovery')
 ident=condition['name']+'_parent_B0'+('_replacement' if sys.argv[1]=='discovery_continue' else '');dispatch(ident,kind='COLD_START_PARENT_FULL_TASK',clock='SCIENTIFIC_SIMULATION',condition=condition)
 random.seed(condition['seed']);np.random.seed(condition['seed']);interface=MatchedInterface(condition,validation);interface.tables={k:np.asarray(v) for k,v in protocol['candidates'].items()}
 try:
  metric=run(ident,interface,execution_mode='SCIENTIFIC_SIMULATION')
  if interface.child is not None:os._exit(0)
  event('END',ident,returncode=0,joined=True,task_valid=metric['task_valid']);assert metric['task_valid'],'NATIVE_PHYSICAL_FAILURE_PARENT'
  print(json.dumps(dict(id=ident,status='COMPLETE',J_F=metric['J_F'],attempts=sum(r['event']=='START' for r in records()))),flush=True)
 except BaseException as e:
  actual=ident if interface.child is None else interface.child['label']+'_'+interface.child['kind'];put(PACKAGE/'reports'/(actual+'_ERROR.json'),dict(error=str(e),traceback=traceback.format_exc()))
  if interface.child is not None:os._exit(1)
  event('END',ident,returncode=1,joined=True,error=str(e));raise
if __name__=='__main__':main()
