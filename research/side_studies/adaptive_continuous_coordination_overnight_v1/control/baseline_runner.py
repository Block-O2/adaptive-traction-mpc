"""Owned serial baseline audit only; nonzero new representation never admitted."""
from pathlib import Path
import os,sys,json,time,random,signal,traceback,fcntl,hashlib
P=Path(__file__).resolve().parents[1]
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TMPDIR=str(P/'tmp'),MPLCONFIGDIR=str(P/'tmp/mpl'))
sys.dont_write_bytecode=True;sys.path[:0]=[str(P/'prototype'),str(P/'code')]
import study_common as sc
import runner as base
from rich_planner import RichFreePlanner
from continuous import LocalQuintic,Piece
import numpy as np
PLAN=json.loads((P/'RUN_PLAN.json').read_text());base.MODE='baseline_gate';base.P=PLAN
base.SCALES=np.ones(18)
class ExactRefinementPlanner(RichFreePlanner):
 def _evaluate(self,**kw):
  result=super()._evaluate(**kw)
  schedule=result.schedule
  if schedule is not None:
   original=Piece(schedule.coefficients.copy(),schedule.duration_s)
   refined=LocalQuintic.from_piece(original,[.25*original.T,.5*original.T,.75*original.T])
   assert refined.collapse_original(original) is original
   # Original immutable schedule and original certificate are returned verbatim.
  return result
base.FreePlanner=ExactRefinementPlanner

def resources():
 import shutil
 size=sum(f.stat().st_size for f in P.rglob('*') if f.is_file());disk=shutil.disk_usage(P)
 mem={x.split(':')[0]:int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines()}
 assert size<7.5*2**30 and disk.free>10*2**30 and mem['MemAvailable']>2**30,'RESOURCE_STOP'
 return dict(package_bytes=size,disk_free_bytes=disk.free,memory_available_bytes=mem['MemAvailable'])
def dispatch(ident,**extra):
 n=sum(r['event']=='START' for r in base.mh.records());assert n<4,'BASELINE_ONLY_CAP'
 assert time.time()<PLAN['dispatch_cutoff_unix']-600,'DEADLINE'
 assert not any(r['event']=='START' and r['id']==ident for r in base.mh.records()),'DUPLICATE_ID'
 base.mh.event('START',ident,mode='BASELINE_AUDIT_NOT_FORCE_SEARCH',resources=resources(),**extra)
 state=json.loads((P/'STATE.json').read_text());state.update(phase='BASELINE_PHYSICAL_AUDIT',physics_starts=n+1,remaining_seconds=PLAN['hard_stop_unix']-time.time(),owned_pids=[os.getpid()],next_allowed_action='finish baseline audit only');base.put('STATE.json',state)
base.mh.dispatch=dispatch;base.sd.dispatch=dispatch;base.dispatch=dispatch;base.resource_sample=resources
prior=json.loads((P/'control/frozen18D_baseline_identity.json').read_text())['best']['candidate']
class Baseline(base.FreeInterface):
 def decision_boundary(self,b):
  phase=b['task_state'].phase.value
  if self.child is None and not self.fork_done and phase=='OUTBOUND':
   self.fork_done=True
   candidates=[dict(id='B0_original',stage='REFERENCE',seed_family='B0',phases={},free_parameters=[0.]*18),{**prior,'id':'frozen18D_identity','stage':'REFERENCE'},dict(id='zero_exact_refinement',stage='REFERENCE',seed_family='B0',phases={},free_parameters=[0.]*18)]
   for c in candidates:
    self.cache={}
    if self.eval(b,c,'baseline') is None:return self.control(b)
   gate=base.mh.complete_gate('baseline_B0_original','baseline_zero_exact_refinement');base.put('BASELINE_ZERO_COLLAPSE_GATE.json',gate)
   assert gate['status']=='PASS','ZERO_COLLAPSE_TRACE_MISMATCH'
   for ident,old_id in [('baseline_B0_original','development_repair2_B0_original'),('baseline_frozen18D_identity','development_repair2_quality_NATIVE_SCALAR_18_063')]:
    errors=[]
    with np.load(P/'source/results'/ident/'trace.npz') as a,np.load(P/'key_traces'/old_id/'trace.npz') as z:
     assert set(a.files)==set(z.files)
     for key in a.files:
      same=a[key].shape==z[key].shape and (np.array_equal(a[key],z[key],equal_nan=True) if a[key].dtype.kind in 'fc' else np.array_equal(a[key],z[key]))
      if not same:errors.append(key)
    base.put('audit/'+ident+'_HISTORICAL_TRACE_GATE.json',dict(status='PASS' if not errors else 'FAIL',all_trace_fields=True,mismatches=errors,new=ident,historical=old_id))
    assert not errors,'HISTORICAL_IDENTITY_MISMATCH'
   base.put('BASELINE_REPRODUCTION.json',dict(status='PASS',runs=self.eval_rows,scope='new complete B and frozen18D physical rollouts plus exact-zero collapse baseline; same full live parent',clock='SCIENTIFIC_SIMULATION',host_qualified=False))
  self.control(b)

def main():
 lock=(P/'PHYSICS.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 condition=dict(name='baseline',seed=PLAN['seed'],prefix={});interface=Baseline(condition)
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('BASELINE_WALL_STOP')));signal.alarm(min(1200,max(1,int(PLAN['physics_hard_stop_unix']-time.time()))))
 dispatch('baseline_parent',kind='LEGAL_COLD_PARENT');random.seed(condition['seed']);np.random.seed(condition['seed'])
 try:
  m=sc.run('baseline_parent',interface,execution_mode='SCIENTIFIC_SIMULATION')
  if interface.child is not None:os._exit(0)
  base.mh.event('END','baseline_parent',returncode=0,joined=True,task_valid=m['task_valid']);assert m['task_valid']
  base.sd.metric('baseline_parent');gate=base.mh.complete_gate('baseline_parent','baseline_B0_original');base.put('BASELINE_PARENT_GATE.json',gate);assert gate['status']=='PASS'
  base.put('BASELINE_DONE.json',dict(status='PASS',unix=time.time(),starts=len([r for r in base.mh.records() if r['event']=='START'])))
 except BaseException as e:
  ident='baseline_parent' if interface.child is None else interface.child['label']+'_'+interface.child['kind']
  base.put('reports/'+ident+'_ERROR.json',dict(unix=time.time(),error=str(e),traceback=traceback.format_exc()))
  if interface.child is not None:os._exit(1)
  if not any(r['event']=='END' and r['id']==ident for r in base.mh.records()):base.mh.event('END',ident,returncode=1,joined=True,error=str(e))
  raise
 finally:
  if interface.child is None:
   signal.alarm(0);base.put('control/BASELINE_WORKER_EXIT.json',dict(pid=os.getpid(),unix=time.time(),active_child=getattr(interface,'active_owned_child_pid',None)))
if __name__=='__main__':main()
