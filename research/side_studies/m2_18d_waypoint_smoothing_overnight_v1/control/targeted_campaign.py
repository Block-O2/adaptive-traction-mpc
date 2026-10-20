"""Serial, complete live-state forks; registered local shape contrasts only."""
from pathlib import Path
import os,sys,json,time,signal,traceback,hashlib,random,fcntl,shutil
P=Path(__file__).resolve().parents[1]
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TMPDIR=str(P/'tmp'),MPLCONFIGDIR=str(P/'tmp/mpl'))
sys.dont_write_bytecode=True;sys.path.insert(0,str(P/'code'));sys.path.insert(0,str(P/'control'))
import interface_base as ib
import study_common as sc,matched_harness as mh,analyze_matched as am
import numpy as np
ib.GROUP='targeted';PLAN=json.loads((P/'RUN_PLAN.json').read_text());CODE_SHA=hashlib.sha256((P/'EXECUTION_CODE_MANIFEST.json').read_bytes()).hexdigest()
def put(n,x):mh.put(P/n,x)
def append(n,x):
 with (P/n).open('a') as f:f.write(json.dumps(sc.clean(x),allow_nan=False)+'\n')
def dispatch(ident,**extra):
 n=sum(x['event']=='START' for x in mh.records());assert n<PLAN['physics_budget'],'START_CAP';assert time.time()<PLAN['dispatch_cutoff_unix']-PLAN['physical_timeout_s'],'DISPATCH_CUTOFF';assert not (P/'PHYSICS_STOP.json').exists(),'STOPPED';assert shutil.disk_usage(P).free>12*2**30,'STORAGE_CAP'
 assert not any(x['event']=='START' and x['id']==ident for x in mh.records()),'DUPLICATE_START'
 mh.event('START',ident,code_manifest_sha256=CODE_SHA,**extra);put('STATE.json',dict(status='TARGETED_PHYSICS',physics_starts=n+1,last=ident))
mh.dispatch=dispatch
def local(ident,lo,hi):
 z=np.load(P/'motion_series'/(ident+'.npz'));tr=np.load(P/'source/results'/ident/'trace.npz');m=tr['stage']=='TASK';tf=tr['time_s'][m];tf=tf-tf[0];t=z['time_s']-z['time_s'][0];sel=(t>=lo-1e-8)&(t<=hi+1e-8)
 f=np.linalg.norm(tr['physical_cuff_force_world_n'][m],axis=1);w=np.maximum(0,np.minimum(tf[1:],hi)-np.maximum(tf[:-1],lo))
 return dict(J_F=float(f[:-1]@w),TV_v=float(np.linalg.norm(np.diff(z['true_dq_rad_s'][sel],axis=0),axis=1).sum()))
