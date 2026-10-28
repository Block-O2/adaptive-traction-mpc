"""One physical owner, serial legal full-state forks, unmodified raw scorer."""
from pathlib import Path
import os,sys,json,time,signal,random,traceback,fcntl,copy,shutil
sys.dont_write_bytecode=True
P=Path(os.environ['ACL2_PACKAGE']);R=P/'runtime';C=json.loads((P/sys.argv[1]).read_text());GROUP=C['group']
os.environ.update(STUDY_GROUP=GROUP,STUDY_MODE=C.get('mode','development'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TMPDIR=str(R/'tmp'),MPLCONFIGDIR=str(R/'tmp/mpl'))
sys.path[:0]=[str(P/'source'),str(R/'control'),str(R/'code')]
import campaign_v6 as frozen
import study_common as sc,matched_harness as mh,analyze_matched as am
from acl2_shared import put,read,sha,utc,native_used,decision,append
from acl2_modal_planner import ModalPlanner
from acl2_modal_retimed import RetimedModalPlanner
from v5_smooth_planner import ReferenceSmoothPlanner
from v5_bounded_anticipatory import AnticipatoryPlanner
import branch_diagnostics
branch_diagnostics.install()
import v5_native_wrench
v5_native_wrench.install()
from v5_blind_shift_planner import BlindShiftPlanner
import numpy as np
A=read('ACTIVATION.json');PLAN=read('runtime/RUN_PLAN.json');CURRENT_CATEGORY='engineering';SOURCE_MANIFEST=None

def worst_ratio(m,b,comp):
 vals=[]
 for ratios in comp['burden_ratios'].values():vals.append(float(np.max(ratios))/1.1)
 vals += [float(np.max(comp['excursion_delta_deg']))/.5,float(np.max(comp['endpoint_abs_delta_deg']))/.5,comp['phase_boundary_max_delta_deg']/.5,comp['duration_abs_delta_s']/.1]
 for ph in ['OUTBOUND','HOLD','RETURN']:vals.append(abs(m['phase_durations'][ph]-b['phase_durations'][ph])/.1)
 travel=np.asarray(comp['cumulative_ratio']);vals += [float(np.max(travel))/1.05,float(np.max(.95/travel))]
 vals += [m['moment_integral_Nm_s']/b['moment_integral_Nm_s']/1.25,m['force_peak_N']/b['force_peak_N']/1.05,m['moment_peak_Nm']/b['moment_peak_Nm']/1.05,max(0.,float(np.max(np.asarray(m['tracking_RMS_deg'])-np.asarray(b['tracking_RMS_deg']))))/.5]
 return max(vals)

def dispatch(ident,**kw):
 rs=mh.records();starts=[r for r in rs if r['event']=='START'];assert len(starts)<PLAN['physics_budget'],'TOTAL_START_CAP'
 assert not any(r['id']==ident for r in starts),'DUPLICATE_START'
 cutoff=PLAN['validation_dispatch_cutoff_unix'] if C.get('mode')=='validation' else PLAN['dispatch_cutoff_unix']
 assert time.time()<cutoff-PLAN['physical_timeout_s'],'NEW_PHYSICS_DEADLINE'
 assert not (P/'STOP_REQUESTED').exists(),'STOP_REQUESTED'
 assert native_used()+300000<PLAN['native_step_cap'],'NATIVE_CAP'
 assert CURRENT_CATEGORY!='optimization' or sum(r.get('category')=='optimization' for r in starts)<PLAN['development_cap'],'LOCKED_VALIDATION_RESERVE'
 assert shutil.disk_usage(P).free>18*2**30,'DISK_FLOOR'
 for rel,h in SOURCE_MANIFEST['files'].items():assert sha(P/rel)==h,'RUNNING_SOURCE_CHANGED:'+rel
 mh.event('START',ident,category=CURRENT_CATEGORY,group=GROUP,job_source_sha256=sha(P/('jobs/'+GROUP+'/SOURCE_MANIFEST.json')),config_sha256=sha(P/sys.argv[1]),absolute_deadline_unix=A['hard_stop_unix'],**kw)
mh.dispatch=dispatch

class Study(frozen.Campaign):
 def __init__(self):
  super().__init__(C['condition']);self.metrics=[];self.active_action={};self.current=None;self.causal=[];self.last_counter=0.;self.closed_native=0;self.prediction=None;self.baseline=None;self.arm_rows={};self.owned_step_start=0
 def control(self,b):
  phase=b['task_state'].phase.value;slot=self.count.get(phase,0)
  super().control(b)
  if self.current is not None and self.current['base']=='T':
   x=np.asarray(frozen.bc.OLD['free_parameters'],float).copy();legacy=np.asarray(self.active_action.get('legacy',[0.,0.]),float);assert legacy.shape==(2,) and np.all(abs(legacy)<=1+1e-12)
   x[[1,6]]+=.002*legacy;b['planner'].free_parameters=x
   if self.active_action.get('family')=='old18d':
    full=np.asarray(self.active_action['parameters'],float);scales=np.asarray([z['scale'] for z in read('runtime/PARAMETER_MAP.json')['parameters']]);assert full.shape==(18,) and np.all(abs(full)<=scales+1e-12),'FULL_18D_DOMAIN';b['planner'].free_parameters=full
   if self.active_action.get('family') in ['modal8','modal8_retimed']:
    b['planner'].__class__=RetimedModalPlanner if self.active_action.get('family')=='modal8_retimed' else ModalPlanner;b['planner'].coordination_modes=np.asarray(self.active_action['x'],float);b['planner'].coordination_slot=slot
    if self.active_action.get('smooth_strength',0):
     b['planner'].__class__=ReferenceSmoothPlanner;b['planner'].smooth_strength=self.active_action['smooth_strength']
    if self.active_action.get('anticipatory'):
     b['planner'].__class__=AnticipatoryPlanner;b['planner'].smooth_strength=self.active_action.get('smooth_strength',0.)
    if self.active_action.get('blind_shift') is not None:
     b['planner'].__class__=BlindShiftPlanner;b['planner'].smooth_strength=0.;b['planner'].blind_shift_delta_deg=self.active_action['blind_shift']
 def boundary(self,b):
  super().boundary(b)
  if time.time()-self.last_counter>3:
   self.last_counter=time.time();current=round(float(b['physical_now'])/.00025)-(0 if self.child is None else self.child['physics_step_at_fork'])
   assert current<=180000,'ATTEMPT_NATIVE_CAP';assert self.closed_native+current+160000<PLAN['native_step_cap'],'LIVE_NATIVE_CAP'
   mem=dict(s.split(':',1) for s in Path('/proc/meminfo').read_text().splitlines());assert int(mem['MemAvailable'].split()[0])*1024>6*2**30,'RAM_FLOOR'
   assert time.time()<PLAN['physics_hard_stop_unix'],'PHYSICS_HARD_STOP';assert not (P/'STOP_REQUESTED').exists(),'STOP_REQUESTED'
   put('audit/LIVE_PHYSICS_COUNTERS.json',dict(utc=utc(),id=GROUP+'_parent' if self.child is None else self.child['label']+'_'+self.child['kind'],pid=os.getpid(),actual_new_native_live=current,closed_native_at_dispatch=self.closed_native,remaining_wall_s=A['hard_stop_unix']-time.time()))
  if self.child is not None:
   self.causal.append(dict(time_s=float(b['physical_now']),phase=b['task_state'].phase.value,estimated_q_dq=b['observation'].as_array(),reference_q_dq=np.r_[b['reference'].q_rad,b['reference'].dq_rad_s],measured_force=b['interface'].measured_force_world_n,measured_moment=b['interface'].measured_moment_world_nm,source_sample_time_s=b['request'].source_sample_time_s,truth_used=False))
 def finish(self,env,metric):
  super().finish(env,metric)
  put('history/'+metric['name']+'_CAUSAL_HISTORY.json',self.causal)
  put('attempts/'+metric['name']+'_EXECUTION_BINDING.json',dict(action=self.active_action,candidate=self.current,prediction=self.prediction,truth_used=False))
 def run_branch(self,b,tag,action,category='engineering',prediction=None):
  global CURRENT_CATEGORY
  CURRENT_CATEGORY=category;self.closed_native=native_used();self.prediction=copy.deepcopy(prediction)
  ident=GROUP+'_'+tag
  if prediction is not None:
   pred=copy.deepcopy(prediction);pred.update(id=ident,created_unix=time.time(),parent_hash=self.manifest(b)['hash']);put('predictions/'+ident+'.json',pred)
  failed=None;start=time.time()
  candidate=copy.deepcopy(C['B'] if action.get('family')=='B' else C['H150']);candidate['id']=tag
  if action.get('candidate_overrides'):candidate.update(copy.deepcopy(action['candidate_overrides']))
  try:
   if self.fork(b,tag,np.zeros((2,5,3))):
    self.current=candidate;self.active_action=copy.deepcopy(action);self.references={};self.sample_rows=[];self.terminal_intent=None;self.causal=[];self.last_counter=0
    signal.alarm(min(PLAN['physical_timeout_s'],max(1,int(PLAN['physics_hard_stop_unix']-time.time()))));return True
  except AssertionError as error:
   if not str(error).startswith(('CHILD_FAILED:','NATIVE_PHYSICAL_FAILURE:')):raise
   assert self.active_owned_child_pid is None and self.parent_checks[-1]['unchanged'],'PARENT_MUTATED_AFTER_FAILURE';failed=str(error)
  row=dict(id=ident,action=action,category=category,complete=False,qualified=False,error=failed,prediction=prediction,wall_s=time.time()-start,actual_new_native_steps=0)
  for suffix in ['_DATA.json','_PARTIAL_COMPUTE.json']:
   f=R/'output'/(ident+suffix)
   if f.exists():
    d=json.loads(f.read_text());row['actual_new_native_steps']=d.get('metric',d).get('actual_new_native_physics_steps')
    if d.get('metric') and not d['metric'].get('task_valid',True):
     mode=d['metric'].get('physical_audit',{}).get('unchanged_evaluator',{});checks=mode.get('physical_task_result',{}).get('scorer_v2_common_conditions',{})
     hard=['force','moment','torque','human_speed','human_acceleration','robot_speed','session_clearance','true_clearance','measured_sleeve_clearance','no_shank_table_contact','no_human_rom_violation']
     bad=[k for k in hard if checks.get(k) is False]
     if bad:raise RuntimeError('TRUE_NATIVE_SAFETY_CONTRACT_FAILURE:'+str(bad))
     row['protected_task_failure']={'abort_reason':mode.get('raw_scorer_v2',{}).get('abort_reason'),'hard_safety_conditions':{k:checks.get(k) for k in hard},'partial_JF_unranked':d['metric'].get('J_F')}
    break
  if failed is None:
   m=am.measure(ident);B=m if tag=='B' else read('runtime/reports/'+GROUP+'_B_MEASURED.json');comp=am.compare(m,B)
   qualified=bool(comp['acceptance_pass'] and m['axes']['LEGACY_R2_MATCHED']=='PASS' and m['native_physical_audit']['pass_'] and m['axes']['PHYSICAL_TASK_VALID']=='PASS' and m['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID']=='PASS')
   summary=read('runtime/source/results/'+ident+'/summary.json');execution=[]
   for lr in summary['learning_records']:
    screen=lr.get('selected_plan',{}).get('execution_screen',{});modal=screen.get('coordination_modal_v2');old=screen.get('free_trajectory')
    if modal is not None:assert np.max(abs(np.asarray(modal['parameters'])-np.asarray(action['x'])))<1e-12,'MODAL_PARAMETER_IDENTITY'
    if modal or old:execution.append(dict(decision_index=lr.get('decision_index'),activated=lr.get('selected_plan_activated'),modal=modal,legacy=old,reference_start_s=lr.get('start_time_s'),reference_end_s=lr.get('end_time_s')))
   row.update(complete=True,qualified=qualified,JF=m['J_F_N_s'],JM=m['moment_integral_Nm_s'],worst_ratio=worst_ratio(m,B,comp),motion_vs_B=comp,axes=m['axes'],metrics_path='runtime/reports/'+ident+'_MEASURED.json',branch=m['branch'],execution=execution,tracking=m['tracking_RMS_deg'],phase_cost=m['phase_cost']['phases'],actual_new_native_steps=m['actual_new_native_steps'])
   if not m['native_physical_audit']['pass_']:raise RuntimeError('TRUE_NATIVE_SAFETY_CONTRACT_FAILURE')
  if row['complete'] and tag in C.get('historical_repeats',{}):
   gate=frozen.bc.compare_raw(R/'source/results'/ident,Path('/home/hank/ihear-lab/deep_learning_method_exploration_v8/runtime/source/results')/C['historical_repeats'][tag]);put('audit/'+ident+'_HISTORICAL_IDENTITY.json',gate);assert gate['status']=='PASS','HISTORICAL_REPRODUCTION_MISMATCH'
  self.metrics.append(row);put('attempts/'+ident+'_RESULT.json',row);append('ALL_RESULTS.jsonl',row);put('jobs/'+GROUP+'/PROGRESS.json',dict(rows=self.metrics,arm_rows=self.arm_rows,utc=utc()))
  print('BRANCH_END',ident,'complete',row['complete'],'qualified',row['qualified'],'JF',row.get('JF'),'JM',row.get('JM'),'failed',row.get('motion_vs_B',{}).get('failed_requirements'),'error',failed,flush=True)
  self.last_row=row;return False
 def decision_boundary(self,b):
  if self.child is None and not self.fork_done and b['task_state'].phase.value=='OUTBOUND' and self.count['OUTBOUND']>=1:
   self.fork_done=True
   put('audit/'+GROUP+'_FORK_CONTEXT.json',dict(physical_s=b['physical_now'],task_s=b['physical_now']-b['task_start_time'],count=self.count.copy(),causal_estimated_state=b['observation'].as_array(),commissioned_belief=b['belief'].value_state_record(),source='actual cold commissioning and registered legal prefix; full address-space fork, not q/dq reconstruction',parent_hash=self.manifest(b)['hash']))
   if C.get('algorithm'):
    from importlib import import_module
    driver=import_module(C['algorithm']);gen=driver.sequence(self,C)
   else:gen=iter(C['actions'])
   for a in gen:
    if time.time()>min(C.get('local_stop_unix',PLAN['dispatch_cutoff_unix']),PLAN['physics_hard_stop_unix'])-PLAN['physical_timeout_s']:
     put('jobs/'+GROUP+'/EARLY_STOP.json',dict(reason='LOCAL_OR_GLOBAL_DEADLINE',utc=utc()));break
    tag=a['tag'];action=a['action']
    if self.run_branch(b,tag,action,a.get('category','engineering'),a.get('prediction')):return self.control(b)
    if tag=='B':
     assert self.last_row['qualified'],'B_NOT_QUALIFIED'
    if tag=='H150':
     assert self.last_row['qualified'],'H150_NOT_QUALIFIED';self.baseline=copy.deepcopy(self.last_row)
    if a.get('repeat_of'):
     gate=frozen.bc.compare_raw(R/'source/results'/(GROUP+'_'+a['repeat_of']),R/'source/results'/self.last_row['id']);put('audit/'+self.last_row['id']+'_REPEAT_GATE.json',gate);assert gate['status']=='PASS','ZERO_OR_REPEAT_RAW_DIFFERENCE'
   put('jobs/'+GROUP+'/PHYSICS_DONE.json',dict(status='COMPLETED',rows=self.metrics,all_parent_unchanged=all(r['unchanged'] for r in self.parent_checks),utc=utc()))
  self.control(b)

def main():
 global SOURCE_MANIFEST
 lock=(P/'PHYSICS.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 files={}
 for d in ['runtime/source','runtime/control','runtime/code','runtime/deps']:
  for f in (P/d).rglob('*'):
   if f.is_file() and f.suffix in ['.py','.json','.xml','.so'] and 'results' not in f.relative_to(P/d).parts:files[str(f.relative_to(P))]=sha(f)
 for name in [Path(__file__).name,'acl2_shared.py','acl2_modal_planner.py','acl2_modal_retimed.py','branch_diagnostics.py','v5_smooth_planner.py','v5_anticipatory_planner.py','v5_native_wrench.py','v5_blind_shift_planner.py','v5_bounded_anticipatory.py','v5_bounded_smooth.py']+([C['algorithm']+'.py'] if C.get('algorithm') else []):files['source/'+name]=sha(P/'source'/name)
 for name in ['RUN_PLAN.json','FROZEN_18D.json','MOTION_ACCEPTANCE_PROTOCOL.json','PARAMETER_MAP.json','ACTION_SET.json']:files['runtime/'+name]=sha(R/name)
 files['runtime/output/SHARED_COORDINATION_ACTION_CONTRACT.json']=sha(R/'output/SHARED_COORDINATION_ACTION_CONTRACT.json')
 if C.get('algorithm')=='acl2_search':files['source/acl2_proxy.py']=sha(P/'source/acl2_proxy.py')
 SOURCE_MANIFEST=dict(frozen_utc=utc(),files=files,config_sha256=sha(P/sys.argv[1]),origin=read('audit/CLOSURE_RELOCATION.json')['origin_manifest_sha256']);put('jobs/'+GROUP+'/SOURCE_MANIFEST.json',SOURCE_MANIFEST)
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('OWNED_WALL_DEADLINE')));signal.alarm(max(1,int(PLAN['physics_hard_stop_unix']-time.time())))
 it=Study();ident=GROUP+'_parent';start=time.time();dispatch(ident,kind='LEGAL_COLD_PARENT');random.seed(C['condition']['seed']);np.random.seed(C['condition']['seed'])
 try:
  m=sc.run(ident,it,execution_mode='SCIENTIFIC_SIMULATION')
  if it.child is not None:os._exit(0)
  mh.event('END',ident,returncode=0,joined=True,native_steps=m['actual_new_native_physics_steps'],wall_seconds=time.time()-start);am.measure(ident)
  gate=frozen.bc.compare_raw(R/'source/results'/ident,R/'source/results'/(GROUP+'_B'));put('audit/'+GROUP+'_PARENT_RAW_GATE.json',gate);assert gate['status']=='PASS','PARENT_B_RAW_MISMATCH'
  put('jobs/'+GROUP+'/WORKER_DONE.json',dict(status='PASS_EXECUTED_WITH_REPORTED_QUALIFICATIONS',utc=utc(),wall_s=time.time()-start,all_children_joined=True,parent_checks=it.parent_checks))
 except BaseException as error:
  actual=ident if it.child is None else it.child['label']+'_'+it.child['kind'];put('audit/'+actual+'_ERROR.json',dict(utc=utc(),error=str(error),traceback=traceback.format_exc()))
  if it.child is not None:os._exit(1)
  if not any(r['event']=='END' and r['id']==ident for r in mh.records()):mh.event('END',ident,returncode=1,joined=True,error=str(error))
  put('jobs/'+GROUP+'/WORKER_DONE.json',dict(status='FAILED_PRESERVED',error=str(error),utc=utc(),rows=it.metrics));raise
 finally:
  if it.child is None:signal.alarm(0);put('owned/'+GROUP+'_EXIT.json',dict(pid=os.getpid(),utc=utc(),active_child=getattr(it,'active_owned_child_pid',None)))
if __name__=='__main__':main()
