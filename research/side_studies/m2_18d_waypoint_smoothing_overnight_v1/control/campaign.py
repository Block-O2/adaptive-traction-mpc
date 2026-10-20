"""Serial lawful full-state forks. Exact 18D intent, then certified smoothing."""
from pathlib import Path
import os,sys,json,time,signal,random,traceback,hashlib,fcntl,shutil,copy
P=Path(__file__).resolve().parents[1]
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TMPDIR=str(P/'tmp'),MPLCONFIGDIR=str(P/'tmp/mpl'))
sys.dont_write_bytecode=True;sys.path[:0]=[str(P/'code'),str(P/'control')]
import interface_base as ib
import study_common as sc, matched_harness as mh, analyze_matched as am
from interfaces import TableInterface
from rich_planner import RichFreePlanner
import numpy as np
PLAN=json.loads((P/'RUN_PLAN.json').read_text());OLD=json.loads((P/'HISTORICAL_18D_PARAMETERS.json').read_text())
GROUP=os.environ.get('STUDY_GROUP','development1');MODE=os.environ.get('STUDY_MODE','development')
def put(n,x):mh.put(P/n,x)
def append(n,x):
 with (P/n).open('a') as f:f.write(json.dumps(sc.clean(x),allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def dispatch(ident,**extra):
 rs=mh.records();n=sum(x['event']=='START' for x in rs)
 assert n<(90 if MODE=='development' else 120),'START_CAP_WITH_VALIDATION_RESERVE'
 assert time.time()<PLAN['dispatch_cutoff_unix']-PLAN['physical_timeout_s'],'NEW_START_CUTOFF'
 assert not (P/'PHYSICS_STOP.json').exists(),'STOPPED'
 assert not any(r['event']=='START' and r['id']==ident for r in rs),'DUPLICATE_START'
 size=sum(f.stat().st_size for f in P.rglob('*') if f.is_file());assert size<7.5*2**30 and shutil.disk_usage(P).free>12*2**30,'STORAGE_STOP'
 mh.event('START',ident,mode=MODE,code_manifest_sha256=sc.sha(P/'EXECUTION_CODE_MANIFEST.json'),package_bytes=size,**extra)
 put('STATE.json',dict(phase='SERIAL_'+MODE.upper(),physics_starts=n+1,last=ident,owned_pids=[os.getpid()],next_action='finish and evaluate current arm',hard_stop_unix=PLAN['hard_stop_unix']))
mh.dispatch=dispatch
def local(ident,lo,hi):
 z=np.load(P/'motion_series'/(ident+'.npz'));tr=np.load(P/'source/results'/ident/'trace.npz');m=tr['stage']=='TASK';tf=tr['time_s'][m];tf=tf-tf[0];t=z['time_s']-z['time_s'][0];sel=(t>=lo-1e-8)&(t<=hi+1e-8)
 f=np.linalg.norm(tr['physical_cuff_force_world_n'][m],axis=1);w=np.maximum(0,np.minimum(tf[1:],hi)-np.maximum(tf[:-1],lo))
 return dict(J_F=float(f[:-1]@w),TV_v=float(np.linalg.norm(np.diff(z['true_dq_rad_s'][sel],axis=0),axis=1).sum()),TV_a=float(np.linalg.norm(np.diff(z['acceleration_rad_s2'][sel],axis=0),axis=1).sum()),jerk_RMS=float(np.sqrt(np.mean(np.sum(z['jerk_rad_s3'][sel]**2,axis=1)))))
class Campaign(ib.Interface):
 def __init__(self,condition):super().__init__(condition);self.current=None;self.results=[];self.lookup={}
 def choose(self,b,c):
  # Exact historical SearchInterface.choose semantics, no table/Q training.
  candidate=self.current if self.child is not None else None
  if not candidate or candidate['base']=='B':return TableInterface.choose(self,b,c)
  ph=c['phase'];i=self.count[ph];self.count[ph]+=1
  spec=OLD.get('phases',{}).get(ph,[None]*5)[i] if i<5 else None
  if spec is None:self.apply(b,c,np.zeros(3),np.zeros(3));self.labels[-1].update(native_index=i,search_candidate=candidate['id']);return
  assert max(abs(np.asarray(spec['values'])))<=.2+1e-12
  start=c['start_m'];lo,hi=spec['support'];fraction=np.r_[lo,lo+(hi-lo)*np.asarray(spec['knots']),hi]
  knots=start+(1-start)*fraction;values=np.r_[0.,spec['values'],0.];pairs=np.column_stack([knots,values]).tolist()
  if pairs[0][0]>0:pairs=[[0.,0.]]+pairs
  if pairs[-1][0]<1:pairs=pairs+[[1.,0.]]
  a=np.asarray(pairs);assert a[0].tolist()==[0.,0.] and a[-1].tolist()==[1.,0.] and np.all(np.diff(a[:,0])>0)
  self.action={ph:pairs};b['planner'].residual_spec=self.action
  self.labels.append(dict(**c,action=[0.,0.,0.],teacher_label=[0.,0.,0.],graph=self.action,expected_delta=float(np.interp(c['nominal_m'],a[:,0],a[:,1])),native_index=i,search_candidate=candidate['id'],raw_v2=True,registered_spec=spec));self.previous=np.zeros(3)
 def control(self,b):
  phase=b['task_state'].phase.value;planner=b['planner'];slot=self.count.get(phase,0)
  if not isinstance(planner,RichFreePlanner):planner.__class__=RichFreePlanner
  planner.free_parameters=np.asarray(OLD['free_parameters'] if self.child is not None and self.current['base']=='E' else np.zeros(18),float)
  planner.multisegment_intent=None
  # Historical original control uses causal context and the native seed graph.
  mh.MatchedInterface.control(self,b)
  if self.child is not None:
   for change in self.current.get('changes',[]):
    if phase==change['phase'] and slot==change['slot']:
     req=b['request'];planner.multisegment_intent=dict(request_id=req.request_id,source_sample_time_s=float(req.source_sample_time_s),sensor_capture_ns=int(req.sensor_capture_ns),phase=phase,phase_remaining_s=float(b['arguments']['phase_remaining_s']),perturbation_deg=[0,0],policy='exact_18D_plus_bounded_motion_directed_shape',outbound_slot=slot,study_spec=change['spec'])
 def boundary(self,b):
  super().boundary(b);prior=b['runtime'].get('reference_progress_commit')
  if prior is not None:
   def commit(receipt,original=prior,runtime=b['runtime']):
    original(receipt)
    if 'multisegment_reference' in receipt:receipt['multisegment_reference']['current_full_path_certificate']=runtime['activation_validation']['multisegment_current_path']['current_full_path_certificate']
   b['runtime']['reference_progress_commit']=commit
 def evaluate(self,b,c):
  ident=GROUP+'_'+c['id'];start=time.time()
  try:
   if self.fork(b,c['id'],np.zeros((2,5,3))):
    self.current=c;self.references={};self.sample_rows=[]
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('CHILD_TIMEOUT')));signal.alarm(min(PLAN['physical_timeout_s'],max(1,int(PLAN['physics_hard_stop_unix']-time.time()))));return True
   m=am.measure(ident);bm=m if c['id']=='B0' else json.loads((P/'reports'/(GROUP+'_B0_MEASURED.json')).read_text());comp=am.compare(m,bm)
   base=GROUP+('_E0' if c['base']=='E' else '_B0');matched=m if c['id']=='E0' else json.loads((P/'reports'/(base+'_MEASURED.json')).read_text())
   paired=am.compare(m,matched)
   r=dict(id=ident,candidate=c,status='COMPLETE',task=m['axes']['PHYSICAL_TASK_VALID'],receipt=m['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID'],safety=m['native_physical_audit']['pass_'],motion_pass=comp['acceptance_pass'],comparison=comp,paired_comparison=paired,J_F=m['J_F_N_s'],matched_baseline=base,initial_state_hash=m['branch']['full_hash'],wall_s=time.time()-start,actual_new_native_steps=m['actual_new_native_steps'])
   r['local']=[dict(window=x['local_window_task_s'],candidate=local(ident,*x['local_window_task_s']),baseline=local(base,*x['local_window_task_s'])) for x in c.get('changes',[])]
   r['reference_object_count']=len(json.loads((P/'output'/(ident+'_REFERENCE_OBJECTS.json')).read_text())['references'])
   if c.get('changes'):assert r['reference_object_count']==len(c['changes']),'TARGETED_REFERENCE_NOT_EXECUTED'
  except BaseException as e:
   if self.child is not None or isinstance(e,(KeyboardInterrupt,TimeoutError)):raise
   r=dict(id=ident,candidate=c,status='FAILED_UNRANKED',error=str(e),traceback=traceback.format_exc(),wall_s=time.time()-start)
   if 'PARENT_MUTATED' in str(e) or 'FORK_HASH' in str(e):raise
  self.results.append(r);append('EXPLORATION_RESULTS.jsonl',r);put('PROGRESS.json',dict(rows=self.results))
  print(json.dumps({k:r.get(k) for k in ['id','status','motion_pass','J_F','local','error']}),flush=True)
  return False
 def decision_boundary(self,b):
  if self.child is None and not self.fork_done and b['task_state'].phase.value=='OUTBOUND':
   self.fork_done=True;registered=json.loads((P/'EXECUTABLE_PLAN.json').read_text())
   for c in registered['coarse']:
    if self.evaluate(b,c):return self.control(b)
    r=self.results[-1]
    if c['id'] in ['B0','E0']:
     assert r['status']=='COMPLETE' and r['motion_pass'] and r['receipt']=='PASS' and r['safety'],'BASELINE_FAIL'
     old=P.parent/'ihear_overnight_research_retrospective_v1/source/results'/('development_repair2_B0_original' if c['id']=='B0' else 'development_repair2_quality_NATIVE_SCALAR_18_063')/'trace.npz'
     with np.load(old) as a,np.load(P/'source/results'/r['id']/'trace.npz') as z:
      eq={k:bool(np.array_equal(a[k],z[k],equal_nan=True)) if a[k].dtype.kind in 'fc' else bool(np.array_equal(a[k],z[k])) for k in a.files}
     put('audit/'+r['id']+'_ARCHIVE_GATE.json',dict(status='PASS' if all(eq.values()) else 'FAIL',fields=eq));assert all(eq.values()),'ARCHIVAL_IDENTITY_DIFFERENCE'
    if c['id'].endswith('_zero'):
     gate=ib.compare_raw(GROUP+('_E0' if c['base']=='E' else '_B0'),r['id'],True);put(c['id']+'_ZERO_GATE.json',gate);assert gate['status']=='PASS','ZERO_SHAPE_DIFFERENCE'
   # The registered first batch ends for evidence review, no automatic blind sweep.
   put(GROUP+'_PHYSICAL_ARM_RESULTS.json',dict(rows=self.results))
  self.control(b)
