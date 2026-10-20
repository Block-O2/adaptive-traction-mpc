from study_common import *
from interfaces import TableInterface
from planning import Predictor,feature
import fork_core as fc
from accounting import record,attempts
import random,signal,traceback,gc
class BranchInterface(TableInterface):
 def __init__(self,group,split,parent_table=None,candidates=8,targets=None):
  super().__init__(parent_table);self.group=group;self.split=split;self.n_candidates=candidates;self.targets=targets or [['OUTBOUND',0],['OUTBOUND',2],['OUTBOUND',4],['RETURN',1]];self.finished=[];self.branch_output_dir=None;self.branch_records=[];self.predictor=Predictor();self.value_rows=[];self.branch_start=None
 def manifest(self,b):
  m=fc.state_manifest(b,self);m['interface_state']=dict(table=self.table,count=self.count,previous=self.previous,labels=self.labels,model_hash=self.model_hash)
  m['hash']=digest(dict(native=m['manifest'],interface=m['interface_state']));return m
 def make_plans(self,b,c,label):
  rng=np.random.default_rng(int.from_bytes(hashlib.sha256(label.encode()).digest()[:4],'little'))
  reference=np.asarray(read('HISTORICAL_K3_DESIGN_REFERENCE.json')['table']).reshape(2,5,3)
  plans=[np.zeros((2,5,3)),reference.copy()][:self.n_candidates]
  for j in range(self.n_candidates-2):
   center=reference if j%2 else np.zeros((2,5,3));noise=rng.normal(0.,.2 if j<3 else .35,(2,5,3));noise[:,1:]=.7*noise[:,:-1]+.3*noise[:,1:];plans.append(np.clip(center+noise,-1,1))
  return plans
 def choose(self,b,c):
  phase=c['phase'];idx=self.count[phase];label=self.group+'_'+phase+'_'+str(idx)
  if self.child is None and [phase,idx] in self.targets and label not in self.finished:
   self.finished.append(label);fc.quiesce(b)
   # Collect unreachable planner/logging clones BEFORE the frozen snapshot.
   # Never collect/trim between the before and after equality checks.
   import operational_memory_v3 as memory
   memory.evidence('PRE_SNAPSHOT_GC_BEGIN',label=label)
   collected=gc.collect()
   memory.evidence('PRE_SNAPSHOT_GC_END',label=label,collected=collected)
   assert 'torch' not in sys.modules,'NO_TORCH_IN_FORK_PARENT'
   before=self.manifest(b);snapshot_name=label+'_SNAPSHOT.json'
   if (L/snapshot_name).exists():snapshot_name=label+'_SNAPSHOT_restart_'+str(os.getpid())+'.json'
   save(snapshot_name,before)
   plans=self.make_plans(b,c,label)
   assert self.manifest(b)['hash']==before['hash'],'CANDIDATE_GENERATION_CHANGED_PHYSICAL_SNAPSHOT'
   evaluated=[]
   for j,table in enumerate(plans):
    if self.split!='test' and j>=4 and evaluated:
     elite=sorted([r for r in evaluated if r.get('metric',{}).get('valid')],key=lambda r:r['remaining_J_F'])[:3]
     if elite:table=np.clip(.5*np.asarray([r['table'] for r in elite]).mean(0)+.5*table,-1,1)
    guard();assert attempts()<(300 if self.split=='test' else 210),'DEVELOPMENT_PHYSICS_RESERVE'
    name=label+'_candidate'+str(j)
    completed_file=next((p for p in [L/(name+'_DATA.json'),*sorted(L.glob(name+'_retry*_DATA.json'))] if p.exists()),L/(name+'_DATA.json'))
    if completed_file.exists():
     previous_record=read(completed_file.name);previous_context=previous_record['branch_start']['context']
     assert digest(previous_context)==digest(c),'RESUME_CAUSAL_PREFIX_CHANGED'
     assert previous_record['branch_start']['counts']==self.count,'RESUME_NATIVE_COUNT_CHANGED'
     evaluated.append(previous_record);self.branch_records.append(dict(id=name,group=self.group,split=self.split,result_path=str(completed_file),valid=previous_record['metric']['valid'],skipped_completed_on_resume=True));continue
    if (O/name).exists():
     n=1
     while (O/(name+'_retry'+str(n))).exists():n+=1
     name=name+'_retry'+str(n)
    output=O/name;output.mkdir(parents=True,exist_ok=False)
    config=dict(group=self.group,split=self.split,snapshot=label,snapshot_hash=before['hash'],table=table.tolist(),continuation_version='native-certified-committed-K3-suffix-v1',information_condition='KNOWN_MODEL')
    config.update(code_manifest_sha256=getattr(self,'loaded_code_manifest_sha256',sha(STUDY/'CODE_MANIFEST.json')),V_base_version='known-effective-mechanics-analytic-native-continuation-v1')
    record('START',name,config=config,input_hash=digest(config))
    memory.evidence('PRE_BRANCH_FORK',branch=name)
    python_rng=random.getstate();numpy_rng=np.random.get_state();pid=os.fork()
    if pid==0:
     random.setstate(python_rng);np.random.set_state(numpy_rng);memory.evidence('CHILD_BEFORE_MANIFEST',branch=name);restored=self.manifest(b);memory.evidence('CHILD_AFTER_MANIFEST',branch=name)
     if restored['hash']!=before['hash']:
      save(name+'_FORK_MISMATCH.json',dict(before=before,restored=restored));os._exit(1)
     self.child=dict(label=label,kind='candidate'+str(j),snapshot_hash=before['hash'],group=self.group,split=self.split,start_task_s=c['task_s'],start_J_F=float(b['sac_hooks'].force_integral),start_M=float(b['sac_hooks'].moment_integral));self.table=table.copy();self.branch_output_dir=output;b['sac_hooks'].episode_dir=output;self.branch_start=dict(context=c,counts=self.count.copy(),input=feature(c,self.table,self.count),G_input=feature(c,np.zeros((2,5,3)),self.count));self.value_rows=[]
     self.child['kind']=name[len(label)+1:]
     self.child['loaded_code_manifest_sha256']=getattr(self,'loaded_code_manifest_sha256',None)
     from traction_mpc_stage4 import estimator_v2 as model_accounting
     self.child.update(main_api_counter_at_fork=getattr(model_accounting,'RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS',0),native_api_counter_at_fork=native_model_calls(getattr(b['lifecycle'],'_events',{})),physical_time_at_fork=float(b['physical_now']),physics_step_at_fork=round(float(b['physical_now'])/rt.NOMINAL_PHYSICS_DT_S))
     try:self.collect_value(b,c);memory.evidence('CHILD_AFTER_INITIAL_VALUE',branch=name);super().choose(b,c);return
     except BaseException as error:
      save(name+'_BRANCH_ERROR.json',dict(error=str(error),traceback=traceback.format_exc()));os._exit(1)
    _,status=os.waitpid(pid,0);code=os.waitstatus_to_exitcode(status)
    resultfile=L/(name+'_DATA.json');result=read(resultfile.name) if resultfile.exists() else dict(id=name,status='FAILED',exitcode=code,config=config)
    if result.get('metric',{}).get('valid'):evaluated.append(result)
    after=self.manifest(b)
    if after['hash']!=before['hash']:
     save(name+'_PARENT_MISMATCH.json',dict(before=before,after=after));record('END',name,status='FAILED_PARENT_MISMATCH',returncode=code);raise RuntimeError('PARENT_CHANGED_AFTER_BRANCH')
    record('END',name,status=result.get('status'),valid=result.get('metric',{}).get('valid',False),result=str(resultfile),returncode=code)
    self.branch_records.append(dict(id=name,group=self.group,split=self.split,valid=result.get('metric',{}).get('valid',False),result_path=str(resultfile),exitcode=code));save(self.group+'_BRANCH_PROGRESS.json',self.branch_records)
   self.action={};b['planner'].residual_spec={}
  if self.child is not None:self.collect_value(b,c)
  super().choose(b,c)
 def collect_value(self,b,c):
  try:
   pred=self.predictor.predict(b,c,self.table,self.count)
   self.value_rows.append(dict(input=feature(c,self.table,self.count),context=c,count=self.count.copy(),prefix_J_F=float(b['sac_hooks'].force_integral),prefix_M=float(b['sac_hooks'].moment_integral),V_base=pred['total_cost'],model_prediction=pred,continuation_version='native-certified-committed-K3-suffix-v1'))
  except (ValueError,RuntimeError) as error:self.value_rows.append(dict(context=c,count=self.count.copy(),label_error=str(error)))
 def decision_boundary(self,b):
  before=len(self.skips);super().decision_boundary(b)
  if self.child is not None and len(self.skips)>before and self.skips[-1]['reason']=='NATIVE_TERMINAL_OWNERSHIP':
   try:self.collect_value(b,self.terminal_value_context(b))
   except (ValueError,RuntimeError) as error:self.value_rows.append(dict(label_error=str(error),value_sample_role='native terminal request'))
 def finish(self,env,metric):
  if self.child is not None:
   if 'physical_time_at_fork' in self.child:
    metric['actual_new_simulation_seconds']=max(0.,metric['simulation_seconds']-self.child['physical_time_at_fork']);metric['actual_new_native_physics_steps']=metric['native_physics_steps']-self.child['physics_step_at_fork']
   else:
    metric['actual_new_simulation_seconds']=max(0.,metric['duration_s']-self.child['start_task_s']);metric['actual_new_native_physics_steps']=round(metric['actual_new_simulation_seconds']/rt.NOMINAL_PHYSICS_DT_S)
   metric['actual_new_native_control_intervals']=round(metric['actual_new_simulation_seconds']/.005)
  super().finish(env,metric)
  if self.child is not None:
   for row in self.value_rows:
    if 'input' in row:
     row['remaining_J_F']=metric['J_F']-row['prefix_J_F'];row['deltaV_label']=row['remaining_J_F']-row['V_base'];row['feasible_success']=bool(metric['valid'] and metric['status']=='COMPLETE')
   save(metric['name']+'_DATA.json',dict(id=metric['name'],status='COMPLETE',group=self.group,split=self.split,child=self.child,branch_start=self.branch_start,table=self.table,metric=metric,remaining_J_F=metric['J_F']-self.child['start_J_F'],remaining_M=metric['moment_integral']-self.child['start_M'],value_rows=self.value_rows,model_calls=self.predictor.calls,model_schedule_calls=self.predictor.schedule_calls,continuation_version='native-certified-committed-K3-suffix-v1'))
  else:save(metric['name']+'_PARENT.json',dict(group=self.group,split=self.split,metric=metric,branches=self.branch_records))
