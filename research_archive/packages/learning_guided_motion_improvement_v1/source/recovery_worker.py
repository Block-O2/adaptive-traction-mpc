from pathlib import Path
import os,sys,json,time,signal,random,traceback,fcntl,hashlib,datetime
P=Path(__file__).resolve().parents[1];R=P/'runtime';GROUP='RECOVERY'
os.environ.update(STUDY_GROUP=GROUP,STUDY_MODE='development',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TMPDIR=str(R/'tmp'),MPLCONFIGDIR=str(R/'tmp/mpl'))
sys.dont_write_bytecode=True;sys.path[:0]=[str(R/'control'),str(R/'code')]
import campaign_v6 as frozen
import study_common as sc,matched_harness as mh,analyze_matched as am
import numpy as np
PLAN=json.loads((R/'RUN_PLAN.json').read_text());CONFIG=json.loads((R/(GROUP+'_TEST_PLAN.json')).read_text())
def put(n,x):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);tmp=f.with_suffix(f.suffix+'.tmp');tmp.write_text(json.dumps(sc.clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n');tmp.replace(f)
def dispatch(ident,**kw):
 records=mh.records();assert sum(r['event']=='START' for r in records)<8,'ENGINEERING_START_CAP'
 assert not any(r['event']=='START' and r['id']==ident for r in records),'DUPLICATE'
 assert time.time()<PLAN['dispatch_cutoff_unix']-PLAN['physical_timeout_s'],'TIME'
 assert not (P/'STOP_REQUESTED').exists(),'STOP'
 for rel,h in json.loads((P/'EXECUTION_SOURCE_MANIFEST.json').read_text())['files'].items():assert sc.sha(P/rel)==h,'SOURCE_CHANGED:'+rel
 mh.event('START',ident,category='engineering',source_sha256=sc.sha(P/'EXECUTION_SOURCE_MANIFEST.json'),**kw)
mh.dispatch=dispatch
class Recovery(frozen.Campaign):
 def __init__(self):super().__init__(CONFIG['condition']);self.metrics=[];self.causal=[]
 def decision_boundary(self,b):
  if self.child is None and not self.fork_done and b['task_state'].phase.value=='OUTBOUND' and self.count['OUTBOUND']>=1:
   self.fork_done=True
   put('audit/RECOVERY_FORK_CONTEXT.json',{'physical_s':b['physical_now'],'task_s':b['physical_now']-b['task_start_time'],'causal_estimated_state':b['observation'].as_array(),'commissioned_belief':b['belief'].value_state_record(),'phase':b['task_state'].phase.value,'count':self.count,'source':'cold commissioning plus legal D01R prefix; complete address-space fork'})
   arms=CONFIG['arms']+[dict(CONFIG['arms'][1],id='H150_REPEAT')]
   for c in arms:
    if self.fork(b,c['id'],np.zeros((2,5,3))):
     self.current=c;self.references={};self.sample_rows=[];self.terminal_intent=None;self.causal=[];signal.alarm(600);return self.control(b)
    ident=GROUP+'_'+c['id'];measured=am.measure(ident);base=measured if c['id']=='B' else json.loads((R/'reports/RECOVERY_B_MEASURED.json').read_text());comparison=am.compare(measured,base)
    row={'id':ident,'qualified':comparison['acceptance_pass'] and measured['axes']['PHYSICAL_TASK_VALID']=='PASS' and measured['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID']=='PASS' and measured['native_physical_audit']['pass_'],'measurement':measured,'motion_vs_B':comparison}
    self.metrics.append(row);put('audit/RECOVERY_RESULTS.json',self.metrics)
    print('RECOVERY_END',ident,measured['J_F_N_s'],row['qualified'],comparison['failed_requirements'],flush=True)
    assert row['qualified'],'BASELINE_NOT_QUALIFIED'
   repeat=frozen.bc.compare_raw(R/'source/results/RECOVERY_H150',R/'source/results/RECOVERY_H150_REPEAT');put('audit/RECOVERY_REPEAT_RAW_GATE.json',repeat);assert repeat['status']=='PASS','EXACT_REPEAT_FAILED'
   assert all(x['unchanged'] for x in self.parent_checks),'PARENT_CHANGED'
  self.control(b)
 def boundary(self,b):
  super().boundary(b)
  if self.child is not None:
   self.causal.append({'time_s':b['physical_now'],'phase':b['task_state'].phase.value,'estimated_q_dq':b['observation'].as_array(),'reference_q_dq':np.r_[b['reference'].q_rad,b['reference'].dq_rad_s],'measured_force':b['interface'].measured_force_world_n,'measured_moment':b['interface'].measured_moment_world_nm,'source_sample_time_s':b['request'].source_sample_time_s,'truth_used':False})
 def finish(self,env,metric):
  super().finish(env,metric);put('history/'+metric['name']+'_CAUSAL_HISTORY.json',self.causal)

def main():
 lock=(P/'PHYSICS.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('OWNED_WALL_TIMEOUT')));signal.alarm(2400)
 it=Recovery();ident=GROUP+'_parent';start=time.time();dispatch(ident,kind='LEGAL_COLD_PARENT');random.seed(CONFIG['condition']['seed']);np.random.seed(CONFIG['condition']['seed'])
 try:
  m=sc.run(ident,it,execution_mode='SCIENTIFIC_SIMULATION')
  if it.child is not None:os._exit(0)
  mh.event('END',ident,returncode=0,joined=True,native_steps=m['actual_new_native_physics_steps'],wall_seconds=time.time()-start)
  am.measure(ident);gate=frozen.bc.compare_raw(R/'source/results'/ident,R/'source/results/RECOVERY_B');put('audit/RECOVERY_PARENT_RAW_GATE.json',gate);assert gate['status']=='PASS','PARENT_B_RAW_DIFFERENCE'
  put('audit/RECOVERY_DONE.json',{'status':'PASS','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'all_children_joined':True,'wall_s':time.time()-start,'parent_checks':it.parent_checks})
 except BaseException as error:
  actual=ident if it.child is None else it.child['label']+'_'+it.child['kind'];put('audit/'+actual+'_ERROR.json',{'error':str(error),'traceback':traceback.format_exc()})
  if it.child is not None:os._exit(1)
  if not any(r['event']=='END' and r['id']==ident for r in mh.records()):mh.event('END',ident,returncode=1,joined=True,error=str(error))
  put('audit/RECOVERY_DONE.json',{'status':'FAILED_PRESERVED','error':str(error),'wall_s':time.time()-start});raise
 finally:
  if it.child is None:signal.alarm(0);put('audit/RECOVERY_OWNER_EXIT.json',{'pid':os.getpid(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'active_child':getattr(it,'active_owned_child_pid',None)})
if __name__=='__main__':main()
