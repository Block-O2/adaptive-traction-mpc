"""Static SAME-STATE counterfactuals; zero physics integrations."""
import os,sys,json,gzip,hashlib
from pathlib import Path
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
W=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/commissioning-to-recovery-geometry-compatibility-v1');sys.path.insert(0,str(W))
import human_qualification_R2 as h
rt=h.rt;np=h.np
from dataclasses import replace
from traction_mpc_stage5.architecture_recovery_v2.functional_benchmark import PlanarCuffGeometry
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import RigidTableReferenceEnvelopeV1,CombinedRigidTableClearanceV1
from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant
def load(root,name):p=root/name;return json.loads(p.read_text() if p.exists() else gzip.open(str(p)+'.gz','rt').read())
def geom(rec):return PlanarCuffGeometry(**{k:np.array(v) if isinstance(v,list) else v for k,v in rec.items()})
B=W/'baseline/C5_commissioning_only/runs/C5__commissioning_only';O=W/'baseline/C5_existing_oracle/runs/C5__fixed_population'
hb=load(B,'HANDOFF_EXACT.json');sb=load(B,'summary.json');ro=load(O,'RECOVERY_EXACT.json');ho=load(O,'HANDOFF_EXACT.json')
rb=sb['dev_a_recovery'];q=np.array(rb['start_estimated_state_rad_rad_s'][:2]);dq=np.array(rb['start_estimated_state_rad_rad_s'][2:]);qref=np.array(hb['last_trace']['q_ref_rad'])
fitted=geom(hb['target_model_geometry']);nominal=geom(hb['old_model_geometry']);oracle=geom(ho['target_model_geometry'])
offset=tuple(hb['commissioning_reference_origin']['translation_world_m']);oracleoffset=tuple(ho['commissioning_reference_origin']['translation_world_m'])
frozen_state=dict(estimated_q_rad=q,estimated_dq_rad_s=dq,physical_q_dq_evaluation_only=rb['start_true_state_evaluation_only_rad_rad_s'],emitted_reference_q_rad=qref,emitted_reference_dq_rad_s=hb['last_trace']['dq_ref_rad_s'],emitted_reference_ddq_rad_s2=hb['last_trace']['ddq_ref_rad_s2'],recovery_candidate_origin_q_rad=q,old_emitted_pose=hb['old_emitted_pose'])
state_hash=hashlib.sha256(json.dumps(rt._jsonable(frozen_state),sort_keys=True).encode()).hexdigest()
rows=[]
def test(label,g,off=(0.,0.,0.),upper=.46,factor='geometry'):
 env=RigidTableReferenceEnvelopeV1(g,shank_length_upper_m=upper,cuff_reference_translation_world_m=off)
 margins={k:float(v[0]) for k,v in env.margins(q).items()}
 result=dict(label=label,changed_factor=factor,geometry=vars(g),shank_upper_m=upper,cuff_reference_translation_world_m=off,state_sha256=state_hash,state_unchanged=True,margins_m=margins,minimum_m=min(margins.values()),cuff_center_world_m=env.cuff_centers(q)[0],continuous_continuation_possible_from_this_origin=bool(min(margins.values())>=-1e-9),only_diagnostic=True,physics_integrations=0)
 rows.append(result);return result
