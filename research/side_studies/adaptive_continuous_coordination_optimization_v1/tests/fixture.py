from pathlib import Path
import os,sys,json
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
P=Path(__file__).resolve().parents[1];sys.dont_write_bytecode=True;sys.path.insert(0,str(P/'code'))
import study_common as sc
import numpy as np
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveHumanBeliefV22,AdaptiveHumanWaypointHWMPCV22
from traction_mpc_stage5.task import load_goal_task_spec,TaskPhase
from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedulerV1
from traction_mpc_stage5.human_waypoint_feedback_mpc import HumanWaypointFeedbackMPCConfigV1
from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime_coordination_residual_v2 as rt
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import CombinedRigidTableClearanceV1,RigidTableReferenceEnvelopeV1
from traction_mpc_stage5.full3d_adaptive_integration_v1.coordination_residual_v2 import NativeResidualPlannerV2
from traction_mpc_stage5.full3d_adaptive_integration_v1.safe_fallback import _prepare_single_decision

def fixture(index=1):
 s=json.loads((P/'key_traces/historical_B/summary.json').read_text());h=s['commissioning']['handoff_belief'];geometry=PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in h['effective_geometry'].items()})
 keys=['beta','state_residual_weights_nm','sequence','dynamics_sample_count','accepted_beta_update_count','residual_update_count','geometry_source','dynamics_source','residual_source','residual_limit_nm']
 belief=AdaptiveHumanBeliefV22(geometry=geometry,rom_human=rt.high_rom_deployable_prior(),**{k:np.asarray(h[k]) if k in ['beta','state_residual_weights_nm'] else h[k] for k in keys})
 spec=load_goal_task_spec(P/'source/stages/stage5_personalized_motion_learning/configs/high_rom_v1/stage5_goal_task_120_v1.json')
 clearance=CombinedRigidTableClearanceV1(rt.SessionClearanceContract(geometry),RigidTableReferenceEnvelopeV1(geometry),use_monotonic_certificate=True)
 scheduler=QuinticHumanWaypointSchedulerV1(spec,belief.human_model(),reference_period_s=.005,clearance_evaluator=clearance,preserve_task_endpoint_clearance_floor=True,require_continuous_nonpenetrating_path=True,use_duration_lower_bound=True,reference_velocity_fraction=.5,reference_acceleration_fraction=.25)
 planner=NativeResidualPlannerV2(spec,scheduler,HumanWaypointFeedbackMPCConfigV1(mechanics_duration_search=True));planner.pass_through_waypoints=True;planner.robust_terminal_center=True;planner.robust_hold_reference=True;planner.safe_fallback_enabled=True;planner.causal_tracking_offset_clearance=True;planner.residual_spec={}
 d=s['decisions'][index];snapshot=s['learning_records'][index]['selected_plan']['execution_screen']['causal_tracking_offset_clearance']['reference_snapshot'];planner.tracking_reference_snapshot={k:np.asarray(v) if isinstance(v,list) else v for k,v in snapshot.items()}
 args=dict(belief=belief,current_deployable_state=np.asarray(d['deployable_state_rad_rad_s']),current_reference_state=np.asarray(d['reference_state_rad_rad_s']),phase=TaskPhase(d['phase']),phase_elapsed_s=d['phase_elapsed_s'],phase_remaining_s=d['phase_remaining_s'],value_evaluator=None)
 decision=AdaptiveHumanWaypointHWMPCV22(planner).decide(**args);decision=_prepare_single_decision(decision,planner,belief)
 source=float(d['request_measurement_timestamp_s']);context=dict(request_id=d['timing_request_id'],source_sample_time_s=source,sensor_capture_ns=123456789,phase=d['phase'],phase_remaining_s=d['phase_remaining_s'],perturbation_deg=[0.,0.])
 return dict(summary=s,decision=decision,planner=planner,belief=belief,spec=spec,clearance=clearance,args=args,context=context)
if __name__=='__main__':
 f=fixture();print('FIXTURE',f['decision'].executed.schedule.duration_s,f['decision'].executed.schedule.candidate.label)
