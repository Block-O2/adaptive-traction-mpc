"""Bounded second-round contrasts; complete live parent, serial forks only."""
from pathlib import Path
import os,sys,json,time,signal,random,traceback,fcntl,shutil
P=Path(__file__).resolve().parents[1]
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TMPDIR=str(P/'tmp'),MPLCONFIGDIR=str(P/'tmp/mpl'))
sys.dont_write_bytecode=True;sys.path[:0]=[str(P/'control'),str(P/'code')]
import base_campaign as bc
import study_common as sc,matched_harness as mh,analyze_matched as am
import interface_base as ib
from round_planner import RoundPlanner
from early_return_planner import EarlyReturnPlanner
from rich_planner import RichFreePlanner
from terminal_repair import TerminalRepairPlanner
import numpy as np
GROUP=os.environ['STUDY_GROUP'];MODE=os.environ.get('STUDY_MODE','development')
PLAN=json.loads((P/'RUN_PLAN.json').read_text());CONFIG=json.loads((P/(GROUP+'_PLAN.json')).read_text())
def put(n,x):mh.put(P/n,sc.clean(x))
def append(n,x):
 with (P/n).open('a') as f:f.write(json.dumps(sc.clean(x),allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def dispatch(ident,**extra):
 rs=mh.records();n=sum(r['event']=='START' for r in rs)
 assert n<PLAN['physics_budget'],'START_CAP_24'
 assert MODE!='development' or n<PLAN['development_cap'],'VALIDATION_RESERVE'
 assert time.time()<PLAN['no_new_physics_after_unix']-PLAN['physical_timeout_s'],'PHYSICS_TIME_RESERVE'
 assert not (P/'PHYSICS_STOP.json').exists(),'STOPPED'
 assert not any(r['event']=='START' and r['id']==ident for r in rs),'DUPLICATE_START'
 assert shutil.disk_usage(P).free>12*2**30,'STORAGE_STOP'
 # Recheck frozen closure before every START.
 for rel,h in json.loads((P/'EXECUTION_CODE_MANIFEST.json').read_text())['files'].items():assert sc.sha(P/rel)==h,rel
 mh.event('START',ident,group=GROUP,mode=MODE,code_manifest_sha256=sc.sha(P/'EXECUTION_CODE_MANIFEST.json'),group_plan_sha256=sc.sha(P/(GROUP+'_PLAN.json')),**extra)
 put('STATE.json',dict(phase='SERIAL_'+MODE,physics_starts=n+1,last=ident,owned_pids=[os.getpid()]))
mh.dispatch=dispatch
class Campaign(bc.Qualification):
 def __init__(self,cond):
  super().__init__(cond);self.current=None;self.references={};self.sample_rows=[]
 def control(self,b):
  phase=b['task_state'].phase.value;slot=self.count.get(phase,0);planner=b['planner'];planner.multisegment_intent=None;planner.round_posture=None;planner.early_return_intent=None
  if self.current is not None:
   self.arm='E' if self.current['base']!='B' else 'B'
   if self.current['base']=='E':planner.__class__=RichFreePlanner
   elif self.current['base']=='T':planner.__class__=EarlyReturnPlanner if self.current.get('early') else RoundPlanner
   if self.current['base']!='B':planner.free_parameters=np.asarray(bc.OLD['free_parameters'],float)
  mh.MatchedInterface.control(self,b)
  if self.child is not None:
   for change in self.current.get('early',[]):
    if phase==change['phase'] and slot==change['slot']:planner.early_return_intent=change
   for change in self.current.get('posture',[]):
    if phase==change['phase'] and slot==change['slot']:planner.round_posture=change
   for change in self.current.get('changes',[]):
    if phase==change['phase'] and slot==change['slot']:
     req=b['request'];planner.multisegment_intent=dict(request_id=req.request_id,source_sample_time_s=float(req.source_sample_time_s),sensor_capture_ns=int(req.sensor_capture_ns),phase=phase,phase_remaining_s=float(b['arguments']['phase_remaining_s']),perturbation_deg=[0.,0.],policy='frozen_T_targeted_shape_v1',outbound_slot=slot,study_spec=change['spec'])
 def boundary(self,b):
  ib.Interface.boundary(self,b)
  prior=b['runtime'].get('reference_progress_commit')
  if prior is not None:
   def commit(receipt,original=prior,runtime=b['runtime']):
    original(receipt)
    if 'multisegment_reference' in receipt:receipt['multisegment_reference']['current_full_path_certificate']=runtime['activation_validation']['multisegment_current_path']['current_full_path_certificate']
   b['runtime']['reference_progress_commit']=commit
 def finish(self,env,metric):
  mh.MatchedInterface.finish(self,env,metric)
  put('output/'+metric['name']+'_REFERENCE_OBJECTS.json',dict(references=self.references,mathematical_and_certified_same_object=True))
  put('output/'+metric['name']+'_ISSUED_REFERENCE.json',dict(rows=self.sample_rows))
 def decision_boundary(self,b):
  if self.child is None and not self.fork_done and b['task_state'].phase.value=='OUTBOUND' and self.count['OUTBOUND']>=CONFIG.get('fork_after_prefix',1):
   self.fork_done=True
   put('audit/'+GROUP+'_FORK_CONTEXT.json',dict(source='actual cold commissioning + legal prefix + complete live address-space os.fork',physical_s=b['physical_now'],task_s=b['physical_now']-b['task_start_time'],count=self.count,manifest=self.manifest(b)))
   for c in CONFIG['arms']:
    if c.get('conditional_repeat'):
     prior=next(r for r in self.results if r['candidate']['id']=='D')
     if not (prior['all_original_qualifications'] and prior['motion']['gain_percent']>=1.0 and prior['J_F_N_s']<next(r['J_F_N_s'] for r in self.results if r['candidate']['id']=='T')):
      put(GROUP+'_REPEAT_NOT_STARTED.json',dict(reason='D did not pass every original qualification and retain force advantage',new_START=False));continue
    if self.fork(b,c['id'],np.zeros((2,5,3))):
     self.current=c;self.references={};self.sample_rows=[]
     signal.alarm(min(PLAN['physical_timeout_s'],max(1,int(PLAN['physics_hard_stop_unix']-time.time()))))
     return self.control(b)
    ident=GROUP+'_'+c['id'];m=am.measure(ident);baseline=m if c['id']=='B' else json.loads((P/'reports'/(GROUP+'_B_MEASURED.json')).read_text());comp=am.compare(m,baseline)
    tbase=m if c['id'] in ['B','E','T'] else json.loads((P/'reports'/(GROUP+'_T_MEASURED.json')).read_text());paired=am.compare(m,tbase)
    row=dict(id=ident,candidate=c,J_F_N_s=m['J_F_N_s'],phase_cost=m['phase_cost'],phase_durations=m['phase_durations'],motion=comp,paired_vs_T=paired,task=m['axes']['PHYSICAL_TASK_VALID'],receipt=m['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID'],absolute_safety=bool(m['native_physical_audit']['pass_']),actual_new_native_steps=m['actual_new_native_steps'],branch=m['branch'],complete_task=True,metrics_path='reports/'+ident+'_MEASURED.json')
    su=json.loads((P/'source/results'/ident/'summary.json').read_text());postures=[lr['selected_plan']['execution_screen']['second_round_posture'] for lr in su['learning_records'] if 'second_round_posture' in lr['selected_plan']['execution_screen']]
    early=[lr['selected_plan']['execution_screen']['early_return_duration'] for lr in su['learning_records'] if 'early_return_duration' in lr['selected_plan']['execution_screen']]
    row['posture_execution']=postures;row['early_execution']=early;row['intervention_executed']=len(postures)==len(c.get('posture',[])) and all(x['status']=='ACCEPTED' for x in postures) and len(early)==len(c.get('early',[])) and all(x['status']=='ACCEPTED' for x in early)
    row['all_original_qualifications']=bool(comp['acceptance_pass'] and row['task']=='PASS' and row['receipt']=='PASS' and row['absolute_safety'] and row['intervention_executed'])
    self.results.append(row);append('EXPLORATION_RESULTS.jsonl',row);put(GROUP+'_RESULTS.json',dict(rows=self.results,condition=self.condition))
    print(json.dumps(dict(id=ident,J_F=m['J_F_N_s'],gain=comp['gain_percent'],motion=comp['acceptance_pass'],failed=comp['failed_requirements'])),flush=True)
    assert row['absolute_safety'] and row['task']=='PASS' and row['receipt']=='PASS','ABSOLUTE_TASK_SAFETY_CAUSAL_STOP'
    if c['id'] in ['B','E','T'] and CONFIG.get('archive_condition'):
     src=P.parent/'m2_18d_terminal_expanded_prefix_validation_v1/source/results'/(CONFIG['archive_condition']+'_'+c['id'])
     gate=bc.compare_raw(P/'source/results'/ident,src);put('audit/'+ident+'_ARCHIVE_GATE.json',gate);assert gate['status']=='PASS','BASELINE_REPRODUCTION_FAIL'
    # New prospectively registered qualification contract permits D evaluation
    # despite T motion failure; unchanged motion gates still qualify every arm.
    if CONFIG.get('reproduce_W1') and c['id'] in ['B','T','D']:
     gate=bc.compare_raw(P/'source/results'/ident,P.parent/'m2_18d_w1_d_qualification_v1/source/results'/('W1_'+c['id']));put('audit/'+ident+'_HISTORICAL_GATE.json',gate);assert gate['status']=='PASS','W1_REPRODUCTION_FAIL'
    if c.get('zero'):
     gate=ib.compare_raw(GROUP+'_T',ident,True);put('audit/'+ident+'_ZERO_GATE.json',gate);assert gate['status']=='PASS','ZERO_PHYSICAL_FAIL'
    if c.get('repeat_of'):
     gate=bc.compare_raw(P/'source/results'/(GROUP+'_'+c['repeat_of']),P/'source/results'/ident);put('audit/'+ident+'_REPEAT_GATE.json',gate);assert gate['status']=='PASS','REPEAT_FAIL'
    if c.get('early'):
     dm=json.loads((P/'reports'/(GROUP+'_D_MEASURED.json')).read_text());df=dm['motion']['raw']['full'];mf=m['motion']['raw']['full'];new_failures=sorted(set(comp['failed_requirements'])-set(next(x for x in self.results if x['candidate']['id']=='D')['motion']['failed_requirements']))
     peak_worse=any(np.any(np.asarray(mf[key][stat])>1.10*np.asarray(df[key][stat])+1e-8) for key,stat in [('acceleration_deg_s2','max_abs'),('jerk_deg_s3','rms')])
     tracking_worse=bool(np.any(np.asarray(m['tracking_RMS_deg'])>np.asarray(dm['tracking_RMS_deg'])+.5))
     if new_failures or peak_worse or tracking_worse:
      put(GROUP+'_MECHANISM_REVIEW_REQUIRED.json',dict(id=ident,new_failures=new_failures,peak_worse=bool(peak_worse),tracking_worse=tracking_worse,next_candidates_not_started=True));break
   put(GROUP+'_PAIR_GATE.json',dict(status='PASS',all_parent_unchanged=all(r['unchanged'] for r in self.parent_checks),hashes={r['id']:r['branch']['full_hash'] for r in self.results}))
  self.control(b)
def main():
 assert json.loads((P/'PREPHYSICAL_CHECKS.json').read_text())['status']=='PASS'
 if MODE=='validation':assert json.loads((P/'REPAIR_FROZEN_SELECTION.json').read_text())['primary'] is not None
 lock=(P/'PHYSICS.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 it=Campaign(CONFIG['condition']);ident=GROUP+'_parent'
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('OWNED_TIMEOUT')));signal.alarm(max(1,int(PLAN['physics_hard_stop_unix']-time.time())))
 dispatch(ident,kind='LEGAL_COLD_PARENT',condition=CONFIG['condition']);random.seed(CONFIG['condition']['seed']);np.random.seed(CONFIG['condition']['seed'])
 try:
  m=sc.run(ident,it,execution_mode='SCIENTIFIC_SIMULATION')
  if it.child is not None:os._exit(0)
  mh.event('END',ident,returncode=0,joined=True,task_valid=m['task_valid']);assert m['task_valid']
  am.measure(ident);gate=bc.compare_raw(P/'source/results'/ident,P/'source/results'/(GROUP+'_B'));put(GROUP+'_PARENT_GATE.json',gate);assert gate['status']=='PASS','PARENT_B_DIFFERENCE'
  put(GROUP+'_DONE.json',dict(status='PASS',unix=time.time(),all_children_joined=True,rows=it.results))
 except BaseException as e:
  actual=ident if it.child is None else it.child['label']+'_'+it.child['kind'];put('reports/'+actual+'_ERROR.json',dict(error=str(e),traceback=traceback.format_exc(),unix=time.time()))
  if it.child is not None:os._exit(1)
  if not any(r['event']=='END' and r['id']==ident for r in mh.records()):mh.event('END',ident,returncode=1,joined=True,error=str(e))
  put('PHYSICS_STOP.json',dict(reason=str(e),unix=time.time()));raise
 finally:
  if it.child is None:signal.alarm(0);put(GROUP+'_WORKER_EXIT.json',dict(pid=os.getpid(),unix=time.time(),active_child=getattr(it,'active_owned_child_pid',None)))
if __name__=='__main__':main()
