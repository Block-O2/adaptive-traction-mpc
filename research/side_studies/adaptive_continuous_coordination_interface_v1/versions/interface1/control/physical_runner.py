"""One serial owner: B, zero multi, bounded single-knot demo, one repeat."""
from pathlib import Path
import os,sys,json,time,random,signal,fcntl,traceback,hashlib,copy,itertools
P=Path(__file__).resolve().parents[1]
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TMPDIR=str(P/'tmp'),MPLCONFIGDIR=str(P/'tmp/mpl'))
sys.dont_write_bytecode=True;sys.path.insert(0,str(P/'code'))
import study_common as sc
import matched_harness as mh
import analyze_matched as am
import numpy as np
from traction_mpc_stage5.full3d_adaptive_integration_v1.multisegment_reference import MultiSegmentReference,primitive,digest
from stream_runtime_evidence import array_items
PLAN=json.loads((P/'RUN_PLAN.json').read_text());GROUP=sys.argv[1] if len(sys.argv)>1 else 'interface1'
CODE=json.loads((P/'EXECUTION_CODE_MANIFEST.json').read_text());CODE_SHA=hashlib.sha256((P/'EXECUTION_CODE_MANIFEST.json').read_bytes()).hexdigest()
def put(n,x):mh.put(P/n,x)
def dispatch(ident,**extra):
 n=sum(r['event']=='START' for r in mh.records());assert n<24,'24_START_CAP';assert time.time()<PLAN['dispatch_cutoff_unix']-PLAN['physical_timeout_s'],'NEW_START_CUTOFF'
 assert not (P/'PHYSICS_STOP.json').exists(),'CAMPAIGN_STOPPED'
 assert not any(r['event']=='START' and r['id']==ident for r in mh.records()),'DUPLICATE_ATTEMPT'
 import shutil
 size=sum(f.stat().st_size for f in P.rglob('*') if f.is_file());assert size<7*2**30 and shutil.disk_usage(P).free>10*2**30,'STORAGE_STOP'
 mh.event('START',ident,code_manifest_sha256=CODE_SHA,source_manifest='EXECUTION_CODE_MANIFEST.json',mode='INTERFACE_QUALIFICATION_NO_FORCE_SEARCH',**extra)
 state=json.loads((P/'STATE.json').read_text());state.update(phase='SERIAL_PHYSICAL_INTERFACE_GATES',physics_starts=n+1,owned_pids=[os.getpid()],last_checkpoint=ident,next_allowed_action='finish owned attempt and apply next gate',remaining_to_dispatch_cutoff_s=PLAN['dispatch_cutoff_unix']-time.time());put('STATE.json',state)
mh.dispatch=dispatch

def compare_raw(a,b,allow_reference_identity=False):
 pa=P/'source/results'/a;pb=P/'source/results'/b;errors=[];identity_differences=[]
 with np.load(pa/'trace.npz') as x,np.load(pb/'trace.npz') as y:
  if set(x.files)!=set(y.files):errors.append('TRACE_SCHEMA')
  else:
   for k in x.files:
    same=x[k].shape==y[k].shape and (np.array_equal(x[k],y[k],equal_nan=True) if x[k].dtype.kind in 'fc' else np.array_equal(x[k],y[k]))
    if not same:errors.append('TRACE:'+k)
 native=receipts=0
 for x,y in itertools.zip_longest(array_items(pa/'runtime_artifacts.json.gz','native_states_evaluation_only'),array_items(pb/'runtime_artifacts.json.gz','native_states_evaluation_only')):
  native+=1
  if x is None or y is None:errors.append('NATIVE_LENGTH');break
  for k in ['time_s','qpos_evaluation_only','qvel_evaluation_only','command_torque_nm','contact_pairs_evaluation_only']:
   if x[k]!=y[k]:errors.append('NATIVE:'+k);break
 keys=['applied','start_physics_s','end_physics_s','native_steps','source_sample_time_s','command_torque_nm','q_ref_rad','dq_ref_rad_s','validation_model_version','plan_request_id','command_kind','reference_version']
 for x,y in itertools.zip_longest(array_items(pa/'runtime_artifacts.json.gz','command_receipts'),array_items(pb/'runtime_artifacts.json.gz','command_receipts')):
  receipts+=1
  if x is None or y is None:errors.append('RECEIPT_LENGTH');break
  for k in keys:
   if x.get(k)!=y.get(k):
    if k=='reference_version' and allow_reference_identity:identity_differences.append(dict(receipt=receipts,a=x.get(k),b=y.get(k)))
    else:errors.append('RECEIPT:'+k)
 return dict(status='PASS' if not errors else 'FAIL',a=a,b=b,errors=sorted(set(errors)),native_rows=native,receipts=receipts,reference_identity_differences=identity_differences,scope='all archived physical control fields and native body/torque/contact; wall profiling excluded',zero_multisegment_not_collapsed=True)

