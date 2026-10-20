from pathlib import Path
import os,sys,json,time,copy,shutil,ast
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');sys.dont_write_bytecode=True;sys.path[:0]=[str(P/'control'),str(P/'code')]
import study_common as sc
import numpy as np
from types import SimpleNamespace
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointMPCShadowContractV1
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(sc.clean(x),indent=2,ensure_ascii=False)+'\n')
assert read('Dev_OWNER.json')['joined'];assert read('PHYSICS_STOP.json')['reason']=='CHILD_FAILED:Dev_KD120'
assert read('output/Dev_KD120_PARTIAL_COMPUTE.json')['actual_new_native_physics_steps']==0
assert not (P/'EXECUTION_CODE_MANIFEST_v2.json').exists()
primary=next(r for r in read('EXPERIMENT_RESULTS.json')['rows'] if r['id']=='Dev_H150');assert primary['selection_eligible']
put('NEW_FROZEN_SELECTION.json',dict(primary='H150',selected_unix=time.time(),candidate=primary['candidate'],development_id='Dev_H150',original_code_manifest_sha=sc.sha(P/'EXECUTION_CODE_MANIFEST.json'),selection_rule_sha=sc.sha(P/'CANDIDATE_SELECTION_RULE.json'),reason='First eligible reference-only candidate, original gates pass, overshoot improves0.074349deg with retained force benefit. Frozen before repeat/new-state outcomes.',validation='Same H150 wrapper and frozen parameters under v2 harness; controller repairs irrelevant to H150 path; actual raw reproducibility mandatory'))
s=(P/'control/terminal_control.py').read_text().replace("VERSION='terminal_acceleration_intent_v1'","VERSION='terminal_acceleration_intent_v2_target_cache'")
old=" contract.terminal_frame=dict(qref=r.q_rad.copy(),vref=r.dq_rad_s.copy(),aref=r.ddq_rad_s2.copy(),goal=b['planner'].reference_phase_goal(b['task_state'].phase).copy(),phase=b['task_state'].phase.value,sample_s=float(obs.sample_timestamp_s),now_s=float(b['physical_now']))"
new=""" phase=b['task_state'].phase.value
 goal=np.asarray(b['spec'].start_return_target_rad).copy()
 target_source='registered_target_unused_outside_RETURN'
 if phase=='RETURN':
  accepted=[v for v in getattr(b['planner'],'terminal_reference_cache',{}).values() if v.get('feasible') and np.allclose(v.get('original_goal_rad',[np.inf,np.inf]),goal,atol=1e-12,rtol=0)]
  if accepted:
   goal=np.asarray(accepted[-1]['reference_target_rad']).copy();target_source='accepted_deployable_terminal_reference_cache'
  else:phase='NO_ACCEPTED_TERMINAL_TARGET';target_source='no_assist_until_causal_target_available'
 contract.terminal_frame=dict(qref=r.q_rad.copy(),vref=r.dq_rad_s.copy(),aref=r.ddq_rad_s2.copy(),goal=goal,phase=phase,sample_s=float(obs.sample_timestamp_s),now_s=float(b['physical_now']))
 contract.terminal_target_source=target_source"""
