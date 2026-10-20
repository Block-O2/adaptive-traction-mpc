from pathlib import Path
import ast,json,hashlib
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1/source');S=R/'stages/stage5_personalized_motion_learning';D=S/'docs/adaptive_human_online_interface_v1'
SRC=S/'src/traction_mpc_stage5'
def location(path,name):
    p=SRC/path;tree=ast.parse(p.read_text())
    n=next(n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name)
    return dict(path=str(p.relative_to(R)),start_line=n.lineno,end_line=n.end_lineno,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def lines(path,needle):
    p=SRC/path;return [dict(path=str(p.relative_to(R)),line=i,text=line.strip()) for i,line in enumerate(p.read_text().splitlines(),1) if needle in line]
runtime='full3d_adaptive_integration_v1/runtime.py';phase='architecture_recovery_v2/phase3_human_waypoint.py'
e={
'commissioning_collection':lines(runtime,'commissioning_samples.append'),
'geometry_estimation':location('architecture_recovery_v2/effective_model.py','fit_effective_geometry'),
'commissioning_replay':location(runtime,'_fit_and_replay_commissioning'),
'dynamic_identifier':location('architecture_recovery_v2/effective_model.py','OnlineEffectiveDynamicsIdentifier'),
'belief':location(phase,'AdaptiveHumanBeliefV22'),
'continual_update':lines(runtime,'updater.observe_dynamics('),
'residual_update':location(phase,'observe_dynamics'),
'model_reconstruction':location(phase,'human_model'),
'runtime_assignment':lines(runtime,'runtime["model"] = belief.human_model()'),
'contract_consumption':lines(runtime,'runtime["contract"].human_model = runtime["model"]'),
'planner_consumption':location(phase,'AdaptiveHumanWaypointHWMPCV22'),
'mechanics_consumption':location(phase,'AdaptiveMechanicsScreenV22'),
'execution_inverse_dynamics':lines('human_waypoint_shadow.py','action = _model_inverse_dynamics('),
'execution_incremental_mass':lines(runtime,'model.mass_matrix(state[:2])'),
'execution_supervisor':lines(runtime,'human_model=model,'),
'repetition_persistence':lines(runtime,'session_context.update(runtime=runtime, updater=updater, fit=fit,'),
'inter_repetition_consumption':location(runtime,'advance_inter_rep_boundary'),
'observer':location('controller_interface.py','InterfaceAwareHumanStateObserver'),
'residual_model':location('architecture_recovery_v2/functional_benchmark.py','StateResidualHumanModel'),
}
from sys import path
for stage in ('stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning'):path.insert(0,str(R/'stages'/stage/'src'))
from traction_mpc_stage4.estimator_v2 import DYNAMIC_BASE_PARAMETER_NAMES
record=dict(status='STRUCTURALLY_CONNECTED_EXECUTION_CONFIRMATION_REQUIRED',effective_dynamic_vector=list(DYNAMIC_BASE_PARAMETER_NAMES),geometry_fields=['hip_xz_m[2]','thigh_length_m','knee_to_cuff_m'],residual_shape=[2,5],source=e,geometry_scope='Cuff-observable effective geometry only; full shank length and cuff fraction are not separately identified. Full shank clearance uses an explicit structural upper-length prior.',online_geometry_update=False,geometry_update_scope='Commissioning fit is retained during task; continual updates modify beta and state torque residual.',truth_firewall='Estimation inputs are reconstructed causal cuff pose/twist/wrench. MuJoCo Human joint states are evaluation-only. Measurement derivative assumption remains the existing ideal simulated sensor boundary.',source_does_not_prove_generalization=True)
(D/'CURRENT_HUMAN_ADAPTATION_SOURCE_EVIDENCE.json').write_text(json.dumps(record,indent=2)+'\n')
md='# Current Human adaptation dataflow\n\nQuestion A: source audit only; execution qualification is reported separately.\n\n'
md+='Measured robot/cuff pose, twist and wrench → effective geometry fit → causal state and transmitted-torque reconstruction → 11-parameter dynamic identification and bounded 2×5 state torque residual → immutable belief snapshot → reconstructed Human model → planning, mechanics screening, inverse-dynamics execution and incremental-response mass matrix → continued 20 ms task updates → repetition-boundary updater persistence.\n\n'
md+='Effective beta names: '+', '.join(DYNAMIC_BASE_PARAMETER_NAMES)+'.\n\nGeometry estimates hip X/Z, thigh length and knee-to-cuff distance. Full shank length/cuff fraction are not separately identifiable. Task geometry is commissioning-frozen; dynamics and residual continue online. No population generalization follows from this structure.\n\n'
for k,v in e.items():
    md+='- '+k+': '+('; '.join(f"`{x['path']}:{x.get('line',x.get('start_line'))}`" for x in (v if isinstance(v,list) else [v])))+'.\n'
(D/'CURRENT_HUMAN_ADAPTATION_DATAFLOW.md').write_text(md)
print(json.dumps({'source_audit':record['status'],'entries':len(e)}))
