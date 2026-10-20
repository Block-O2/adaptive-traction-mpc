from pathlib import Path
import os,sys,json,time,ast,hashlib,types
P=Path(__file__).resolve().parents[1];A=P.parent/'m2_18d_terminal_response_repair_v1'
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',TMPDIR=str(P/'tmp'),MPLCONFIGDIR=str(P/'tmp/mpl'))
sys.dont_write_bytecode=True;sys.path.insert(0,str(P/'code'))
import study_common as sc, matched_harness as mh, analyze_matched as am
import numpy as np
from terminal_repair import FixedTerminalScheduler,TerminalRepairPlanner
from rich_planner import RichFreePlanner
from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedulerV1
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointCandidate
from traction_mpc_stage5.task import TaskPhase
from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import CombinedRigidTableClearanceV1,RigidTableReferenceEnvelopeV1
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22,AdaptiveHumanBeliefV22
def put(n,x):mh.put(P/n,sc.clean(x))
assert sc.STUDY==P and mh.PACKAGE==P and am.S==P
assert json.loads((P/'audit/T_EXECUTION_CONTRACT_AUDIT.json').read_text())['status']=='PASS'
assert json.loads((P/'audit/NEW_PREFIX_PROVENANCE.json').read_text())['status']=='PASS'
assert sc.sha(P/'code/terminal_repair.py')==sc.sha(A/'code/terminal_repair.py')
assert sc.sha(P/'FROZEN_18D.json')==sc.sha(A/'FROZEN_18D.json')
assert sc.sha(P/'MOTION_ACCEPTANCE_PROTOCOL.json')==sc.sha(A/'MOTION_ACCEPTANCE_PROTOCOL.json')
imports=[]
for name,m in list(sys.modules.items()):
 f=getattr(m,'__file__',None)
 if f and '/home/hank/coding/' in f:
  assert Path(f).resolve().is_relative_to(P),(name,f)
  imports.append(dict(module=name,path=f))
case,options=sc.load_case_options();spec=hidden_plant(case)[2]
su=json.loads((A/'source/results/N2_E/summary.json').read_text());lr=su['learning_records'][5];ss=lr['selected_plan']['schedule'];belief_record=lr['adaptive_state'];geo=belief_record['effective_geometry']
geometry=sc.rt.PlanarCuffGeometry(**{k:np.array(v) if isinstance(v,list) else v for k,v in geo.items()})
belief=AdaptiveHumanBeliefV22(geometry=geometry,beta=np.array(belief_record['beta']),state_residual_weights_nm=np.array(belief_record['state_residual_weights_nm']),sequence=belief_record['sequence'],dynamics_sample_count=belief_record['dynamics_sample_count'],accepted_beta_update_count=belief_record['accepted_beta_update_count'],residual_update_count=belief_record['residual_update_count'],rom_human=sc.rt.high_rom_deployable_prior())
model=belief.human_model();shank=sc.rt.SessionClearanceContract(geometry);clearance=CombinedRigidTableClearanceV1(shank,RigidTableReferenceEnvelopeV1(geometry),use_monotonic_certificate=options.get('monotonic_clearance_certificate',False))
sched=QuinticHumanWaypointSchedulerV1(spec,model,reference_period_s=.005,clearance_evaluator=clearance,clearance_source='ARCHIVED_CAUSAL_MODEL_RECONSTRUCTION',preserve_task_endpoint_clearance_floor=True,require_continuous_nonpenetrating_path=True,use_duration_lower_bound=options.get('duration_lower_bound',False),reference_velocity_fraction=options.get('reference_velocity_fraction',.6) if options.get('reference_pacing',False) else 1.,reference_acceleration_fraction=options.get('reference_acceleration_fraction',.5) if options.get('reference_pacing',False) else 1.)
candidate=HumanWaypointCandidate(label='archived_terminal_interface_test',phase=TaskPhase.OUTBOUND,phase_goal_rad=np.array(spec.outbound_goal_target_rad),q_waypoint_rad=np.array(ss['target_q_rad']),dq_waypoint_rad_s=np.array(ss['target_dq_rad_s']))
kw=dict(current_q_hat_rad=np.array(ss['start_q_rad']),current_dq_hat_rad_s=np.array(ss['start_dq_rad_s']),candidate=candidate,phase_elapsed_s=su['decisions'][5]['phase_elapsed_s'])
old=sched.plan_reference_contract(**kw);proxy=FixedTerminalScheduler(sched);new=proxy.plan_reference_contract(**kw)
assert abs(old.duration_s-ss['duration_s'])<1e-12
assert np.max(abs(old.maximum_reference_acceleration_rad_s2-np.array(ss['maximum_reference_acceleration_rad_s2'])))<1e-10
assert abs(new.duration_s-.33)<1e-12
assert np.array_equal(old.start_q_rad,new.start_q_rad) and np.array_equal(old.start_dq_rad_s,new.start_dq_rad_s)
for obj in [old,new]:
 first=obj.sample(0);last=obj.sample(obj.duration_s)
 assert np.max(abs(first.q_rad-kw['current_q_hat_rad']))<1e-10
 assert np.max(abs(first.dq_rad_s-kw['current_dq_hat_rad_s']))<1e-10
 assert np.max(abs(first.ddq_rad_s2))<1e-10
 assert np.max(abs(last.q_rad-candidate.q_waypoint_rad))<1e-10
 assert np.max(abs(last.dq_rad_s-candidate.dq_waypoint_rad_s))<1e-10
 assert np.max(abs(last.ddq_rad_s2))<1e-10
 assert AdaptiveMechanicsScreenV22().evaluate(belief,candidate,obj)['feasible']
