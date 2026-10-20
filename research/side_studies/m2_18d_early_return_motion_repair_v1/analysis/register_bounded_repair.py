from pathlib import Path
import os,sys,json,time,ast,hashlib,copy
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
A=P;H=P.parent/'m2_18d_w1_d_qualification_v1'
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');sys.dont_write_bytecode=True;sys.path[:0]=[str(P/'control'),str(P/'code')]
import numpy as np
import study_common as sc,matched_harness as mh
from round_planner import RoundPlanner,FixedDuration
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveHumanBeliefV22,AdaptiveMechanicsScreenV22
from traction_mpc_stage5.task import load_goal_task_spec,TaskPhase
from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedulerV1
from traction_mpc_stage5.human_waypoint_feedback_mpc import HumanWaypointFeedbackMPCConfigV1
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import CombinedRigidTableClearanceV1,RigidTableReferenceEnvelopeV1
from traction_mpc_stage5.full3d_adaptive_integration_v1.safe_fallback import _prepare_single_decision
from traction_mpc_stage5.full3d_adaptive_integration_v1.activation_validation import validate_rolling_composite
from traction_mpc_stage5.full3d_adaptive_integration_v1.rolling_suffix_splice import RollingSuffixCompositeSchedule
from dataclasses import replace
def read(n):return json.loads((P/n).read_text())
def put(n,x):mh.put(P/n,sc.clean(x))
assert not (P/'repair_PLAN.json').exists()
results=read('EXPERIMENT_RESULTS.json')['rows'];development=[r for r in results if r['candidate'].get('early')];assert len(development)==2 and not any(r['eligible_primary'] for r in development)
assert all(r['motion']['failed_requirements']==['acceleration_deg_s2/p95_abs','excursion'] for r in development)
src=(H.parent/'m2_18d_t_second_round_coordination_v1/control/register.py').read_text();tree=ast.parse(src);s=ast.get_source_segment(src,next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='fixture')).replace('source/results/V1_T','source/results/W1dev_ER110');exec(s)
fx=fixture(12);prior=fixture(11);planner=fx['planner'];old=fx['schedule'];duration=float(np.ceil(old.duration_s*1.2/.005-1e-10)*.005);native=planner.scheduler;planner.scheduler=FixedDuration(native,duration);planner.round_forced_velocity=np.array(fx['archived']['target_dq_rad_s'])
try:r=planner._evaluate(**fx['evaluate_args'])
finally:planner.scheduler=native;planner.round_forced_velocity=None
assert r.feasible,r.rejection_reason
prepared=_prepare_single_decision(replace(fx['decision'],executed=r),planner,fx['belief']);new=prepared.executed.schedule;composite=RollingSuffixCompositeSchedule(prefix=prior['schedule'].safe_escape.bridge,prefix_start_s=0.,suffix=new,request_id=fx['context']['request_id']);d=fx['decision_record'];tr=np.load(P/'source/results/W1dev_ER110/trace.npz');idx=int(np.argmin(abs(tr['time_s']-d['activation_timestamp_s'])));cur=composite.sample(0.)
future=dict(spec=planner.spec,estimated_state=tr['estimated_human_state_rad_rad_s'][idx],estimated_acceleration=tr['actual_human_acceleration_rad_s2'][idx],reference_acceleration=cur.ddq_rad_s2,acceleration_valid=bool(tr['actual_human_acceleration_valid'][idx]),revalidation_capture_ns=105000000,now_ns=105000000,original_capture_ns=100000000,request_plan_version=new.version,original_sample_s=d['request_measurement_timestamp_s'],revalidation_sample_s=d['activation_timestamp_s'],age_policy='simulation')
val=validate_rolling_composite(composite=composite,belief=fx['belief'],request_sequence=fx['belief'].sequence,clearance=native.clearance_evaluator,spec=planner.spec,phase=fx['evaluate_args']['phase'],request_phase=fx['evaluate_args']['phase'],remaining_s=fx['evaluate_args']['phase_remaining_s']-.005,current_reference_state=np.r_[cur.q_rad,cur.dq_rad_s],current_reference_acceleration=cur.ddq_rad_s2,future_handoff=future,now_physics_s=d['activation_timestamp_s'])
row=dict(status='PASS' if val['feasible'] else 'BLOCKED',duration_factor=1.2,slot=4,old_duration_s=old.duration_s,new_duration_s=duration,old_reference_vmax_deg_s=np.rad2deg(old.maximum_reference_velocity_rad_s),old_reference_amax_deg_s2=np.rad2deg(old.maximum_reference_acceleration_rad_s2),new_reference_vmax_deg_s=np.rad2deg(new.maximum_reference_velocity_rad_s),new_reference_amax_deg_s2=np.rad2deg(new.maximum_reference_acceleration_rad_s2),current_admission=val,safe_escape=True,C2=True,fresh_certificate=new.continuous_clearance_certificate)
put('audit/BOUNDED_REPAIR_PRECHECK.json',row);assert val['feasible'],'NO_LEGAL_BOUNDED_REPAIR'
base=copy.deepcopy(read('W1dev_PLAN.json'));base['condition']['name']='repair';base['condition']['role']='W1 one bounded development repair; same seed and legal prefixes';base['frozen_unix']=time.time();base.pop('metadata_repair',None);base['arms']=base['arms'][:3]
c=copy.deepcopy(next(c for c in read('W1dev_PLAN.json')['arms'] if c['id']=='ER110'));c['id']='ER110_R4_120';c['early'].append(dict(phase='RETURN',slot=4,duration_factor=1.2));base['arms'].append(c)
protocol=dict(version='bounded_repair_v1',frozen_unix=time.time(),candidate=c,base_candidate='W1dev_ER110',single_added_factor='RETURN4 selected duration x1.20, ceil5ms; original live selected target and pass velocity unchanged',reason='Both early RETURN1 candidates clear velocity p95/amax/jerk gates but retain a95/excursion. ER110 late RETURN4 interval16.09325–16.5445 contributes1806 high acceleration samples; irreversible crossing16.417; excursion crossing16.57375. Added intervention takes effect near15.380, before either.',selection='Use ER110 as smaller early factor, not minimum J_F. One added duration factor1.20 selected before this physics; no sweep, no second repair.',mathematical_limits='Reference peaks and current-model checks are predictions, not physical qualification.',budgets=dict(development_starts_after_repair=13,remaining_validation_START=11,total_cap=24),validation_rule='Only if every original gate and gain criteria passes, freeze this new composite identity before deterministic repeat and unused W2; validation never reselects primary',code_identity='same frozen EarlyReturnPlanner, already bounded factors1..1.30 and slot-intent interface; no source changes or certificate reuse')
put('BOUNDED_REPAIR_PROTOCOL.json',protocol);base['bounded_repair_protocol_sha256']=sc.sha(P/'BOUNDED_REPAIR_PROTOCOL.json');base['precheck_sha256']=sc.sha(P/'audit/BOUNDED_REPAIR_PRECHECK.json');put('repair_PLAN.json',base)
(P/'INTERVENTION_PROTOCOL_BOUNDED_REPAIR.md').write_text('# 一次有界开发修复（运行前注册）\n\n'+json.dumps(sc.clean(protocol),indent=2,ensure_ascii=False)+'\n\n初始两个失败候选全部保留。原INTERVENTION_PROTOCOL.md、原控制代码manifest及B/T/D身份均不改。新参数由repair_PLAN.json SHA随每次START记录。\n')
print(json.dumps(sc.clean({k:row[k] for k in ['status','old_duration_s','new_duration_s','old_reference_amax_deg_s2','new_reference_amax_deg_s2']})),flush=True)
