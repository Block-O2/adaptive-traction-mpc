"""Parameter-only model provisioning. Never opens a MuJoCo environment."""
from study_common import *
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry,nominal_base_parameters
from traction_mpc_stage5.architecture_recovery_v2.functional_benchmark import StateResidualHumanModel
from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime_coordination_residual_v2 import high_rom_deployable_prior
def provision():
 case,_=load_case_options();human,g,_,_=hidden_plant(case)
 rotation=g.world_from_human.rotation
 geometry=PlanarCuffGeometry(origin_world_m=g.world_from_human.translation.copy(),plane_x_world=rotation[:,0],joint_axis_world=rotation[:,1],plane_z_world=rotation[:,2],hip_plane_m=np.zeros(2),thigh_length_m=human.thigh_length_m,knee_to_cuff_in_cuff_m=np.array([human.sleeve_center_m,0.]))
 record=dict(beta=nominal_base_parameters(human),residual_weights_nm=np.zeros((2,5)),geometry=asdict(geometry),source='registered case physical parameter mapping; no simulated states, forces or future trajectories',rom_source='unchanged deployable high-ROM prior; anatomical clearance upper bound remains frozen B',case_sha256=digest(case),provisioning_changes_physics=False,scope='known effective mechanics for research candidate cost predictions; B actuator/observer/commissioning/safety models stay frozen estimated and common to all arms')
 save('KNOWN_MODEL_PARAMETERS.json',record);return record
def model():
 p=L/'KNOWN_MODEL_PARAMETERS.json';r=read(p.name) if p.exists() else provision()
 return StateResidualHumanModel(PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in r['geometry'].items()}),np.asarray(r['beta']),high_rom_deployable_prior(),residual_weights_nm=np.asarray(r['residual_weights_nm']))
if __name__=='__main__':
 r=provision();print(json.dumps(dict(status='KNOWN_MODEL_PARAMETER_ONLY',hash=digest(r))))