class Campaign(ib.Interface):
 def __init__(self,condition):super().__init__(condition);self.current=None;self.results=[]
 def control(self,b):
  phase=b['task_state'].phase.value;planner=b['planner'];planner.residual_spec={};planner.multisegment_intent=None;self.action={};slot=self.count.get(phase,0)
  if self.child is not None and self.current and self.current['family']!='B' and phase==self.current['phase'] and slot==self.current['slot']:
   req=b['request'];planner.multisegment_intent=dict(request_id=req.request_id,source_sample_time_s=float(req.source_sample_time_s),sensor_capture_ns=int(req.sensor_capture_ns),phase=phase,phase_remaining_s=float(b['arguments']['phase_remaining_s']),perturbation_deg=[0,0],policy='motion_directed_local_waypoints_v3',outbound_slot=slot,study_spec=self.current['spec'])
  if phase in self.count:self.count[phase]+=1
 def boundary(self,b):
  super().boundary(b);prior=b['runtime'].get('reference_progress_commit')
  if prior is not None:
   def commit(receipt,original=prior,runtime=b['runtime']):
    original(receipt)
    if 'multisegment_reference' in receipt:receipt['multisegment_reference']['current_full_path_certificate']=runtime['activation_validation']['multisegment_current_path']['current_full_path_certificate']
   b['runtime']['reference_progress_commit']=commit
 def evaluate(self,b,candidate):
  ident=self.condition['name']+'_'+candidate['id'];t0=time.time()
  try:
   if self.fork(b,candidate['id'],np.zeros((2,5,3))):
    self.current=candidate;self.references={};self.sample_rows=[]
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('CHILD_TIMEOUT')));signal.alarm(PLAN['physical_timeout_s']);return True
   m=am.measure(ident);base=m if not self.results else json.loads((P/'reports/targeted_B0_MEASURED.json').read_text());comp=am.compare(m,base)
   r=dict(id=ident,candidate=candidate,status='COMPLETE',task=m['axes']['PHYSICAL_TASK_VALID'],receipt=m['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID'],safety=m['native_physical_audit']['pass_'],motion_pass=comp['acceptance_pass'],comparison=comp,J_F=m['J_F_N_s'],initial_state_hash=m['branch']['full_hash'],wall_s=time.time()-t0)
   if candidate.get('local_window_task_s'):
    lo,hi=candidate['local_window_task_s'];r['local']=local(ident,lo,hi);r['B_local']=local('targeted_B0',lo,hi)
  except BaseException as e:
   if self.child is not None:raise
   if isinstance(e,(KeyboardInterrupt,TimeoutError)):raise
   r=dict(id=ident,candidate=candidate,status='FAILED_UNRANKED',error=str(e),traceback=traceback.format_exc(),wall_s=time.time()-t0)
  self.results.append(r);append('CANDIDATE_RESULTS.jsonl',r);put('PROGRESS.json',dict(rows=self.results));print(json.dumps({k:r.get(k) for k in ['id','status','motion_pass','J_F','local','B_local','error']}),flush=True)
  return False
 def decision_boundary(self,b):
  if self.child is None and not self.fork_done and b['task_state'].phase.value=='OUTBOUND':
   self.fork_done=True;registered=json.loads((P/'EXECUTABLE_PLAN.json').read_text())
   for c in registered['coarse']:
    if self.evaluate(b,c):return self.control(b)
    r=self.results[-1]
    if c['id']=='B0':
     assert r['status']=='COMPLETE' and r['motion_pass'] and r['receipt']=='PASS' and r['safety'],'B_FAIL'
     # Verify archival B physical arrays before any intervention is dispatched.
     old=P.parent/'adaptive_continuous_coordination_optimization_v1/source/results/development_B0/trace.npz';new=P/'source/results/targeted_B0/trace.npz'
     with np.load(old) as a,np.load(new) as z:
      eq={k:bool(np.array_equal(a[k],z[k],equal_nan=True)) if a[k].dtype.kind in 'fc' else bool(np.array_equal(a[k],z[k])) for k in a.files}
     put('ARCHIVED_B_REPRODUCTION.json',dict(status='PASS' if all(eq.values()) else 'FAIL',fields=eq));assert all(eq.values()),'ARCHIVED_B_DIFFERENCE'
    if c['id'].endswith('_zero'):
     gate=ib.compare_raw('targeted_B0',r['id'],True);put(c['id']+'_ZERO_GATE.json',gate);assert gate['status']=='PASS','ZERO_SHAPE_DIFFERENCE'
   for tag in ['O','R']:
    r=next(r for r in self.results if r['candidate']['id']==tag+'_smooth')
    qualifies=r.get('status')=='COMPLETE' and r.get('motion_pass') and r.get('safety') and r.get('receipt')=='PASS'
    both=qualifies and r['local']['TV_v']<r['B_local']['TV_v']*(1-1e-6) and r['local']['J_F']<r['B_local']['J_F']-1e-8
    put(tag+'_CONDITIONAL_GATE.json',dict(qualifies=qualifies,both_motion_and_force=both,original=r))
    if not both:continue
    c=dict(r['candidate']);c['id']=tag+'_half';c['spec']={**c['spec'],'deltas_deg':(np.asarray(c['spec']['deltas_deg'])*.5).tolist()}
    put(tag+'_HALF_REGISTERED.json',dict(frozen_unix=time.time(),candidate=c,rule='predeclared half amplitude; no optimization'))
    if self.evaluate(b,c):return self.control(b)
    c=dict(r['candidate']);c['id']=tag+'_repeat'
    put(tag+'_REPEAT_REGISTERED.json',dict(frozen_unix=time.time(),candidate=c))
    if self.evaluate(b,c):return self.control(b)
    put(tag+'_REPEAT_GATE.json',ib.compare_raw(r['id'],'targeted_'+tag+'_repeat',True))
   put('PHYSICAL_ARM_RESULTS.json',dict(rows=self.results))
  self.control(b)
def main():
 assert json.loads((P/'TARGETED_MATH_TESTS.json').read_text())['status']=='PASS'
 lock=(P/'PHYSICS.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 condition=dict(name='targeted',seed=PLAN['seed'],prefix={});it=Campaign(condition);ident='targeted_parent'
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('OWNER_STOP')));signal.alarm(max(1,int(PLAN['physics_hard_stop_unix']-time.time())))
 dispatch(ident,kind='LEGAL_COLD_PARENT');random.seed(PLAN['seed']);np.random.seed(PLAN['seed'])
 try:
  m=sc.run(ident,it,execution_mode='SCIENTIFIC_SIMULATION')
  if it.child is not None:os._exit(0)
  mh.event('END',ident,returncode=0,joined=True,task_valid=m['task_valid']);assert m['task_valid'];am.measure(ident)
  gate=ib.compare_raw(ident,'targeted_B0');put('PARENT_FORK_GATE.json',gate);assert gate['status']=='PASS'
  put('PHYSICAL_DONE.json',dict(status='COMPLETE',unix=time.time(),rows=it.results,all_children_joined=True))
 except BaseException as e:
  actual=ident if it.child is None else it.child['label']+'_'+it.child['kind'];put('reports/'+actual+'_ERROR.json',dict(error=str(e),traceback=traceback.format_exc(),unix=time.time()))
  if it.child is not None:os._exit(1)
  if not any(r['event']=='END' and r['id']==ident for r in mh.records()):mh.event('END',ident,returncode=1,joined=True,error=str(e))
  put('PHYSICAL_FAILURE.json',dict(error=str(e),unix=time.time()));raise
 finally:
  if it.child is None:signal.alarm(0);put('WORKER_EXIT.json',dict(pid=os.getpid(),unix=time.time(),active_child=getattr(it,'active_owned_child_pid',None)))
if __name__=='__main__':main()