def main():
 assert json.loads((P/'PREPHYSICAL_CHECKS.json').read_text())['status']=='PASS'
 lock=(P/'PHYSICS.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 it=Campaign(dict(name=GROUP,seed=PLAN['seed'],prefix={}));ident=GROUP+'_parent'
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('OWNER_STOP')));signal.alarm(max(1,int(PLAN['physics_hard_stop_unix']-time.time())))
 dispatch(ident,kind='LEGAL_COLD_PARENT');random.seed(PLAN['seed']);np.random.seed(PLAN['seed'])
 try:
  m=sc.run(ident,it,execution_mode='SCIENTIFIC_SIMULATION')
  if it.child is not None:os._exit(0)
  mh.event('END',ident,returncode=0,joined=True,task_valid=m['task_valid']);assert m['task_valid'];am.measure(ident)
  gate=ib.compare_raw(ident,GROUP+'_B0');put(GROUP+'_PARENT_FORK_GATE.json',gate);assert gate['status']=='PASS'
  put(GROUP+'_PHYSICAL_DONE.json',dict(status='COMPLETE',unix=time.time(),rows=it.results,all_children_joined=True))
 except BaseException as e:
  actual=ident if it.child is None else it.child['label']+'_'+it.child['kind'];put('reports/'+actual+'_ERROR.json',dict(error=str(e),traceback=traceback.format_exc(),unix=time.time()))
  if it.child is not None:os._exit(1)
  if not any(r['event']=='END' and r['id']==ident for r in mh.records()):mh.event('END',ident,returncode=1,joined=True,error=str(e))
  put(GROUP+'_PHYSICAL_FAILURE.json',dict(error=str(e),unix=time.time()));raise
 finally:
  if it.child is None:signal.alarm(0);put(GROUP+'_WORKER_EXIT.json',dict(pid=os.getpid(),unix=time.time(),active_child=getattr(it,'active_owned_child_pid',None)))
if __name__=='__main__':main()
