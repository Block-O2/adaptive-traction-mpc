"""Frozen candidates at one preregistered new legal prefix; no model updates."""
from pathlib import Path
import os,sys,json,time,signal,random,traceback,fcntl,hashlib,datetime,copy,inspect,textwrap
P=Path(__file__).resolve().parents[1];R=P/'runtime';sys.path.insert(0,str(P/'source'))
import study_worker as sw
from study_worker import sc,mh,am,frozen,np
GROUP='FROZEN_NEW_PREFIX';CONFIG=json.loads((P/'FROZEN_NEW_PREFIX_PLAN.json').read_text())
sw.GROUP=GROUP;sw.CONFIG=CONFIG;frozen.GROUP=GROUP
# Change only the same-chain baseline report path. Formula/thresholds stay exact.
original=inspect.getsource(sw.Study.run_branch);assert original.count('OPTIMIZATION_B_MEASURED.json')==1
adapted=textwrap.dedent(original).replace('OPTIMIZATION_B_MEASURED.json','FROZEN_NEW_PREFIX_B_MEASURED.json')
ns=sw.__dict__;exec(compile(adapted,'<frozen new-prefix own B provenance binding>','exec'),ns);bound_run_branch=ns['run_branch']

def dispatch(ident,**kw):
 for rel,h in json.loads((P/'VALIDATION_SOURCE_MANIFEST.json').read_text())['files'].items():assert sc.sha(P/rel)==h,'VALIDATION_SOURCE_CHANGED:'+rel
 sw.dispatch(ident,validation_source_sha256=sc.sha(P/'VALIDATION_SOURCE_MANIFEST.json'),**kw)
mh.dispatch=dispatch

class Validation(sw.Study):
 run_branch=bound_run_branch
 def decision_boundary(self,b):
  if self.child is None and not self.fork_done and b['task_state'].phase.value=='OUTBOUND' and self.count['OUTBOUND']>=1:
   self.fork_done=True;signal.alarm(max(1,int(sw.PLAN['physics_hard_stop_unix']-time.time())))
   sw.put('audit/FROZEN_NEW_PREFIX_CONTEXT.json',{'physical_s':b['physical_now'],'causal_estimated_state':b['observation'].as_array(),'commissioned_belief':b['belief'].value_state_record(),'condition':CONFIG['condition'],'all_candidates_frozen_before_this_parent':True})
   nativeB=copy.deepcopy(CONFIG['arms'][0]);H=copy.deepcopy(CONFIG['arms'][1]);lock=json.loads((P/'FINAL_SELECTION_BEFORE_VALIDATION.json').read_text())
   for tag,c in [('B',nativeB),('H150',H)]:
    if self.run_branch(b,tag,c,[0,0],'validation'):return self.control(b)
    if tag=='B':assert self.last_row['qualified'],'NEW_PREFIX_B_NOT_QUALIFIED'
   for arm in 'ABC':
    chosen=lock['locked'][arm]
    if chosen is None:continue
    pred=copy.deepcopy(chosen['prediction']);pred.update(validation_only=True,original_training_id=chosen['id'],new_prefix_preregistered=True,no_model_update=True,current_context_generalization_validated=False)
    if self.run_branch(b,'LOCKED_'+arm,H,chosen['x'],'validation',pred):return self.control(b)
   sw.put('FROZEN_NEW_PREFIX_RESULTS.json',{'status':'EXECUTED_WITH_ALL_RESULTS_PRESERVED','condition':CONFIG['condition'],'rows':self.metrics,'all_parent_unchanged':all(x['unchanged'] for x in self.parent_checks),'model_updates':0,'same_patient_one_new_legal_prefix_only':True})
  self.control(b)

def main():
 assert json.loads((P/'audit/OPTIMIZATION_DONE.json').read_text())['status']=='PASS_EXECUTED','OPTIMIZATION_MUST_CLOSE_FIRST'
 lock=(P/'PHYSICS.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('OWNED_VALIDATION_TIMEOUT')));signal.alarm(max(1,int(sw.PLAN['physics_hard_stop_unix']-time.time())))
 sw.put('audit/VALIDATION_BASELINE_BINDING.json',{'original_sha256':hashlib.sha256(original.encode()).hexdigest(),'adapted_sha256':hashlib.sha256(adapted.encode()).hexdigest(),'only_change':'current new-prefix own B report path; no formulas/thresholds/physics changes'})
 it=Validation();ident=GROUP+'_parent';sw.CATEGORY='engineering';start=time.time();dispatch(ident,kind='NEW_LEGAL_PREFIX_COLD_PARENT');random.seed(CONFIG['condition']['seed']);np.random.seed(CONFIG['condition']['seed'])
 try:
  m=sc.run(ident,it,execution_mode='SCIENTIFIC_SIMULATION')
  if it.child is not None:os._exit(0)
  mh.event('END',ident,returncode=0,joined=True,native_steps=m['actual_new_native_physics_steps'],wall_seconds=time.time()-start)
  am.measure(ident);gate=frozen.bc.compare_raw(R/'source/results'/ident,R/'source/results'/(GROUP+'_B'));sw.put('audit/FROZEN_NEW_PREFIX_PARENT_RAW_GATE.json',gate);assert gate['status']=='PASS','NEW_PREFIX_PARENT_B_RAW_MISMATCH'
  sw.put('audit/FROZEN_NEW_PREFIX_DONE.json',{'status':'PASS_EXECUTED','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'all_children_joined':True,'parent_checks':it.parent_checks,'wall_s':time.time()-start})
 except BaseException as error:
  actual=ident if it.child is None else it.child['label']+'_'+it.child['kind'];sw.put('audit/'+actual+'_ERROR.json',{'error':str(error),'traceback':traceback.format_exc()})
  if it.child is not None:os._exit(1)
  if not any(r['event']=='END' and r['id']==ident for r in mh.records()):mh.event('END',ident,returncode=1,joined=True,error=str(error))
  sw.put('audit/FROZEN_NEW_PREFIX_DONE.json',{'status':'FAILED_PRESERVED','error':str(error),'rows':it.metrics});raise
 finally:
  if it.child is None:signal.alarm(0);sw.put('audit/FROZEN_NEW_PREFIX_OWNER_EXIT.json',{'pid':os.getpid(),'active_child':getattr(it,'active_owned_child_pid',None),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
if __name__=='__main__':main()