class Interface(mh.MatchedInterface):
 def __init__(self,condition):
  super().__init__(condition);self.policy_kind=None;self.perturbation=0.;self.references={};self.sample_rows=[];self.metrics=[];self.target_outbound_slot=1
 def control(self,b):
  phase=b['task_state'].phase.value;planner=b['planner'];planner.residual_spec={};self.action={};planner.multisegment_intent=None
  slot=self.count.get(phase,0)
  if self.child is not None and self.policy_kind in ['ZERO','NONZERO'] and phase=='OUTBOUND' and slot==self.target_outbound_slot:
   req=b['request'];planner.multisegment_intent=dict(request_id=req.request_id,source_sample_time_s=float(req.source_sample_time_s),sensor_capture_ns=int(req.sensor_capture_ns),phase=phase,phase_remaining_s=float(b['arguments']['phase_remaining_s']),perturbation_deg=[0.,self.perturbation],policy='single_internal_knee_position_only',outbound_slot=slot)
  if phase in self.count:self.count[phase]+=1
 def decision_boundary(self,b):
  if self.child is None and not self.fork_done and b['task_state'].phase.value=='OUTBOUND':
   self.fork_done=True
   rows=[('B0','B',0.),('zero_multi','ZERO',0.),('knee_005','NONZERO',.05)]
   for tag,kind,amplitude in rows:
    if self.eval_arm(b,tag,kind,amplitude):return self.control(b)
    if tag=='zero_multi':
     gate=compare_raw(GROUP+'_B0',GROUP+'_zero_multi',allow_reference_identity=True);put('P0_ZERO_PHYSICAL_GATE.json',gate);assert gate['status']=='PASS','P0_ZERO_PHYSICAL_DIFFERENCE'
    if tag=='knee_005':
     row=self.metrics[-1]
     if row['motion']['acceptance_pass']:
      if self.eval_arm(b,'knee_005_repeat','NONZERO',.05):return self.control(b)
      repeat=compare_raw(GROUP+'_knee_005',GROUP+'_knee_005_repeat',allow_reference_identity=True);put('NONZERO_REPEAT_GATE.json',repeat);assert repeat['status']=='PASS','NONZERO_REPEAT_DIFFERENCE'
     else:
      # Qualification-only reduction, never choose by force.
      for amp,smalltag in [(.02,'knee_002'),(.01,'knee_001')]:
       if self.eval_arm(b,smalltag,'NONZERO',amp):return self.control(b)
       if self.metrics[-1]['motion']['acceptance_pass']:break
   put('PHYSICAL_ARM_RESULTS.json',dict(rows=self.metrics,not_force_optimization=True))
  self.control(b)
 def eval_arm(self,b,tag,kind,amplitude):
  # Each fork inherits the identical full parent before any TASK action.
  if self.fork(b,tag,np.zeros((2,5,3))):
   self.policy_kind=kind;self.perturbation=amplitude;self.references={};self.sample_rows=[]
   signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('OWNED_PHYSICAL_TIMEOUT')));signal.alarm(PLAN['physical_timeout_s']);return True
  ident=GROUP+'_'+tag;m=am.measure(ident);base=m if not self.metrics else json.loads((P/'reports'/(GROUP+'_B0_MEASURED.json')).read_text());comparison=am.compare(m,base)
  row=dict(id=ident,kind=kind,perturbation_deg=[0,amplitude],J_F_N_s=m['J_F_N_s'],task=m['axes']['PHYSICAL_TASK_VALID'],receipt=m['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID'],motion=comparison,source_parent=GROUP+'_parent',actual_new_native_steps=m['actual_new_native_steps']);self.metrics.append(row)
  put('PHYSICAL_PROGRESS.json',dict(rows=self.metrics));print(json.dumps(dict(id=ident,task=row['task'],receipt=row['receipt'],motion_pass=comparison['acceptance_pass'],failed=comparison['failed_requirements'],J_F=m['J_F_N_s'])),flush=True)
  return False
 def boundary(self,b):
  sc.Interface.boundary(self,b)
  active=b.get('active_schedule');multi=None;local=None
  proposal=b.get('progress_proposal')
  if proposal is not None:
   progress=float(proposal['selected_progress_s'])
   if isinstance(active,MultiSegmentReference):multi=active;local=progress
   elif isinstance(getattr(active,'suffix',None),MultiSegmentReference) and progress>active.splice_elapsed_s+1e-12:multi=active.suffix;local=progress-active.splice_elapsed_s
  if multi is None:return
  multi.assert_integrity();actual=b['reference'];expected=multi.sample(local)
  errors=[float(np.max(abs(getattr(actual,k)-getattr(expected,k)))) for k in ['q_rad','dq_rad_s','ddq_rad_s2']];assert max(errors)<=1e-10,'ISSUED_REFERENCE_NOT_CERTIFIED_OBJECT'
  self.references[multi.sealed_digest]=primitive(multi.record())
  row=dict(time_s=float(b['physical_now']),task_s=float(b['physical_now']-b['task_start_time']),reference_id=multi.sealed_digest,worker_certificate_id=multi.sealed_certificate_id,selected_local_progress_s=local,segment_index=min(len(multi.segments)-1,int(np.searchsorted(multi.knots_s,local,side='right')-1)),q_rad=actual.q_rad.tolist(),dq_rad_s=actual.dq_rad_s.tolist(),ddq_rad_s2=actual.ddq_rad_s2.tolist(),sample_error=errors,source_sample_time_s=json.loads(multi.binding_json)['source_sample_time_s'],source_capture_ns=json.loads(multi.binding_json)['sensor_capture_ns'],current_model_sequence=int(b['belief'].sequence))
  self.sample_rows.append(row)
  runtime=b['runtime'];prior=runtime.get('reference_progress_commit');assert prior is not None,'MISSING_ORIGINAL_RECEIPT_PROGRESS_COMMIT'
  def commit(receipt,original=prior,record=row.copy(),runtime=runtime):
   original(receipt)
   validation=runtime.get('activation_validation',{}).get('multisegment_current_path',{})
   assert validation.get('reference_id')==record['reference_id'] and validation.get('feasible'),'MISSING_CURRENT_MULTISEGMENT_ADMISSION'
   receipt['multisegment_reference']=dict(**record,current_certificate_id=validation['current_certificate_id'])
  runtime['reference_progress_commit']=commit
 def finish(self,env,metric):
  super().finish(env,metric)
  name=metric['name'];put('output/'+name+'_REFERENCE_OBJECTS.json',dict(references=self.references,mathematical_and_certified_same_object=True));put('output/'+name+'_ISSUED_REFERENCE.json',dict(rows=self.sample_rows,applied_requires_actual_receipt_and_positive_native_steps=True))