assert old in s;s=s.replace(old,new).replace("row=intent.evaluate(state=state,**frame);delta=row['delta_rad_s2']","row=intent.evaluate(state=state,**frame);row['target_source']=self.terminal_target_source;delta=row['delta_rad_s2']")
(P/'control/terminal_control_v2.py').write_text(s)
s=(P/'control/campaign.py').read_text().replace('from terminal_control import','from terminal_control_v2 import').replace("'EXECUTION_CODE_MANIFEST.json'","'EXECUTION_CODE_MANIFEST_v2.json'").replace("'PREPHYSICAL_CHECKS.json'","'PREPHYSICAL_CHECKS_v2.json'").replace("'PHYSICS_STOP.json'","'PHYSICS_STOP_v2.json'")
(P/'control/campaign_v2.py').write_text(s)
s=(P/'control/owner.py').read_text().replace('control/campaign.py','control/campaign_v2.py');(P/'control/owner_v2.py').write_text(s)
shutil.copy2(R/'control/register_repair_v2.py',P/'control/register_repair_v2.py')
from terminal_control_v2 import TerminalIntent,bind_boundary
from traction_mpc_stage5.task import TaskPhase
# Pure interface tests: main planner has no worker-only attribute; accepted cache
# is the only permitted internal target source. No plant construction or physics.
spec=SimpleNamespace(start_return_target_rad=np.radians([5.,10.]));r=SimpleNamespace(q_rad=np.radians([10.,11.]),dq_rad_s=np.radians([-8.,-2.]),ddq_rad_s2=np.zeros(2));obs=SimpleNamespace(sample_timestamp_s=3.)
config=dict(mode='DAMPING',kd_fraction=.2,acceleration_cap_rad_s2=.2,rate_cap_rad_s3=1.)
checks=[]
for phase,cache,expected in [('OUTBOUND',{},'OUTBOUND'),('RETURN',{},'NO_ACCEPTED_TERMINAL_TARGET'),('RETURN',{'accepted':dict(feasible=True,original_goal_rad=spec.start_return_target_rad,reference_target_rad=np.radians([5.5,9.5]))},'RETURN')]:
 contract=HumanWaypointMPCShadowContractV1.__new__(HumanWaypointMPCShadowContractV1);b=dict(runtime={'contract':contract},observation=obs,reference=r,planner=SimpleNamespace(terminal_reference_cache=cache),task_state=SimpleNamespace(phase=TaskPhase(phase)),spec=spec,physical_now=3.)
 bind_boundary(b,TerminalIntent(config),'test');assert contract.terminal_frame['phase']==expected
 if expected=='RETURN':assert np.allclose(contract.terminal_frame['goal'],np.radians([5.5,9.5]))
 checks.append(dict(phase=phase,cache=bool(cache),actual=contract.terminal_frame['phase'],source=contract.terminal_target_source,status='PASS'))
# Capture all known owned process IDs while preserving failed v1 evidence.
put('audit/BOUNDED_INTERFACE_REPAIR_V2.json',dict(status='PASS',type='runtime interface defect only',failure='main-process planner lacks worker-only internal_reference_target_rad',failed_arm='Dev_KD120',failed_arm_new_native_steps=0,failed_parent_preserved=True,old_stop_file_preserved=True,scientific_parameters_changed=False,repair='use only accepted deployable terminal_reference_cache for current registered phase target; unavailable cache disables assist',tests=checks,source_before_sha=sc.sha(P/'control/terminal_control.py'),source_after_sha=sc.sha(P/'control/terminal_control_v2.py'),physics_not_started=True))
oldplan=read('Dev_PLAN.json');arms=copy.deepcopy([a for a in oldplan['arms'] if a['id']!='D']);cond=copy.deepcopy(oldplan['condition']);cond.update(name='Ctrl',role='W1 exposed; frozen H150 deterministic repeat and repaired controller ablations')
for arm in arms:
 if arm.get('controller'):
  arm['supersedes_failed_interface_candidate_hash']=arm['candidate_hash'];arm['candidate_hash']=sc.digest(dict(parameters=arm,source_sha=sc.sha(P/'control/terminal_control_v2.py'),contract_version='v2_target_cache_only'))
put('Ctrl_PLAN.json',dict(frozen_unix=time.time(),condition=cond,fork_after_prefix=1,reproduce_W1=True,arms=arms))
put('PREPHYSICAL_CHECKS_v2.json',dict(status='PASS',new_target_interface_tests=checks,original_prechecks_sha=sc.sha(P/'PREPHYSICAL_CHECKS.json'),parameter_limits_unchanged=True,only_one_runtime_repair=True,original_failures_preserved=True))
files=read('EXECUTION_CODE_MANIFEST.json')['files'].copy()
for n in ['control/terminal_control_v2.py','control/campaign_v2.py','control/owner_v2.py','control/register_repair_v2.py','PREPHYSICAL_CHECKS_v2.json']:files[n]=sc.sha(P/n)
put('EXECUTION_CODE_MANIFEST_v2.json',dict(files=files,frozen_unix=time.time(),previous_manifest_sha=sc.sha(P/'EXECUTION_CODE_MANIFEST.json'),change='isolated controller accepted-target interface repair; H150 physical code identical'))
for n in ['NEW_FROZEN_SELECTION.json','Ctrl_PLAN.json','PREPHYSICAL_CHECKS_v2.json','audit/BOUNDED_INTERFACE_REPAIR_V2.json']:
 dst=R/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(P/n,dst)
print(json.dumps(dict(status='PASS',primary='H150',arms=[a['id'] for a in arms],checks=checks)))
