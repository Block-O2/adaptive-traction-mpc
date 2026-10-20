"""Reference-origin/ownership audit, static; retains actual handoff."""
import sys,os,json
from pathlib import Path
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
W=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/commissioning-to-recovery-geometry-compatibility-v1');sys.path.insert(0,str(W))
import human_qualification_R2 as h
rt=h.rt;np=h.np
from traction_mpc_stage5.architecture_recovery_v2.functional_benchmark import PlanarCuffGeometry
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import RigidTableReferenceEnvelopeV1,CombinedRigidTableClearanceV1
from traction_mpc_stage5.full3d_adaptive_integration_v1.terminal_reference import select_robust_terminal_reference
from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant
B=W/'baseline/C5_commissioning_only/runs/C5__commissioning_only';hb=json.loads((B/'HANDOFF_EXACT.json').read_text());rb=json.loads((B/'RECOVERY_EXACT.json').read_text());c=json.loads((W/'CONTRACT_R2.json').read_text());_,_,spec,_=hidden_plant(c['conditions'][5]['case'])
g=PlanarCuffGeometry(**{k:np.array(v) if isinstance(v,list) else v for k,v in hb['target_model_geometry'].items()});env=RigidTableReferenceEnvelopeV1(g)
clear=CombinedRigidTableClearanceV1(rt.SessionClearanceContract(g),env,use_monotonic_certificate=True)
pose=hb['old_emitted_pose'];oldp=np.array(pose['translation']);oldR=np.array(pose['rotation'])
physicalq=np.array(rb['start_estimated_state_rad_rad_s'][:2]);qold=np.array(hb['last_trace']['q_ref_rad']);qpose=g.estimate_q(oldp,oldR)
rows=[]
for label,origin in [('actual_fitted_causal_observation',physicalq),('reuse_old_nominal_joint_numbers_as_fitted_reference',qold),('reexpress_old_emitted_robot_pose_in_fitted_geometry',qpose)]:
 newpose=g.cuff_pose(origin);selection=select_robust_terminal_reference(spec=spec,goal=spec.start_return_target_rad,clearance=clear,origin=origin)
 rows.append(dict(label=label,physical_q_dq_unchanged=True,emitted_reference_q_dq_ddq_unchanged=True,changed_factor='candidate reference origin only',candidate_origin_q_rad=origin,origin_margins_m={k:float(v[0]) for k,v in env.margins(origin).items()},actual_handoff_margins_still_m={k:float(v[0]) for k,v in env.margins(physicalq).items()},terminal_selection=selection,fitted_reference_position_difference_from_old_emitted_pose_m=newpose.translation-oldp,pose_translation_difference_norm_m=np.linalg.norm(newpose.translation-oldp),rotation_frobenius_difference=np.linalg.norm(newpose.rotation-oldR),valid_same_physical_safety_certificate=bool(min(float(v[0]) for v in env.margins(physicalq).values())>=0)))
assert all(not r['valid_same_physical_safety_certificate'] for r in rows)
h.save(W/'REFERENCE_OWNERSHIP_COUNTERFACTUALS.json',dict(status='STATIC_COMPLETE',physics_integrations=0,rows=rows,interpretation='Changing only the nominal/candidate origin can make a path certificate positive for a hypothetical reference, but cannot remove the current fitted-state distal-shank violation. Reusing old nominal joint numbers in the new geometry is not a coordinate-preserving map; the fitted inverse of emitted robot pose is separately checked. A positive hypothetical reference certificate alone is insufficient to authorize recovery from the actual failed handoff. No reset, offset carryover, double-hip shift or bypass implemented.'))
print([(r['label'],r['origin_margins_m']['distal_shank_m'],r['terminal_selection']['feasible'],r['pose_translation_difference_norm_m']) for r in rows])
