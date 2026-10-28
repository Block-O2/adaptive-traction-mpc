"""High-ROM path IK and sampled CR12 clearance screen; no time integration."""
from __future__ import annotations
import json, math, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
for relative in ('stages/stage5_personalized_motion_learning/src','stages/stage4_adaptive_control/src','stages/stage3_full3d/src'):
    sys.path.insert(0,str(ROOT/relative))
import mujoco, numpy as np
from traction_mpc_stage5.cr12_plant import Stage5CR12SpringDamperPlant,solve_cr12_stage5_ik
from traction_mpc_stage5.cr12_robot import CR12TorqueRobot
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.high_rom_v1 import deployable_prior

def main():
    human=deployable_prior();plant=Stage5CR12SpringDamperPlant(human=human);robot=CR12TorqueRobot()
    bed=int(plant.bed_geom_id);out={}
    for degree in (100,110,120):
        for label,lead in (('synchronous',0.0),('hip_leads',0.45)):
            start=np.radians([5.,10.]);delta=np.radians([degree,degree])-start
            prior=None;sampled=[];failure=None
            for progress in np.linspace(0,1,129):
                q=start+delta*np.array([(1+lead)*progress-lead*progress**2,(1-lead)*progress+lead*progress**2])
                target=STAGE5_GEOMETRY.base_from_end_effector_target(q,human)
                try:qrobot=solve_cr12_stage5_ik(robot,target,previous_q_rad=prior)
                except Exception as exc:
                    failure={'progress':float(progress),'exception':str(exc)};break
                prior=qrobot;robot.set_configuration(qrobot)
                plant.data.qpos[plant.human_qpos_indices]=q;plant.data.qpos[plant.robot_qpos_indices]=qrobot
                plant.data.qvel[:]=0;mujoco.mj_forward(plant.model,plant.data)
                distance=min(float(mujoco.mj_geomDistance(plant.model,plant.data,bed,int(g),2.,None)) for g in plant.robot_collision_geom_ids)
                margin=float(np.min(np.r_[qrobot-robot.joint_limits_rad[:,0],robot.joint_limits_rad[:,1]-qrobot]))
                sigma=float(np.linalg.svd(robot.attachment_jacobian(),compute_uv=False)[-1])
                sampled.append([distance,margin,sigma,*qrobot])
            arr=np.asarray(sampled);out[f'{degree}_{label}']={'samples':len(sampled),'failure':failure,
                'minimum_robot_table_mm_sampled':None if not len(arr) else float(arr[:,0].min()*1000),
                'minimum_joint_margin_deg_sampled':None if not len(arr) else float(np.degrees(arr[:,1].min())),
                'minimum_jacobian_sigma_sampled':None if not len(arr) else float(arr[:,2].min()),
                'largest_adjacent_joint_step_deg':None if len(arr)<2 else float(np.degrees(np.abs(np.diff(arr[:,3:],axis=0)).max())),
                'evidence_limit':'129 sampled IK configurations; between-sample robot swept geometry and collision unproven'}
    path=ROOT/'stages/stage5_personalized_motion_learning/docs/high_rom_v1/phase_b_robot_path_screen.json'
    path.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out))
if __name__=='__main__':main()
