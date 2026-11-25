"""Historical estimated Human belief; no truth, synthetic residual or actuation."""
import bootstrap
import json
import numpy as np
from pathlib import Path
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveHumanBeliefV22
from traction_mpc_stage5.high_rom_v1 import deployable_prior, CONFIG_PATH
from traction_mpc_stage5.task import load_goal_task_spec, TaskPhase
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import SessionClearanceContract
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import CombinedRigidTableClearanceV1, RigidTableReferenceEnvelopeV1
from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedulerV1
from phase_coordinates import Phase, State, Limits
from continuous_completion import make_plan
from native_integration import schedule

def native_context():
    archive=(Path(__file__).resolve().parents[4] / 'adaptive-traction-mpc-side-studies/force_mechanism_waypoint_v3/key_traces/historical_B/summary.json')
    h=json.loads(archive.read_text())['commissioning']['handoff_belief']
    geom=PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in h['effective_geometry'].items()})
    keys=['beta','state_residual_weights_nm','sequence','dynamics_sample_count','accepted_beta_update_count',
          'residual_update_count','geometry_source','dynamics_source','residual_source','residual_limit_nm']
    belief=AdaptiveHumanBeliefV22(geometry=geom,rom_human=deployable_prior(),
        **{k:np.asarray(h[k]) if k in ('beta','state_residual_weights_nm') else h[k] for k in keys})
    spec=load_goal_task_spec(CONFIG_PATH)
    clearance=CombinedRigidTableClearanceV1(SessionClearanceContract(geom),RigidTableReferenceEnvelopeV1(geom),True)
    scheduler=QuinticHumanWaypointSchedulerV1(spec,belief.human_model(),clearance_evaluator=clearance,
        require_continuous_nonpenetrating_path=True,preserve_task_endpoint_clearance_floor=True,
        reference_velocity_fraction=.5,reference_acceleration_fraction=.25)
    bounds=np.c_[belief.human_model().q_min_rad,belief.human_model().q_max_rad]
    limits=Limits(np.asarray(spec.task_joint_velocity_limit_rad_s)*.5,np.asarray(spec.task_joint_acceleration_limit_rad_s2)*.25,bounds)
    return belief,spec,scheduler,limits

def plan_fixture(start_deg=(95,90), u=(.1,.13), h=.5):
    belief,spec,scheduler,limits=native_context()
    ph=Phase(np.radians(start_deg),spec.outbound_goal_target_rad)
    plan,_=make_plan(State([0,0],[0,0],[0,0]),u,h,ph,limits,1e-10)
    return belief,spec,scheduler,limits,ph,schedule(plan,ph,TaskPhase.OUTBOUND)
