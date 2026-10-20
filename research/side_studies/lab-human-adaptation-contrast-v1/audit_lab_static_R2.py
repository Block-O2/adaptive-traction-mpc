"""Zero-time-integration physical propagation and prospective cuff/IK audit."""
import os
for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS']:os.environ[name]='1'
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1'
os.nice(19)
from pathlib import Path
from dataclasses import replace,asdict
import sys,json,hashlib,time,resource,traceback,importlib.metadata,gc
from datetime import datetime,timezone
W=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/lab-human-adaptation-contrast-v1');R=W/'snapshot';S=R/'stages/stage5_personalized_motion_learning'
sys.dont_write_bytecode=True
for stage in ['stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning']:sys.path.insert(0,str(R/'stages'/stage/'src'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,x):(W/n).write_text(json.dumps(rt._jsonable(x),indent=2,allow_nan=False)+'\n')
start=time.monotonic();startutc=datetime.now(timezone.utc).isoformat()
try:
 import numpy as np,mujoco
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime as rt
 from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant
 from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import RigidTableReferenceEnvelopeV1
 from traction_mpc_stage5.cr12_plant import Stage5CR12SpringDamperPlant,solve_cr12_stage5_ik,build_stage5_cr12_model_xml
 from traction_mpc_stage5.cr12_robot import CR12TorqueRobot
 from traction_mpc_stage3.human import mass_matrix,soft_limit_torque
 from traction_mpc_stage3.coupled import SLEEVE_HALF_LENGTH_M,SLEEVE_OUTER_RADIUS_M,BED_HEIGHT_M,SHANK_RADIUS_M
 from traction_mpc_stage4.estimator_v2 import nominal_base_parameters
 from traction_mpc_stage5.architecture_recovery_v2.effective_model import OnlineEffectiveDynamicsIdentifier
 modules={k:str(v.__file__) for k,v in sys.modules.items() if k.startswith('traction_mpc') and getattr(v,'__file__',None)}
 assert all(p.startswith(str(R)) for p in modules.values())
 prov=json.loads((W/'SOURCE_PROVENANCE.json').read_text());assert all(sha(R/p)==r['sha256'] for p,r in prov['source_files'].items())
 c=json.loads((W/'CONTRACT_R2.json').read_text());assert c['status']=='FROZEN_BEFORE_DYNAMIC'
 assert not (W/'runs_R2').exists()
 scoring=json.loads((S/'docs/high_rom_v1/PHASE_B_MATRIX.json').read_text())['scoring'];floor=float(scoring['clearance_m_min'])
 startq=np.radians([5.,10.]);goal=np.radians([120.,120.]);qs=startq+(goal-startq)*np.linspace(0,1,1201)[:,None]
 def geometry_screen(rho):
  case=json.loads(json.dumps(c['conditions'][0]['case']));case['physical']['cuff_fraction_of_shank']=rho
  h,g,spec,probe=hidden_plant(case)
  effective=replace(rt.nominal_control_geometry(),origin_world_m=g.world_from_human.translation.copy(),hip_plane_m=np.zeros(2),thigh_length_m=h.thigh_length_m,knee_to_cuff_in_cuff_m=np.array([h.sleeve_center_m,0.]))
  envelope=RigidTableReferenceEnvelopeV1(effective)
  # Regression for wrapper field repair: effective geometry must map exactly
  # to original fixture cuff centers, not silently use the nominal lever.
  for qcheck in [startq,goal,np.radians([9.,27.])]:
   assert np.allclose(envelope.cuff_centers(qcheck)[0],g.world_from_cuff(qcheck,h).translation,atol=1e-12)
  margins=envelope.margins(qs);initial=envelope.margins(startq)
  lo=h.sleeve_center_m-SLEEVE_HALF_LENGTH_M;hi=h.sleeve_center_m+SLEEVE_HALF_LENGTH_M
  barhalf=g.cuff_bar_length_m/2
  install=bool(rho>=.5 and lo>=0 and hi<=h.shank_length_m and h.sleeve_center_m-barhalf>=0 and h.sleeve_center_m+barhalf<=h.shank_length_m)
  mins={k:float(np.min(v)) for k,v in margins.items()};passed=bool(install and all(v>=floor for v in mins.values()))
  # Original commissioning waypoints are commands projected by the existing
  # DEV-D feedback mechanism, not a promise to physically realize unsafe waypoints.
  raw_probe_min={k:float(np.min(v)) for k,v in envelope.margins(probe).items()}
  return {'rho':rho,'shank_length_m':h.shank_length_m,'knee_to_cuff_m':h.sleeve_center_m,'sleeve_half_length_m':SLEEVE_HALF_LENGTH_M,'sleeve_interval_m':[lo,hi],'center_in_distal_half':rho>=.5,'full_sleeve_in_distal_half':lo>=h.shank_length_m/2,'full_sleeve_distal_half_proximal_margin_m':lo-h.shank_length_m/2,'sleeve_distal_end_margin_m':h.shank_length_m-hi,'installation_valid':install,'initial_margins_m':{k:float(v[0]) for k,v in initial.items()},'synchronous_120_path_minima_m':mins,'original_clearance_floor_m':floor,'geometric_screen_pass':passed,'raw_prescribed_probe_minima_m':raw_probe_min,'probe_interpretation':'Raw prescribed waypoints require unchanged DEV-D feedback projection. Negative literal-waypoint geometry is not a setup exclusion if validated commissioning controller projects it; actual commissioning remains untested.','adapter_length_m':float(np.linalg.norm(g.end_effector_from_cuff.translation)),'adapter_connector_length_m':max(0,float(np.linalg.norm(g.end_effector_from_cuff.translation))-.058),'cuff_bar_half_length_m':barhalf,'sleeve_collision_disabled':True,'evidence':'Original analytic rigid-table envelope with evaluation-only truth geometry; not fed to estimator/controller and not a dynamic certificate'}
 trials={str(rho):geometry_screen(rho) for rho in [.60,.66,.72]}
 assert all(x['geometric_screen_pass'] for x in trials.values())
 save('CUFF_LOCATION_GEOMETRY_AUDIT_R2.json',{'status':'FROZEN_FORMAL_POSITIONS_STATIC_PRECHECK_PASS','final':[.60,.66,.72],'candidate_trials':list(trials.values()),'old_boundary_evidence_sha256':sha(W/'CUFF_LOCATION_GEOMETRY_AUDIT.json'),'boundary_only':[.77,.85],'clearance_floor_unchanged':floor,'no_dynamic_results_seen':True,'installation_tolerances':'Synthetic nominal dimensions only; .60 sleeve distal-half margin near boundary. No tolerance/safety certification.'})
 print('CUFF_R2_FROZEN',[.60,.66,.72],flush=True)
 ident=OnlineEffectiveDynamicsIdentifier();rows=[];ikcache={};nominal_objects=None
 for cond in c['conditions']:
  h,g,spec,probe=hidden_plant(cond['case']);rho=h.cuff_fraction_of_shank
  plant=Stage5CR12SpringDamperPlant(human=h,geometry=g);model=plant.model
  row={'id':cond['id'],'case_sha256':cond['case_sha256'],'truth':dict(cond['case']['physical']),'derived':{n:float(getattr(h,n)) for n in ['thigh_length_m','shank_length_m','thigh_mass_kg','shank_mass_kg','thigh_com_m','shank_com_m','thigh_inertia_kg_m2','shank_inertia_kg_m2','sleeve_center_m']},'compiled_physical_objects':{},'valid_MuJoCo_model':True,'soft_limit_law_sha256':sha(R/'stages/stage3_full3d/src/traction_mpc_stage3/human.py')}
  for name in ['hip','shank']:
   b=model.body(name);row['compiled_physical_objects'][name]={'mass_kg':float(b.mass[0]),'COM_body_m':b.ipos.tolist(),'inertia_kg_m2':b.inertia.tolist(),'body_pos_m':b.pos.tolist()}
  for name in ['hip_joint','knee_joint']:
   j=model.joint(name);did=int(j.dofadr[0]);row['compiled_physical_objects'][name]={'stiffness_Nm_rad':float(j.stiffness[0]),'damping_Nms_rad':float(model.dof_damping[did]),'range_rad':j.range.tolist(),'springref_rad':float(model.qpos_spring[int(j.qposadr[0])])}
  row['compiled_physical_objects']['sleeve_attach_site']={'pos_m':model.site('sleeve_attach_site').pos.tolist()}
  row['compiled_physical_objects']['sleeve_geom']={'pos_m':model.geom('sleeve_geom').pos.tolist(),'size_m':model.geom('sleeve_geom').size.tolist(),'contype':int(model.geom('sleeve_geom').contype[0])}
  assert np.isclose(row['compiled_physical_objects']['hip']['mass_kg'],h.thigh_mass_kg) and np.isclose(row['compiled_physical_objects']['shank']['mass_kg'],h.shank_mass_kg)
  assert np.allclose(row['compiled_physical_objects']['hip']['inertia_kg_m2'],[.51*h.thigh_inertia_kg_m2,h.thigh_inertia_kg_m2,.51*h.thigh_inertia_kg_m2])
  assert np.allclose(row['compiled_physical_objects']['shank']['inertia_kg_m2'],[.51*h.shank_inertia_kg_m2,h.shank_inertia_kg_m2,.51*h.shank_inertia_kg_m2])
  assert np.isclose(model.site('sleeve_attach_site').pos[0],h.sleeve_center_m)
  assert all(np.isclose(row['compiled_physical_objects'][n]['stiffness_Nm_rad'],h.passive_stiffness_nm_rad[i]) and np.isclose(row['compiled_physical_objects'][n]['damping_Nms_rad'],5.) for i,n in enumerate(['hip_joint','knee_joint']))
  row['mass_matrix_min_eigenvalue']=float(min(np.linalg.eigvalsh(mass_matrix(np.radians([5.,a]),h))[0] for a in np.linspace(0,125,126)))
  beta=nominal_base_parameters(h);row['true_beta_evaluation_only']=beta.tolist();row['identifier_bounds_contain_truth']=bool(np.all(beta>=ident.lower)&np.all(beta<=ident.upper));row['full_shank_prior_valid']=h.shank_length_m<=.46
  row['truth_geometry_fit_bounds_valid']=bool(.30<=h.thigh_length_m<=.56 and .14<=h.sleeve_center_m<=.48)
  row['limits']=rt._jsonable(asdict(spec));row['setup_frames']=rt._jsonable({'world_from_base':asdict(g.world_from_base),'world_from_human':asdict(g.world_from_human),'end_effector_from_cuff':asdict(g.end_effector_from_cuff)})
  robot=plant._ik_robot
  if rho not in ikcache:
   prev=None;samples=[];fail=None
   for progress in np.linspace(0,1,129):
    q=startq+(goal-startq)*progress
    try:qr=solve_cr12_stage5_ik(robot,g.base_from_end_effector_target(q,h),previous_q_rad=prev)
    except Exception as ex:fail={'progress':float(progress),'exception':str(ex)};break
    prev=qr;plant.data.qpos[plant.human_qpos_indices]=q;plant.data.qpos[plant.robot_qpos_indices]=qr;plant.data.qvel[:]=0;mujoco.mj_forward(model,plant.data)
    negative=[{'geoms':[mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_GEOM,int(ct.geom[0])),mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_GEOM,int(ct.geom[1]))],'distance_m':float(ct.dist)} for ct in plant.data.contact if ct.dist< -1e-9]
    distance=min(float(mujoco.mj_geomDistance(model,plant.data,int(plant.bed_geom_id),int(gid),2.,None)) for gid in plant.robot_collision_geom_ids)
    samples.append({'progress':float(progress),'q_human_rad':q.tolist(),'q_robot_rad':qr.tolist(),'robot_table_distance_m':distance,'penetrating_contacts':negative,'joint_limit_margin_rad':float(np.min(np.r_[qr-robot.joint_limits_rad[:,0],robot.joint_limits_rad[:,1]-qr]))})
   ikcache[rho]={'sample_count':len(samples),'failure':fail,'minimum_robot_table_m':min((x['robot_table_distance_m'] for x in samples),default=None),'initial_penetrating_contacts':samples[0]['penetrating_contacts'] if samples else None,'penetrating_sample_count':sum(bool(x['penetrating_contacts']) for x in samples),'minimum_joint_margin_rad':min((x['joint_limit_margin_rad'] for x in samples),default=None),'samples':samples,'source_condition':cond['id']}
  row['static_IK']=ikcache[rho];row['geometric_audit']=geometry_screen(rho)
  row['IK_reuse_justification']='Exact identical physical geometry/ROM/setup for mass and stiffness factors; inertial/passive changes do not alter static geometric IK or contacts. Reuse stored configuration path, while each condition separately compiles the full physical model.'
  valid=bool(row['valid_MuJoCo_model'] and row['mass_matrix_min_eigenvalue']>0 and row['identifier_bounds_contain_truth'] and row['full_shank_prior_valid'] and row['truth_geometry_fit_bounds_valid'] and row['geometric_audit']['geometric_screen_pass'] and row['static_IK']['sample_count']==129 and row['static_IK']['failure'] is None and row['static_IK']['initial_penetrating_contacts']==[])
  row['setup_status']='NECESSARY_STATIC_PRECHECK_PASS' if valid else 'PHYSICAL_SETUP_OUT_OF_SCOPE'
  row['dynamic_safety_status']='NOT_PROVEN_NOT_EXECUTED';row['propagation_verified']=True
  rows.append(row);save('PARAMETER_PROPAGATION_AUDIT_R2.json',{'status':'STATIC_AUDIT_IN_PROGRESS','rows':rows,'time_integration_steps':0});print('STATIC_CONDITION',cond['id'],row['setup_status'],flush=True)
  del plant,model,robot;gc.collect()
 save('PARAMETER_PROPAGATION_AUDIT_R2.json',{'status':'PHYSICAL_ARRAY_PROPAGATION_VERIFIED','rows':rows,'identifier_bounds':{'lower':ident.lower.tolist(),'upper':ident.upper.tolist(),'unchanged':True},'time_integration_steps':0,'synthetic_mass_inertia_scaling':True,'no_anatomical_population_claim':True})
 save('FEASIBILITY_AUDIT_R2.json',{'status':'NECESSARY_STATIC_PRECHECKS_ONLY','rows':[{'id':r['id'],'setup_status':r['setup_status'],'static_IK':{k:v for k,v in r['static_IK'].items() if k!='samples'},'geometry':r['geometric_audit'],'mass_matrix_min_eigenvalue':r['mass_matrix_min_eigenvalue'],'limits':r['limits'],'full_shank_prior_valid':r['full_shank_prior_valid'],'dynamic_safety_status':r['dynamic_safety_status']} for r in rows],'scoring':scoring,'primary_goal_unchanged_deg':[120,120],'task_complete_dynamics_executed':False,'path_scope':'129 sampled synchronous outbound IK plus original 1201-point rigid-table envelope. HOLD endpoint/reverse RETURN geometry only. Actual startup/commissioning/replanning/HOLD/RETURN and between-sample motion remain untested.'})
 save('ENVIRONMENT_R2.json',{'python':sys.executable,'version':sys.version,'packages':{k:importlib.metadata.version(k) for k in ['numpy','scipy','mujoco']},'project_imports':modules,'all_imports_from_snapshot':True,'threads':{n:os.environ[n] for n in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']},'CUDA_VISIBLE_DEVICES':os.environ['CUDA_VISIBLE_DEVICES'],'nice':os.getpriority(os.PRIO_PROCESS,0),'no_bytecode_writes':True,'static_start_utc':startutc,'static_finish_utc':datetime.now(timezone.utc).isoformat(),'static_wall_s':time.monotonic()-start,'static_self_peak_RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'time_integration_steps':0})
 print('AUDIT_DONE',len(rows),round(time.monotonic()-start,2),resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,flush=True)
except Exception:
 (W/'STATIC_AUDIT_EXCEPTION_R2.txt').write_text(traceback.format_exc());print(traceback.format_exc(),flush=True);sys.exit(1)