def main():
 assert json.loads((P/'CERTIFICATION_TEST_RESULTS.json').read_text())['status']=='PASS'
 lock=(P/'PHYSICS.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 condition=dict(name=GROUP,seed=PLAN['seed'],prefix={});interface=Interface(condition);ident=GROUP+'_parent'
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('ABSOLUTE_OWNER_STOP')));signal.alarm(max(1,int(min(2400,PLAN['physics_hard_stop_unix']-time.time()))))
 dispatch(ident,kind='LEGAL_COLD_PARENT');random.seed(PLAN['seed']);np.random.seed(PLAN['seed'])
 try:
  m=sc.run(ident,interface,execution_mode='SCIENTIFIC_SIMULATION')
  if interface.child is not None:os._exit(0)
  mh.event('END',ident,returncode=0,joined=True,task_valid=m['task_valid']);assert m['task_valid'];am.measure(ident)
  gate=compare_raw(ident,GROUP+'_B0');put('PARENT_FORK_GATE.json',gate);assert gate['status']=='PASS'
  put('PHYSICAL_DONE.json',dict(status='COMPLETE',unix=time.time(),rows=interface.metrics,all_children_joined=True))
 except BaseException as e:
  actual=ident if interface.child is None else interface.child['label']+'_'+interface.child['kind'];put('reports/'+actual+'_ERROR.json',dict(unix=time.time(),error=str(e),traceback=traceback.format_exc()))
  if interface.child is not None:os._exit(1)
  if not any(r['event']=='END' and r['id']==ident for r in mh.records()):mh.event('END',ident,returncode=1,joined=True,error=str(e))
  put('PHYSICAL_FAILURE.json',dict(unix=time.time(),reason=str(e),attempts=sum(r['event']=='START' for r in mh.records())));raise
 finally:
  if interface.child is None:
   signal.alarm(0);put('control/WORKER_EXIT_'+GROUP+'.json',dict(pid=os.getpid(),unix=time.time(),active_child=getattr(interface,'active_owned_child_pid',None)))
if __name__=='__main__':main()