# Invalid grid and too short requests must fail through the original interface.
rejections=[]
for duration in [.331,.005]:
 try:sched.plan_fixed_duration_reference_contract(**kw,duration_s=duration)
 except ValueError as e:rejections.append(str(e))
assert len(rejections)==2
for d in ['source','code','deps','control']:
 for f in (P/d).rglob('*.py'):ast.parse(f.read_text(),filename=str(f))
semantic=[]
for d in ['source','code','deps','weights']:
 for f in (P/d).rglob('*'):
  if not f.is_file() or 'results' in f.parts or '__pycache__' in f.parts or f.name=='terminal_repair.py':continue
  before=A/f.relative_to(P)
  expected=before.read_bytes()
  if f.suffix in ['.py','.json','.xml','.yaml','.yml','.toml']:
   try:expected=before.read_text().replace(str(A),str(P)).encode()
   except UnicodeError:pass
  assert f.read_bytes()==expected,str(f)
  semantic.append(str(f.relative_to(P)))
manifest={str(f.relative_to(P)):sc.sha(f) for d in ['source','code','deps','weights','control'] for f in (P/d).rglob('*') if f.is_file() and '__pycache__' not in f.parts and 'results' not in f.parts}
for n in ['RUN_PLAN.json','FROZEN_18D.json','MOTION_ACCEPTANCE_PROTOCOL.json','INTERVENTION_PROTOCOL.md','output/SHARED_COORDINATION_ACTION_CONTRACT.json']:manifest[n]=sc.sha(P/n)
put('EXECUTION_CODE_MANIFEST.json',dict(files=manifest,frozen_unix=time.time(),imports=imports))
put('PREPHYSICAL_CHECKS.json',dict(status='PASS',unix=time.time(),no_physics_started=not (P/'ATTEMPTS.jsonl').exists(),original_execution_semantics_preserved_files=len(semantic),frozen_parameters_and_plateau_identity=True,motion_protocol_byte_identity=True,imports_within_closure=True,source_ast_pass=True,archived_original_duration_exact=True,original=old.record(),intervention=new.record(),proxy=proxy.record,rejection_tests=rejections,original_mechanics_pass=True,original_continuous_geometry_pass=True,scope='Real original scheduler on archived causal model/reference; mathematical evidence only, no physics; live current admission still mandatory'))
print('PREPHYSICAL PASS',proxy.record,'knee reference amax original/new',np.rad2deg(old.maximum_reference_acceleration_rad_s2[1]),np.rad2deg(new.maximum_reference_acceleration_rad_s2[1]),flush=True)
