"""Kinematic Jacobian replay only: zero native integration, no new physics arm.

Load archived robot q into a disposable model, compute kinematics and invert
J.T for already-recorded torque components. Require total-wrench closure.
"""
from pathlib import Path
import os,sys,json
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_waypoint_smoothing_overnight_v1');sys.path.insert(0,str(P/'code'));sys.path.insert(0,str(P/'control'))
import study_common
import mujoco,numpy as np
from traction_mpc_stage5.cr12_plant import Stage5CR12SpringDamperPlant
from analyze_mechanism import load as archive_load,put,integ,clean
from postprocess_targeted import load as new_load
def forbid(*args,**kwargs):raise AssertionError('No native integration allowed in kinematic replay')
mujoco.mj_step=forbid;mujoco.mj_step1=forbid;mujoco.mj_step2=forbid
plant=Stage5CR12SpringDamperPlant();rows=[];cache={}
def reconstruct(z):
 n=len(z['tf'])-1;ws={k:np.zeros((n+1,6)) for k in ['position','velocity','allocator']};maxcondition=0
 for i,q in enumerate(z['cr12_q_rad'][:-1]):
  plant.data.qpos[plant.robot_qpos_indices]=q;mujoco.mj_kinematics(plant.model,plant.data);mujoco.mj_comPos(plant.model,plant.data);J=plant.robot_attachment_jacobian();maxcondition=max(maxcondition,np.linalg.cond(J))
  for k in ws:ws[k][i]=np.linalg.solve(J.T,z['robot_torque_component_'+k+'_nm'][i])
 closure=np.max(abs(sum(ws.values())[:-1]-z['allocated_wrench_world'][:-1]));assert closure<1e-7,('WRENCH_CLOSURE',closure);assert plant.data.time==0
 return ws,closure,maxcondition
B=archive_load('B0');cache['B']=reconstruct(B)
cases=[('18D',archive_load('18D'),[(4,6),(15,16),(0,19.03)])]
rs=[json.loads(l) for l in (P/'CANDIDATE_RESULTS.jsonl').read_text().splitlines()]
for r in rs:
 if r['status']=='COMPLETE' and 'local' in r and not r['candidate']['id'].endswith('zero'):cases.append((r['id'],new_load(r['id']),[tuple(r['candidate']['local_window_task_s']),(0,19.03)]))
for name,E,windows in cases:
 we,err,cond=reconstruct(E);wb=cache['B'][0];fb=B['allocated_wrench_world'][:,:3];fe=E['allocated_wrench_world'][:,:3];projection=(fb+fe)/(np.linalg.norm(fb,axis=1)+np.linalg.norm(fe,axis=1))[:,None]
 parts={k:np.sum(projection*(we[k][:,:3]-wb[k][:,:3]),axis=1) for k in we};error=np.max(abs(sum(parts.values())[:-1]-(np.linalg.norm(fe,axis=1)-np.linalg.norm(fb,axis=1))[:-1]));assert error<1e-7
 table={f'{lo}-{hi}':dict(total_command_delta_force_integral_N_s={k:integ(B['tf'],v,lo,hi) for k,v in parts.items()},total_command_delta=integ(B['tf'],np.linalg.norm(fe,axis=1)-np.linalg.norm(fb,axis=1),lo,hi),physical_contact_force_delta=integ(B['tf'],E['f']-B['f'],lo,hi)) for lo,hi in windows}
 rows.append(dict(id=name,windows=table,total_wrench_reconstruction_error=err,J_condition_max=cond))
 np.savez_compressed(P/'series'/(name+'_wrench_components.npz'),tf=B['tf'],**we)
put('derived/WRENCH_COMPONENT_RECONSTRUCTION.json',dict(rows=rows,B_reconstruction_error=cache['B'][1],B_J_condition=cache['B'][2],native_steps=0,kinematic_model_time=float(plant.data.time),scope='Disposable CR12 model kinematics / comPos and archived robot q only; all stepping functions forbidden. J.T inversion reconstructs recorded position, velocity and allocator wrench components; sum required to match archived TOTAL command wrench. Command-force norm differences split exactly by average-unit-vector projection. Contact-force change is not necessarily identical. These are algebraic component accounting, not component-disable causal interventions.'))
print(json.dumps(clean(rows),indent=2))
