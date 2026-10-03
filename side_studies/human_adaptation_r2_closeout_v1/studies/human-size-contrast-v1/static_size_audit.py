"""Static model construction and sampled IK only; never integrates time."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS']: os.environ[k]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['PYTHONDONTWRITEBYTECODE']='1'
from pathlib import Path
import sys,json,hashlib,traceback,time,resource,importlib.metadata
W=Path('<SIDE_STUDIES_ROOT>/human-size-contrast-v1');R=W/'snapshot';S=R/'stages/stage5_personalized_motion_learning'
sys.dont_write_bytecode=True
for stage in ['stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning']:sys.path.insert(0,str(R/'stages'/stage/'src'))
def save(n,x): (W/n).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
try:
 import numpy as np,mujoco
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime as rt
 from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant
 from traction_mpc_stage5.cr12_plant import Stage5CR12SpringDamperPlant,solve_cr12_stage5_ik
 from traction_mpc_stage5.cr12_robot import CR12TorqueRobot
 from traction_mpc_stage3.human import mass_matrix
 from traction_mpc_stage3.coupled import BED_HEIGHT_M,SHANK_RADIUS_M
 from traction_mpc_stage4.estimator_v2 import nominal_base_parameters
 from traction_mpc_stage5.high_rom_v1 import deployable_prior
 from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK
 from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import SessionClearanceContract
 modules={k:str(v.__file__) for k,v in sys.modules.items() if k.startswith('traction_mpc') and getattr(v,'__file__',None)}
 assert all(p.startswith(str(R)) for p in modules.values()),modules
 env={'python':sys.executable,'version':sys.version,'packages':{n:importlib.metadata.version(n) for n in ['numpy','scipy','mujoco']},'threads':{k:os.environ[k] for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']},'CUDA_VISIBLE_DEVICES':os.environ['CUDA_VISIBLE_DEVICES'],'actual_import_paths':modules,'all_project_imports_isolated':True,'time_integration_steps':0}
 save('ENVIRONMENT.json',env)
 print('IMPORT_OK',len(modules),flush=True)
 contract=json.loads((W/'CONTRACT.json').read_text());rows=[]
 prior=deployable_prior();beta_prior=nominal_base_parameters(prior)
 for entry in contract['cases']:
  case=entry['case'];human,geom,spec,probe=hidden_plant(case)
  row={'height_m':human.height_m,'truth_fields':dict(case['physical']),'derived':{n:float(getattr(human,n)) for n in ['thigh_length_m','shank_length_m','thigh_mass_kg','shank_mass_kg','thigh_com_m','shank_com_m','thigh_inertia_kg_m2','shank_inertia_kg_m2','sleeve_center_m']},'geometry_bounds':{'lower':[-.35,-.05,.30,.14],'upper':[.35,.30,.56,.48]},'geometry_truth_within_bounds':bool(.30<=human.thigh_length_m<=.56 and .14<=human.sleeve_center_m<=.48),'dynamic_truth_beta_evaluation_only':nominal_base_parameters(human).tolist(),'dynamic_truth_over_nominal_evaluation_only':(nominal_base_parameters(human)/beta_prior).tolist(),'screens':{}}
  plant=Stage5CR12SpringDamperPlant(human=human,geometry=geom);robot=CR12TorqueRobot()
  model=plant.model
  row['mujoco_objects']={}
  for i in range(model.nbody):
   name=mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_BODY,i) or str(i)
   if any(x in name.lower() for x in ['thigh','shank','human']):row['mujoco_objects'][name]={'mass_kg':float(model.body_mass[i]),'com_body_m':model.body_ipos[i].tolist(),'inertia_kg_m2':model.body_inertia[i].tolist(),'body_pos_m':model.body_pos[i].tolist()}
  row['mujoco_sites']={mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_SITE,i) or str(i):model.site_pos[i].tolist() for i in range(model.nsite) if any(x in (mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_SITE,i) or '').lower() for x in ['human','sleeve','cuff'])}
  row['mass_matrix_min_eigenvalue']=float(min(np.linalg.eigvalsh(mass_matrix(np.radians([5,k]),human))[0] for k in np.linspace(0,125,126)))
  row['inertia_positive']=all(v>0 for n,v in row['derived'].items() if 'inertia' in n)
  candidates=[('primary120',np.radians([120.,120.])),('existing_low_moderate',np.asarray(PROVISIONAL_LOW_MODERATE_GOAL_TASK.outbound_goal_target_rad))]
  for label,goal in candidates:
   prev=None;samples=[];failure=None
   for progress in np.linspace(0,1,129):
    q=np.radians([5.,10.])+(goal-np.radians([5.,10.]))*progress
    target=geom.base_from_end_effector_target(q,human)
    try: qr=solve_cr12_stage5_ik(robot,target,previous_q_rad=prev)
    except Exception as ex:failure={'progress':float(progress),'reason':str(ex)};break
    prev=qr;robot.set_configuration(qr)
    plant.data.qpos[plant.human_qpos_indices]=q;plant.data.qpos[plant.robot_qpos_indices]=qr;plant.data.qvel[:]=0;mujoco.mj_forward(model,plant.data)
    bed=int(plant.bed_geom_id)
    distance=min(float(mujoco.mj_geomDistance(model,plant.data,bed,int(g),2.,None)) for g in plant.robot_collision_geom_ids)
    contacts=[{'geoms':[mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_GEOM,int(c.geom[0])),mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_GEOM,int(c.geom[1]))],'distance_m':float(c.dist)} for c in plant.data.contact if c.dist< -1e-9]
    knee=geom.world_from_human.translation+human.thigh_length_m*np.array([np.cos(q[0]),0,np.sin(q[0])]);ankle=knee+human.shank_length_m*np.array([np.cos(q[0]-q[1]),0,np.sin(q[0]-q[1])])
    shank_gap=min(knee[2],ankle[2])-SHANK_RADIUS_M-BED_HEIGHT_M
    samples.append({'progress':float(progress),'robot_bed_m':distance,'shank_bed_m':float(shank_gap),'penetrating_contacts':contacts,'joint_margin_rad':float(np.min(np.r_[qr-robot.joint_limits_rad[:,0],robot.joint_limits_rad[:,1]-qr]))})
   row['screens'][label]={'goal_deg':np.degrees(goal).tolist(),'sample_count':len(samples),'IK_failure':failure,'minimum_robot_table_m':min((x['robot_bed_m'] for x in samples),default=None),'minimum_true_shank_table_m':min((x['shank_bed_m'] for x in samples),default=None),'initial_contacts':samples[0]['penetrating_contacts'] if samples else None,'negative_contact_sample_count':sum(bool(x['penetrating_contacts']) for x in samples),'samples':samples,'interpretation':'Necessary sampled IK/contact/geometry conditions only; no dynamic safety or intersample proof'}
  rows.append(row);print('STATIC_DONE',human.height_m,flush=True)
 save('HUMAN_PARAMETER_AND_FEASIBILITY_AUDIT.json',{'time_integration_steps':0,'rows':rows,'structural_shank_prior':str(SessionClearanceContract.__dataclass_fields__) if hasattr(SessionClearanceContract,'__dataclass_fields__') else 'See frozen source','lower_ROM_is_immutable_existing_task':list(PROVISIONAL_LOW_MODERATE_GOAL_TASK.outbound_goal_target_rad),'resource_self_peak_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
except Exception:
 save('STATIC_AUDIT_EXCEPTION.json',{'traceback':traceback.format_exc(),'time_integration_steps':0});print(traceback.format_exc());sys.exit(1)