base=test('fitted_geometry_currently_consumed',fitted,factor='none')
test('true_effective_geometry_same_state',oracle,factor='effective_geometry_only_known_truth_diagnostic')
test('nominal_geometry_same_state',nominal,factor='effective_geometry_only')
test('fitted_geometry_oracle_recovery_origin_semantics',fitted,factor='reference_origin_semantics_only: both recovery envelopes are fresh zero-offset; no numeric difference')
test('oracle_geometry_commissioning_reference_origin_semantics',oracle,offset,factor='from true_geometry_same_state: commissioning constant tool offset only')
test('fitted_geometry_commissioning_reference_translation',fitted,offset,factor='constant tool-reference offset only')
test('fitted_geometry_oracle_commissioning_translation',fitted,oracleoffset,factor='constant tool-reference offset only')
# Gauge-equivalent coordinate re-expression. This is not a hip lift.
worldhip=fitted.origin_world_m+fitted.hip_plane_m[0]*fitted.plane_x_world+fitted.hip_plane_m[1]*fitted.plane_z_world
gauge=replace(fitted,origin_world_m=worldhip,hip_plane_m=np.zeros(2))
g=test('fitted_geometry_oracle_origin_gauge_same_world_hip',gauge,factor='coordinate gauge only; world geometry unchanged')
assert max(abs(base['margins_m'][k]-g['margins_m'][k]) for k in base['margins_m'])<1e-12
# Explicit nondeployable prior diagnostic. Not a fix and not used dynamically.
test('fitted_geometry_actual_full_shank_bound_DIAGNOSTIC_ONLY',fitted,upper=.40076,factor='structural shank bound only; hidden truth, forbidden as fix')
# Exact ownership label/model activation counterfactual has no inputs in scalar clearance function.
own=dict(base);own.update(label='fitted_geometry_handoff_ownership_label_only',changed_factor='ownership activation label only; same causal geometry and state; no margin dependency');rows.append(own)
selection=rb['terminal_reference_selection'];checks=selection['continuous_path_checks'];first=checks[0];target=np.array(selection['endpoint_candidates'][first['point_index']])
coeff=(target-q)[:,None]*np.array([0.,0.,0.,10.,-15.,6.]);coeff[:,0]=q
env=RigidTableReferenceEnvelopeV1(fitted);cert=env.check_quintic(coeff,1.)
continuous=dict(first_recorded_rejection=first,target_q_rad=target,origin_q_rad=q,reference_dq_rad_s=[0.,0.],reference_ddq_rad_s2=[0.,0.],unit_duration_certificate=cert,executed_recovery_intervals=rb['executed_interval_count'],total_checks=len(checks),all_rejected=all(not r['feasible'] for r in checks),proof='A continuous path including an origin whose certified distal-shank gap is negative cannot have all-time nonnegative gap, regardless of destination, beta, residual or terminal-search density.')
qoracle=np.array(ro['start_estimated_state_rad_rad_s'][:2])
def margins(g,qvalue):return {k:float(v[0]) for k,v in RigidTableReferenceEnvelopeV1(g).margins(qvalue).items()}
non_same_state=dict(label='STATE_REPLACEMENT_DIAGNOSTIC_NOT_SAME_STATE',fitted_at_B_state=margins(fitted,q),oracle_at_B_state=margins(oracle,q),fitted_at_oracle_state=margins(fitted,qoracle),oracle_at_oracle_state=margins(oracle,qoracle),B_q_rad=q,oracle_q_rad=qoracle,changed_factor='q only for each geometry pair; exposes different physical commissioning trajectories, not a deployable state reset')
critical=(worldhip[2]+fitted.thigh_length_m*np.sin(q[0])-rt.SHANK_RADIUS_M-rt.BED_HEIGHT_M-.001)/(-np.sin(q[0]-q[1]))
h.save(W/'SAME_STATE_COUNTERFACTUALS.json',dict(status='COMPLETE_STATIC_ZERO_PHYSICS',frozen_state=frozen_state,state_sha256=state_hash,rows=rows,first_rejected_continuation=continuous,state_replacement_diagnostic=non_same_state,critical_full_shank_upper_m_at_B_handoff=critical,actual_clearance_evaluation_only_m=rb['minimum_true_physical_clearance_m_evaluation_only'],limitations='This is a reference-envelope diagnostic, not proof of future physical safety. Replacing bound with truth is prohibited. Oracle/reference gauge does not mean adding hip height twice.'))
# Source-level causal chain of initialization construction, numerical evidence.
ib=load(B,'INITIALIZATION_ALIGNMENT.json');io=load(O,'INITIALIZATION_ALIGNMENT.json')
pb=np.array(ib['offline_support_setup']['robot_target_position_m']);po=np.array(io['offline_support_setup']['robot_target_position_m'])
hipsame=np.array(ib['plant_qpos_evaluation_only'][:2])-np.array(io['plant_qpos_evaluation_only'][:2])
assert np.max(np.abs(hipsame))==0
h.save(W/'ORACLE_COMMISSIONING_ALIGNMENT.json',dict(first_divergence=dict(stage='model factory before loaded-support solve; physical human initial q unchanged but robot assembly/preload differs',B_geometry=ib['model_geometry'],oracle_geometry=io['model_geometry'],B_initial_qpos_evaluation_only=ib['plant_qpos_evaluation_only'],oracle_initial_qpos_evaluation_only=io['plant_qpos_evaluation_only'],B_robot_attachment_world_m=pb,oracle_robot_attachment_world_m=po,robot_position_delta_m=po-pb,robot_position_delta_norm_m=np.linalg.norm(po-pb),B_support_state=ib['initial_support_state'],oracle_support_state=io['initial_support_state'],B_startup_alignment=ib['startup_alignment_record'],oracle_startup_alignment=io['startup_alignment_record'],source_lines=['runtime.py:247 nominal_control_model','runtime.py:264 solve_loaded_hold_equilibrium(model)','runtime.py:267 nominal_cuff_pose = STAGE5_GEOMETRY.world_from_cuff(start_q)','runtime.py:268 cuff_relative_support = nominal_cuff_pose.inverse().compose(equilibrium.robot_cuff_pose_world)','runtime.py:269 physical_geometry.world_from_cuff(...).compose(cuff_relative_support)'],oracle_reference_semantics_caveat='Existing oracle patch replaces model factory but leaves nominal structural setup frame in preload re-expression. It therefore is not a same-robot-initial-state oracle intervention.'),B_handoff=hb,oracle_handoff=ho,B_recovery=rb,oracle_recovery=ro,main_claim='Oracle passes from a different commissioning trajectory and a positive conservative margin. At B handoff truth geometry still fails. Both recovery paths consume .46m full-shank bound, .001m shank margin, zero cuff-reference offset and same checks.'))
print('COUNTERFACTUALS',[(r['label'],r['margins_m']['distal_shank_m'],r['margins_m']['sleeve_m']) for r in rows])
print('STATE_REPLACEMENT',non_same_state,'critical_full_shank_upper',critical,'init_robot_delta',np.linalg.norm(po-pb))
