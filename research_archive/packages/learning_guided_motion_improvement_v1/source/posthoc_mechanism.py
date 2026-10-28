"""Locked-result allocator reconstruction; never a forward model input."""
from pathlib import Path
import sys,os,json,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
P=Path(__file__).resolve().parents[1];R=P/'runtime';sys.path[:0]=[str(R/'code'),str(R/'control')]
import study_common as sc
import mujoco

def forbidden(*a,**k):raise RuntimeError('POSTHOC_NO_NATIVE_STEPPING')
mujoco.mj_step=mujoco.mj_step1=mujoco.mj_step2=forbidden
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage4.cuff_allocator import CuffAwareSagittalAllocator
from traction_mpc_stage5.high_rom_v1 import deployable_prior

def load_trace(ident):
 s=json.loads((R/'source/results'/ident/'summary.json').read_text());b=s['commissioning']['handoff_belief']
 with np.load(R/'source/results'/ident/'trace.npz') as z:
  m=z['stage']=='TASK';d={k:z[k][m] for k in ['time_s','estimated_human_state_rad_rad_s','reference_q_rad','reference_dq_rad_s','applied_generalized_action_nm','physical_cuff_force_world_n','physical_cuff_moment_world_nm']}
 return s,b,d

def main():
 result=json.loads((P/'THREE_ARM_RESULTS.json').read_text());selected={a:r for a,r in result['locked'].items() if r is not None};ss,b,H=load_trace('OPTIMIZATION_H150');geometry=PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in b['effective_geometry'].items()});model=sc.rt.StateResidualHumanModel(geometry,np.asarray(b['beta']),deployable_prior(),residual_weights_nm=np.asarray(b['state_residual_weights_nm']));al=CuffAwareSagittalAllocator();t=H['time_s'];dt=np.diff(t);ph=np.full(len(t),'OUTBOUND',dtype='<U10')
 for tr in ss['task']['phase_transitions']:
  if tr['to'] in ['OUTBOUND','HOLD','RETURN']:ph[t>=tr['time_s']-1e-9]=tr['to']
 def integ(v,mask=None):return float(v[:-1]@dt) if mask is None else float(v[:-1][mask]@dt[mask])
 def alloc(q,u):return np.asarray([al._prepare_factors(qq,model).action_to_wrench_world@uu for qq,uu in zip(q,u)])
 hq=H['estimated_human_state_rad_rad_s'][:,:2];hu=H['applied_generalized_action_nm'];base=alloc(hq,hu);Fb=np.linalg.norm(base[:,:3],axis=1);Mb=np.linalg.norm(base[:,3:],axis=1);Factual=np.linalg.norm(H['physical_cuff_force_world_n'],axis=1);Mactual=np.linalg.norm(H['physical_cuff_moment_world_nm'],axis=1);rows={};saved={}
 for arm,r in selected.items():
  ident=r['id'];su,bb,z=load_trace(ident);assert b==bb,'COMMISSIONED_MODEL_IDENTITY';assert np.max(abs(z['time_s']-t))<1e-8,'EQUAL_TASK_GRID'
  q=z['estimated_human_state_rad_rad_s'][:,:2];u=z['applied_generalized_action_nm'];EE=alloc(q,u);EB=alloc(q,hu);BE=alloc(hq,u);F={k:np.linalg.norm(w[:,:3],axis=1) for k,w in [('BB',base),('EE',EE),('EB',EB),('BE',BE)]};geom=.5*((F['EB']-F['BB'])+(F['EE']-F['BE']));action=.5*((F['BE']-F['BB'])+(F['EE']-F['EB']));assert np.max(abs(geom+action-F['EE']+F['BB']))<1e-9,'SHAPLEY_ALGEBRA_CLOSURE'
  fa=np.linalg.norm(z['physical_cuff_force_world_n'],axis=1);ma=np.linalg.norm(z['physical_cuff_moment_world_nm'],axis=1)
  row={'id':ident,'x':r['x'],'actual_delta_JF':integ(fa-Factual),'actual_delta_JM':integ(ma-Mactual),'posthoc_allocator_delta_JF':integ(F['EE']-F['BB']),'posthoc_allocator_delta_JM':integ(np.linalg.norm(EE[:,3:],axis=1)-Mb),'geometry_input_shapley_N_s':integ(geom),'generalized_action_input_shapley_N_s':integ(action),'phase_actual_delta_JF':{p:integ(fa-Factual,ph[:-1]==p) for p in ['OUTBOUND','HOLD','RETURN']},'estimated_posture_mean_delta_deg':np.degrees(np.mean(q-hq,axis=0)),'reference_max_abs_delta_deg':np.degrees(np.max(abs(z['reference_q_rad']-H['reference_q_rad']),axis=0)),'requested_generalized_action_mean_delta_Nm':np.mean(u-hu,axis=0),'force_lower_fraction_of_intervals':float(np.mean(fa[:-1]<Factual[:-1])),'force_pointwise_delta_range_N':[float(np.min(fa-Factual)),float(np.max(fa-Factual))],'scope':'post-run estimated q and logged generalized action allocator arithmetic; no isolated physical causal mediation; command-to-contact/feedback residual remains','actual_six_axis_robot_torque':'independently joined to native receipts in audit/INDEPENDENT_RAW_AUDIT.json'}
  rows[arm]=row;saved[arm]=z
 (P/'NEW_CANDIDATE_MECHANISM.json').write_text(json.dumps(sc.clean({'rows':rows,'baseline':'OPTIMIZATION_H150','new_native_steps':0,'inputs_are_post_execution':True,'never_consumed_by_optimizers':True,'source_sha256':sc.sha(Path(__file__))}),indent=2,ensure_ascii=False)+'\n')
 with (P/'PHYSICS_MECHANISM_AUDIT.md').open('a') as f:
  f.write('\n## 锁定新candidate的事后机制核算\n\n只在候选/模型冻结和物理队列结束后运行，不回流任何新proposal。estimated posture与generalized action输入交换只是allocator代数归因，不是合法可执行物理反事实，也不将它解释成已识别因果中介比例。真实robot六轴torque另由native/receipt独立闭合。\n\n|臂|实际ΔJF|事后allocator ΔJF|geometry输入贡献|请求action输入贡献|实际ΔJM|\n|---|---:|---:|---:|---:|---:|\n')
  for arm,row in rows.items():f.write(f"|{arm}|{row['actual_delta_JF']:.9f}|{row['posthoc_allocator_delta_JF']:.9f}|{row['geometry_input_shapley_N_s']:.9f}|{row['generalized_action_input_shapley_N_s']:.9f}|{row['actual_delta_JM']:.9f}|\n")
  f.write('\n完整posture/reference/action差、分phase受力、瞬时正负差与积分见NEW_CANDIDATE_MECHANISM.json。降力可能伴随moment增量，净完整积分下降不等于每一瞬间都更低。源自已执行状态的好闭合也不能替代事前预测。\n')
 import matplotlib.pyplot as plt
 fig,axes=plt.subplots(4,1,figsize=(12,11),sharex=True,layout='constrained');task=t-t[0];axes[0].plot(task,Factual,label='H150',c='.3');axes[1].plot(task,np.r_[0,np.cumsum(Factual[:-1]*dt)],c='.3',label='H150');axes[2].plot(task,np.degrees(hq[:,0]),c='.3',label='H150 hip');axes[3].plot(task,np.degrees(hq[:,1]),c='.3',label='H150 knee')
 colors={'A':'#2166ac','B':'#b35806','C':'#008837'}
 for arm,z in saved.items():
  force=np.linalg.norm(z['physical_cuff_force_world_n'],axis=1);axes[0].plot(task,force,label=arm,c=colors[arm],alpha=.8);axes[1].plot(task,np.r_[0,np.cumsum(force[:-1]*dt)],label=arm,c=colors[arm]);axes[2].plot(task,np.degrees(z['estimated_human_state_rad_rad_s'][:,0]),label=arm,c=colors[arm]);axes[3].plot(task,np.degrees(z['estimated_human_state_rad_rad_s'][:,1]),label=arm,c=colors[arm])
 for ax,y in zip(axes,['Measured cuff force [N]','Full JF [N s]','Estimated hip [deg]','Estimated knee [deg]']):ax.set_ylabel(y);ax.grid(alpha=.2);ax.legend(ncol=4)
 axes[-1].set_xlabel('Task elapsed [s]');fig.suptitle('Locked complete qualified trajectories | same original task clock');(P/'figures').mkdir(exist_ok=True);fig.savefig(P/'figures/LOCKED_MOTION_AND_FORCE.png',dpi=170);fig.savefig(P/'figures/LOCKED_MOTION_AND_FORCE.svg');plt.close(fig)
 print(json.dumps({a:{k:r[k] for k in ['actual_delta_JF','posthoc_allocator_delta_JF','actual_delta_JM']} for a,r in rows.items()}),flush=True)
if __name__=='__main__':main()
