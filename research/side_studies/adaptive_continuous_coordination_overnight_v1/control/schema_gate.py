from pathlib import Path
import os,sys,json,time,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
P=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(P/'prototype')]+[str(P/'source/stages'/s/'src') for s in ['stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning']]
from continuous import Piece,LocalQuintic
from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedule,_quintic_coefficients
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointCandidate
from traction_mpc_stage5.task import TaskPhase
checks=[]
for ident in ['development_repair2_B0_original','development_repair2_quality_NATIVE_SCALAR_18_063']:
 s=json.loads((P/'key_traces'/ident/'summary.json').read_text())
 for i,r in enumerate(s['learning_records']):
  d=r['selected_plan']['schedule'];q0,v0,q1,v1=[np.asarray(d[k]) for k in ['start_q_rad','start_dq_rad_s','target_q_rad','target_dq_rad_s']];T=d['duration_s'];c=_quintic_coefficients(q0,v0,q1,v1,T)
  frozen=json.loads((P/'MATH_VALIDATION.json').read_text())
  o=Piece(c,T);curve=LocalQuintic.from_piece(o,[T/4,T/2,3*T/4]);tt=np.linspace(0,T,1001);errors=[np.max(abs(curve.evaluate(tt,k)-o.evaluate(tt,k))) for k in range(3)];assert max(errors)<1e-9
  checks.append(dict(id=ident,index=i,max_sample_errors=errors))
# Genuine old schedule constructor, no fake physics state or safety certificate.
s=json.loads((P/'key_traces/development_repair2_B0_original/summary.json').read_text());d=s['learning_records'][0]['selected_plan']['schedule'];T=d['duration_s'];q0,v0,q1,v1=[np.asarray(d[k]) for k in ['start_q_rad','start_dq_rad_s','target_q_rad','target_dq_rad_s']];o=Piece(_quintic_coefficients(q0,v0,q1,v1,T),T)
candidate=HumanWaypointCandidate(label='schema_counterexample',phase=TaskPhase.OUTBOUND,phase_goal_rad=np.radians([120,120]),q_waypoint_rad=q1,dq_waypoint_rad_s=v1)
kwargs=dict(candidate=candidate,start_q_rad=q0,start_dq_rad_s=v0,duration_s=T,maximum_reference_velocity_rad_s=d['maximum_reference_velocity_rad_s'],maximum_reference_acceleration_rad_s2=d['maximum_reference_acceleration_rad_s2'],maximum_causal_20ms_reference_acceleration_rad_s2=d['maximum_causal_20ms_reference_acceleration_rad_s2'],maximum_nominal_tracking_acceleration_rad_s2=d['maximum_nominal_tracking_acceleration_rad_s2'],nominal_completion_time_s=d['nominal_completion_time_s'],minimum_reference_shank_clearance_m=d['minimum_reference_shank_clearance_m'])
old=QuinticHumanWaypointSchedule(coefficients=o.c,**kwargs);curve=LocalQuintic.from_piece(o,[.25*T,.5*T,.75*T]);changed=curve.update(2,dq=np.radians([.3,-.2]))
try:
 QuinticHumanWaypointSchedule(coefficients=np.stack([x.c for x in changed.pieces]),**kwargs)
 schema_rejection=None
except ValueError as e:schema_rejection=str(e)
assert schema_rejection=='coefficients must be a finite 2x6 matrix'
try:changed.collapse_original(o);collapse_rejection=None
except ValueError as e:collapse_rejection=str(e)
assert collapse_rejection
# Holding q/v/a at the two endpoints fixes all six coefficients per joint.
A=np.array([[1,0,0,0,0,0],[0,1,0,0,0,0],[0,0,2,0,0,0],[1,1,1,1,1,1],[0,1,2,3,4,5],[0,0,2,6,12,20]],float);assert np.linalg.matrix_rank(A)==6
result=dict(status='NONZERO_LOCAL_CURVE_BLOCKED_BY_ORIGINAL_INTERFACE',classification=['SOURCE_CONFIRMED','MATH_VERIFIED'],physical_starts=0,original_function_checks=checks,constructor=dict(original_shape=list(o.c.shape),proposed_shape=list(np.stack([x.c for x in changed.pieces]).shape),result=schema_rejection),outer_boundary_rank=int(np.linalg.matrix_rank(A)),endpoint_compression=dict(interior_q_error_rad=float(np.max(abs(changed.evaluate(np.linspace(0,T,2001))-curve.evaluate(np.linspace(0,T,2001)))))),safe_adapter=dict(zero_curve_collapse='PASS returns original immutable polynomial',nonzero_curve=collapse_rejection),unsafe_shortcut='Changing only sample() while retaining coefficients and original proof would certify a different path; forbidden and never executed',repair=dict(attempt='legacy-schema subsegments with zero interior acceleration',status='FAIL_M1',evidence='MATH_VALIDATION.json/M6',effect='No safety bypass or production edits'),P0='baseline-equivalent zero collapse being measured separately',P1='NOT_ADMITTED; zero nonzero new-curve physical rollouts',P2='NOT_EVALUABLE for new curve',force_search='STOP_PENDING_FULL_PATH_INTERFACE')
(P/'PHYSICAL_INTERFACE_PREFLIGHT.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:result[k] for k in ['status','constructor','endpoint_compression','P1','force_search']}),flush=True)
