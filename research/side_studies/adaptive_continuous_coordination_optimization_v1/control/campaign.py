"""Serial matched-state physical sensitivity campaign; all STARTs are counted."""
from pathlib import Path
import os,sys,json,time,signal,traceback,hashlib,random,fcntl,shutil
P=Path(__file__).resolve().parents[1]
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TMPDIR=str(P/'tmp'),MPLCONFIGDIR=str(P/'tmp/mpl'))
sys.dont_write_bytecode=True;sys.path.insert(0,str(P/'code'));sys.path.insert(0,str(P/'control'))
import interface_base as ib
import study_common as sc,matched_harness as mh,analyze_matched as am
import numpy as np
ib.GROUP='development'
PLAN=json.loads((P/'RUN_PLAN.json').read_text());MANIFEST_SHA=hashlib.sha256((P/'EXECUTION_CODE_MANIFEST.json').read_bytes()).hexdigest()
def put(n,x):mh.put(P/n,x)
def append(n,x):
 with (P/n).open('a') as f:f.write(json.dumps(sc.clean(x),allow_nan=False)+'\n')
def dispatch(ident,**extra):
 n=sum(x['event']=='START' for x in mh.records());assert n<PLAN['physics_budget'],'START_CAP';assert time.time()<PLAN['dispatch_cutoff_unix']-PLAN['physical_timeout_s'],'DISPATCH_CUTOFF';assert not (P/'PHYSICS_STOP.json').exists(),'STOPPED';assert shutil.disk_usage(P).free>12*2**30,'STORAGE_CAP'
 assert not any(x['event']=='START' and x['id']==ident for x in mh.records()),'DUPLICATE_START'
 mh.event('START',ident,code_manifest_sha256=MANIFEST_SHA,**extra);put('STATE.json',dict(status='PHYSICAL_SENSITIVITY',physics_starts=n+1,last=ident,wall_remaining_s=PLAN['physics_hard_stop_unix']-time.time()))
mh.dispatch=dispatch
def spec(fracs,deltas,times=None):
 d=dict(fractions=fracs,deltas_deg=deltas)
 if times is not None:d['time_fractions']=times
 return d
