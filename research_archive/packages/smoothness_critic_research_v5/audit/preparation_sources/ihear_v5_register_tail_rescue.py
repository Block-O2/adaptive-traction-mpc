from pathlib import Path
import os,json,copy,hashlib,datetime,subprocess
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
assert not (P/'experiments/TAILRESCUE01.json').exists()
frozen=json.loads((P/'audit/VALIDATION_CONTROL_SOURCE_FREEZE.json').read_text());ant='source/v5_bounded_anticipatory.py';assert hashlib.sha256((P/ant).read_bytes()).hexdigest()==frozen['files'][ant],'BRANCH_MODEL_CHANGED_AFTER_HELDOUT'
# A separately owned worker: existing C1/C2 worker and every frozen model remain unchanged.
src=(P/'source/v5_tail_wrench_worker.py').read_text()
src=src.replace('from v5_tail_features import capture as capture_tail','from v5_tail_features import capture as capture_tail\nfrom v5_bounded_anticipatory import AnticipatoryPlanner\nfrom v5_single_blind_shift import SingleBlindShiftPlanner')
needle="     b['planner'].__class__=ReferenceSmoothPlanner;b['planner'].smooth_strength=self.active_action['smooth_strength']"
assert src.count(needle)==1
src=src.replace(needle,needle+"\n    if self.active_action.get('anticipatory'):\n     b['planner'].__class__=AnticipatoryPlanner;b['planner'].smooth_strength=0.\n    if 'blind_shift_deg' in self.active_action:\n     b['planner'].__class__=SingleBlindShiftPlanner;b['planner'].blind_shift_delta_deg=self.active_action['blind_shift_deg']")
src=src.replace("'v5_tail_features.py','v5_native_wrench.py']", "'v5_tail_features.py','v5_native_wrench.py','v5_bounded_smooth.py','v5_bounded_anticipatory.py','v5_single_blind_shift.py']")
compile(src,str(P/'source/v5_tail_rescue_worker.py'),'exec');(P/'source/v5_tail_rescue_worker.py').write_text(src)
blind=(P/'source/v5_blind_shift_planner.py').read_text().replace('from v5_smooth_planner import ReferenceSmoothPlanner','from v5_bounded_smooth import ReferenceSmoothBoundedPlanner as ReferenceSmoothPlanner').replace('class BlindShiftPlanner','class SingleBlindShiftPlanner').replace("kw['phase'].value!='RETURN' or int(getattr(self,'coordination_slot',-1))!=1", "kw['phase'].value!='OUTBOUND' or int(getattr(self,'coordination_slot',-1))!=2").replace("meta=dict(phase='RETURN',slot=1", "meta=dict(phase='OUTBOUND',slot=2")
needle="  delta=float(getattr(self,'blind_shift_delta_deg',0.));assert abs(delta)<=.02";assert blind.count(needle)==1
blind=blind.replace(needle,needle+"\n  weight=float(np.sin(np.pi*np.clip((int(self.coordination_slot)+.5)/6,0,1))**2);coordinate=float(self.coordination_modes[1])+delta/(.30*weight);assert abs(coordinate)<=1+1e-12,'SINGLE_SHIFT_ORIGINAL_COORDINATE_BOX'")
compile(blind,str(P/'source/v5_single_blind_shift.py'),'exec');(P/'source/v5_single_blind_shift.py').write_text(blind)
cfg=json.loads((P/'experiments/TAILOT.json').read_text());speed=copy.deepcopy(next(r['action'] for r in cfg['actions'] if r['tag']=='SPEEDP'));anticipatory={**copy.deepcopy(speed),'anticipatory':True};minus={**copy.deepcopy(speed),'blind_shift_deg':-.02};plus={**copy.deepcopy(speed),'blind_shift_deg':.02}
cfg.update(group='TAILRESCUE01',worker='v5_tail_rescue_worker.py',job_wall_cap_s=5400,actions=[dict(tag=tag,action=act,category='adaptive_new_failure_tail_rescue') for tag,act in [('B',{'family':'B'}),('SPEEDP',speed),('ANT',anticipatory),('BLINDM',minus),('BLINDP',plus)]]);cfg['condition']['name']='TAILRESCUE01';cfg['condition']['role']='EXPOSED_HELDOUT_FAILURE_REPLAY: known TAILOT failure; unchanged pre-failure branch model, no unseen-generalization claim';cfg['historical_repeats']={}
for f in [P/'experiments/TAILRESCUE01.json',P/'runtime/TAILRESCUE01_TEST_PLAN.json']:f.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
source='''"""Finite replay of a newly exposed failure, after all pre-registered primary experiments."""
from pathlib import Path
import os,sys,json,time,subprocess,datetime,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1');sys.dont_write_bytecode=True
P=Path(__file__).resolve().parents[1];deadline=json.loads((P/'ACTIVATION.json').read_text())['hard_stop_unix']-2700
def put(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\\n')
cfg='experiments/TAILRESCUE01.json';sha=hashlib.sha256((P/cfg).read_bytes()).hexdigest()
put('owned/TAIL_RESCUE_QUEUE_START.json',dict(pid=os.getpid(),utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),deadline_unix=deadline,maximum_new_physical_START=6,config_sha256=sha,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),predecessor='owned/PPO_REPAIR_QUEUE_END.json',known_failure_replay_not_new_blind_validation=True))
done=[];reason='FINITE_NEW_FAILURE_REPLAY_COMPLETED'
try:
 for _ in range(max(1,int(deadline-time.time())+1)):
  if time.time()>deadline or (P/'STOP_REQUESTED').exists():raise TimeoutError('TAIL_RESCUE_QUEUE_DEADLINE')
  f=P/'owned/PPO_REPAIR_QUEUE_END.json'
  if f.exists():
   e=json.loads(f.read_text());assert e['reason'] in ['FINITE_SUPPLEMENTAL_STUDY_COMPLETED','SUPPLEMENTAL_DEV_COMPLETED_NO_GAIN_VALIDATION_NOT_RUN'],'PREDECESSOR_NOT_CLOSED';break
  time.sleep(1)
 else:raise TimeoutError('PREDECESSOR_NOT_FINISHED')
 assert time.time()<deadline-1800,'NO_TIME_FOR_COMPLETE_TAIL_RESCUE_AND_AUDIT'
 assert hashlib.sha256((P/cfg).read_bytes()).hexdigest()==sha,'FROZEN_RESCUE_CONFIG_CHANGED'
 with (P/'logs/TAILRESCUE01_supervisor.log').open('w') as log:
  child=subprocess.Popen([sys.executable,'-B',str(P/'source/supervise_v2.py'),cfg],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
  put('owned/TAIL_RESCUE_QUEUE_CURRENT.json',dict(pid=child.pid,group='TAILRESCUE01'));rc=child.wait(timeout=max(1,int(deadline-time.time())))
 assert rc==0,'TAIL_RESCUE_JOB_FAILED';done.append('TAILRESCUE01')
except BaseException as error:reason=type(error).__name__+':'+str(error);raise
finally:put('owned/TAIL_RESCUE_QUEUE_END.json',dict(pid=os.getpid(),utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),reason=reason,completed=done))
'''
compile(source,str(P/'source/v5_tail_rescue_queue.py'),'exec');(P/'source/v5_tail_rescue_queue.py').write_text(source)
record=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),hypothesis='An unchanged causal explicit branch selector may rescue the newly exposed OUTBOUND SPEEDP guard/motion failure more simply than the failed cost Critic. Blind shifts distinguish geometric information from generic microperturbation.',experiment='TAILRESCUE01, same exact TAILOT legal prefix/seed, full-live-state fork at OUTBOUND2, original B following policy. B, originalSPEEDP, SPEEDP+unchangedAnt, and fixed +/-0.02degree shifts at only this decision. Maximum6START including cold parent.',result='FINITE_ADAPTIVE_REPLAY_REGISTERED',diagnosis='Known heldout failure selected after observing it; no new unseen-generalization claim. Branch model source SHA was frozen before the original heldout result. Original Critic weights/configs and all primary validation candidates remain unchanged.',decision='Run serially after PPO execution repair closes; retain failure and independently verify originalSPEEDP physical replay identity and subsequentB semantics. No new critic fitting or PPO training.',evidence=['experiments/TAILRESCUE01.json','source/v5_tail_rescue_worker.py','source/v5_single_blind_shift.py'],unchanged_branch_model_sha256=frozen['files'][ant],maximum_new_physical_START=6)
(P/'experiments/TAIL_RESCUE_PREREGISTRATION.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
with (P/'RESEARCH_DECISIONS.jsonl').open('a') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
with (P/'logs/TAIL_RESCUE_QUEUE.log').open('w') as log:
 child=subprocess.Popen(['/home/hank/ihear-lab/rl_b_cloud_v1/.venv/bin/python','-B',str(P/'source/v5_tail_rescue_queue.py')],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'})
f=P/'queue/FINAL_AUDIT_DEPENDENCIES.json';d=json.loads(f.read_text());d['required_queue_end'].append('owned/TAIL_RESCUE_QUEUE_END.json');f.write_text(json.dumps(d,indent=2)+'\n')
f=P/'WORK_STATE.json';d=json.loads(f.read_text());d['new_failure_tail_rescue_queue']='TAIL_RESCUE_QUEUE max6START afterPPO_REPAIR_QUEUE_END; knownOTfailedSpeedP replay+unchangedAnt+blind+/- atOUT2; newworker only, allfrozenprimarysourcesunchanged';d['final_closure_must_wait_rescue_END']=True;f.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
print('TAIL_RESCUE_QUEUE_PID',child.pid,'MAX_START6','AFTER_PPO_REPAIR')