class Campaign(ib.Interface):
 def __init__(self,condition):super().__init__(condition);self.current=None;self.results=[]
 def control(self,b):
  phase=b['task_state'].phase.value;planner=b['planner'];planner.residual_spec={};planner.multisegment_intent=None;self.action={};slot=self.count.get(phase,0)
  if self.child is not None and self.current and self.current['family']!='B' and phase=='OUTBOUND' and slot==1:
   req=b['request'];planner.multisegment_intent=dict(request_id=req.request_id,source_sample_time_s=float(req.source_sample_time_s),sensor_capture_ns=int(req.sensor_capture_ns),phase=phase,phase_remaining_s=float(b['arguments']['phase_remaining_s']),perturbation_deg=self.current.get('legacy_delta',[0,0]),policy='bounded_density_timing_research_v1',outbound_slot=slot)
   if self.current.get('spec') is not None:planner.multisegment_intent['study_spec']=self.current['spec']
  if phase in self.count:self.count[phase]+=1
 def boundary(self,b):
  super().boundary(b)
  prior=b['runtime'].get('reference_progress_commit')
  if prior is not None:
   def commit(receipt,original=prior,runtime=b['runtime']):
    original(receipt)
    if 'multisegment_reference' in receipt:
     receipt['multisegment_reference']['current_full_path_certificate']=runtime['activation_validation']['multisegment_current_path']['current_full_path_certificate']
   b['runtime']['reference_progress_commit']=commit
 def evaluate(self,b,candidate):
  tag=candidate['id'];ident=self.condition['name']+'_'+tag;t=time.time()
  try:
   if self.fork(b,tag,np.zeros((2,5,3))):
    self.current=candidate;self.references={};self.sample_rows=[]
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('CHILD_TIMEOUT')));signal.alarm(PLAN['physical_timeout_s']);return True
   m=am.measure(ident);base=m if not self.results else json.loads((P/'reports/development_B0_MEASURED.json').read_text());comparison=am.compare(m,base)
   r=dict(id=ident,parent_id=self.condition['name']+'_parent',candidate=candidate,status='COMPLETE',task=m['axes']['PHYSICAL_TASK_VALID'],receipt=m['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID'],motion_pass=comparison['acceptance_pass'],J_F_N_s=m['J_F_N_s'],phase_J_F=m['phase_cost']['phases'],comparison=comparison,tracking_RMS_deg=m['tracking_RMS_deg'],moment_integral_Nm_s=m['moment_integral_Nm_s'],native_physical_audit=m['native_physical_audit'],initial_state_identity=m['branch']['full_hash'],native_steps=m['actual_new_native_steps'],wall_s=time.time()-t)
   z=np.load(P/'motion_series'/(ident+'.npz'));v=z['true_dq_rad_s'];r['velocity_TV_combined']=float(np.sum(np.linalg.norm(np.diff(v,axis=0),axis=1)));r['jerk_RMS_combined']=float(np.sqrt(np.mean(np.sum(z['jerk_rad_s3']**2,axis=1))))
  except BaseException as e:
   if self.child is not None:raise
   if isinstance(e,(KeyboardInterrupt,TimeoutError)):raise
   r=dict(id=ident,parent_id=self.condition['name']+'_parent',candidate=candidate,status='FAILED_UNRANKED',error=str(e),traceback=traceback.format_exc(),wall_s=time.time()-t)
  self.results.append(r);append('CANDIDATE_RESULTS.jsonl',r);append('EXPLORATION_RESULTS.jsonl',r);put('PROGRESS.json',dict(rows=self.results));print(json.dumps({k:r.get(k) for k in ['id','status','motion_pass','J_F_N_s','velocity_TV_combined','error']}),flush=True)
  return False
 def decision_boundary(self,b):
  if self.child is None and not self.fork_done and b['task_state'].phase.value=='OUTBOUND':
   self.fork_done=True
   plan=json.loads((P/'CANDIDATE_PLAN.json').read_text())
   for c in plan['coarse']:
    if self.evaluate(b,c):return self.control(b)
    if c['id']=='legacy005_repeat':put('ANOMALY_REPEAT_GATE.json',ib.compare_raw('development_legacy005','development_legacy005_repeat',True))
   # Refine only if a physically feasible candidate improves force and does not worsen velocity TV >1%.
   base=self.results[0];good=[r for r in self.results if r.get('motion_pass') and r.get('J_F_N_s',float('inf'))<base['J_F_N_s']-1e-5 and r['velocity_TV_combined']<=base['velocity_TV_combined']*1.01]
   if good:
    best=min(good,key=lambda r:r['J_F_N_s']);c=dict(best['candidate']);c['id']='selected_repeat'
    put('PRE_REPEAT_SELECTION.json',dict(selected=best['id'],candidate=c,rule='force feasible first, velocity TV <=1.01 B',not_heldout=True))
    if self.evaluate(b,c):return self.control(b)
    put('SELECTED_REPEAT_GATE.json',ib.compare_raw(best['id'],'development_selected_repeat',True))
   put('PHYSICAL_ARM_RESULTS.json',dict(rows=self.results));put('SENSITIVITY_RESULTS.json',dict(rows=self.results,physics_start_denominator=sum(x['event']=='START' for x in mh.records()),adaptive_plan=json.loads((P/'ADAPTIVE_REFINEMENT_PLAN.json').read_text())))
  self.control(b)
def main():
 assert json.loads((P/'CERTIFICATION_TEST_RESULTS.json').read_text())['status']=='PASS';assert json.loads((P/'DENSITY_MATH_TESTS.json').read_text())['status']=='PASS'
 lock=(P/'PHYSICS.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 condition=dict(name='development',seed=PLAN['seed'],prefix={});interface=Campaign(condition);ident='development_parent'
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('OWNER_HARD_STOP')));signal.alarm(max(1,int(PLAN['physics_hard_stop_unix']-time.time())))
 dispatch(ident,kind='LEGAL_COLD_PARENT');random.seed(PLAN['seed']);np.random.seed(PLAN['seed'])
 try:
  m=sc.run(ident,interface,execution_mode='SCIENTIFIC_SIMULATION')
  if interface.child is not None:os._exit(0)
  mh.event('END',ident,returncode=0,joined=True,task_valid=m['task_valid']);assert m['task_valid'];am.measure(ident);put('PARENT_FORK_GATE.json',ib.compare_raw(ident,'development_B0'))
  put('PHYSICAL_DONE.json',dict(status='COMPLETE',unix=time.time(),rows=interface.results,all_children_joined=True))
 except BaseException as e:
  actual=ident if interface.child is None else interface.child['label']+'_'+interface.child['kind'];put('reports/'+actual+'_ERROR.json',dict(error=str(e),traceback=traceback.format_exc(),unix=time.time()))
  if interface.child is not None:os._exit(1)
  if not any(r['event']=='END' and r['id']==ident for r in mh.records()):mh.event('END',ident,returncode=1,joined=True,error=str(e))
  put('PHYSICAL_FAILURE.json',dict(reason=str(e),unix=time.time()));raise
 finally:
  if interface.child is None:signal.alarm(0);put('control/WORKER_EXIT.json',dict(pid=os.getpid(),unix=time.time(),active_child=getattr(interface,'active_owned_child_pid',None)))
if __name__=='__main__':main()
