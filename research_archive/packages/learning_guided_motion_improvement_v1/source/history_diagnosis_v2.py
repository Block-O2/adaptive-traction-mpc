from pathlib import Path
import sys,os,json,hashlib,time,shutil,datetime
import numpy as np
P=Path('/tmp/lgmi_active_package').read_text().strip();P=Path(P);R=P/'runtime'
sys.path[:0]=[str(R/'control'),str(R/'code')]
import study_common as sc
import mujoco
calls=[]
def prohibited(*a,**k):calls.append(1);raise RuntimeError('ZERO_NEW_PHYSICS_DIAGNOSTIC')
mujoco.mj_step=mujoco.mj_step1=mujoco.mj_step2=prohibited
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry,BaseParameterHumanModel
from traction_mpc_stage4.cuff_allocator import CuffAwareSagittalAllocator
G=P.parent/'rl_b_matched_recovery_stability_v1/github/research/side_studies/ihear_overnight_control_learning_transition_v1'
def put(n,x):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(sc.clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def load(ident):
 s=json.loads((G/'source/results'/ident/'summary.json').read_text())
 with np.load(G/'source/results'/ident/'trace.npz') as z:
  m=z['stage']=='TASK';d={k:z[k][m] for k in ['time_s','estimated_human_state_rad_rad_s','reference_q_rad','reference_dq_rad_s','reference_ddq_rad_s2','applied_generalized_action_nm','physical_cuff_force_world_n','physical_cuff_moment_world_nm']}
 b=s['commissioning']['handoff_belief'];geo=PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in b['effective_geometry'].items()});model=BaseParameterHumanModel(geo,np.asarray(b['beta']));return s,d,model
allocator=CuffAwareSagittalAllocator()
def calc(q,v,a,model):
 return np.asarray([allocator.allocate(model.inverse_dynamics(qq,vv,aa),qq,model)['wrench_world'] for qq,vv,aa in zip(q,v,a)])
s,b,model=load('D01R_B');se,e,modele=load('D01R_H150')
t=b['time_s'];phase=np.full(len(t),'OUTBOUND',dtype='<U10')
for tr in s['task']['phase_transitions']:
 if tr['to'] in ['OUTBOUND','HOLD','RETURN']:phase[t>=tr['time_s']-1e-8]=tr['to']
dt=np.diff(t)
def integrals(w):
 f=np.linalg.norm(w[:,:3],axis=1);m=np.linalg.norm(w[:,3:],axis=1)
 return {'JF':float(f[:-1]@dt),'JM':float(m[:-1]@dt),'phase_JF':{ph:float(f[:-1][phase[:-1]==ph]@dt[phase[:-1]==ph]) for ph in ['OUTBOUND','HOLD','RETURN']}}
post={}
for name,z,md in [('B',b,model),('H150',e,modele)]:
 w=np.asarray([allocator.allocate(u,q,md)['wrench_world'] for q,u in zip(z['estimated_human_state_rad_rad_s'][:,:2],z['applied_generalized_action_nm'])]);actual=np.c_[z['physical_cuff_force_world_n'],z['physical_cuff_moment_world_nm']]
 post[name]={'allocator_posthoc':integrals(w),'actual':integrals(actual)}
x=np.asarray(json.loads((R/'FROZEN_18D.json').read_text())['free_parameters']);q=b['reference_q_rad'].copy();start=q[0].copy();goal=np.max(q,axis=0)
for ph in ['OUTBOUND','RETURN']:
 idx=phase==ph;origin,span=(start,goal-start) if ph=='OUTBOUND' else (goal,start-goal)
 prog=(q[idx]-origin)/span;m=np.clip(np.mean(prog,axis=1),0,1);env=np.sin(np.pi*m)**2;u=2*m-1;j=0 if ph=='OUTBOUND' else 5;k=10 if j==0 else 14
 c=env*(x[j]+x[k]*u+x[k+1]*u*u);d=env*(x[j+1]+x[j+2]*u+x[k+2]*u*u)
 q[idx]+=span*np.column_stack([c+d,c-d])
delta=q-b['reference_q_rad'];dv=np.gradient(delta,t,axis=0,edge_order=2);da=np.gradient(dv,t,axis=0,edge_order=2);v=b['reference_dq_rad_s']+dv;a=b['reference_ddq_rad_s2']+da
predB=integrals(calc(b['reference_q_rad'],b['reference_dq_rad_s'],b['reference_ddq_rad_s2'],model));predE=integrals(calc(q,v,a,model))
actual_delta={k:post['H150']['actual'][k]-post['B']['actual'][k] for k in ['JF','JM']};pred_delta={k:predE[k]-predB[k] for k in ['JF','JM']}
np.savez_compressed(P/'history/CAUSAL_H150_REFERENCE_TEMPLATE.npz',time_s=e['time_s']-e['time_s'][0],phase=phase,q=e['reference_q_rad'],dq=e['reference_dq_rad_s'],ddq=e['reference_ddq_rad_s2'])
put('history/CAUSAL_COMMISSIONED_BELIEF.json',{'geometry':se['commissioning']['handoff_belief']['effective_geometry'],'beta':se['commissioning']['handoff_belief']['beta'],'initial_estimated_state':e['estimated_human_state_rad_rad_s'][0],'source':'completed historical D01R_H150 commissioned/causal estimate; no physical truth'})
result={'status':'LIMITED_PROXY_DIAGNOSIS_COMPLETE','new_physical_attempts':0,'new_native_steps':0,'trajectory_groups':1,'independent_patient_groups':1,'historical_rows':2,'historical_source':str(G),'historical_compute_cost':'not recomputed; original prefix/B/H150 shared public prior','posthoc':post,'forward_reconstruction':{'inputs':['completed B causal reference','commissioned estimated beta and geometry','proposed frozen18D/H150 intent'],'not_used':['H150 actual future q/dq','future requested torque','future receipts','true Human parameters'],'B':predB,'H150_approx':predE,'actual_delta':actual_delta,'predicted_delta':pred_delta,'delta_error':{k:pred_delta[k]-actual_delta[k] for k in actual_delta},'sign_correct':{k:bool(pred_delta[k]*actual_delta[k]>0) for k in actual_delta},'limitations':['template omits segment schedule/terminal timing/posture repairs','nominal allocation omits robot/contact/feedback/discrete admission','one matched group is not independent validation']},'PHYSICS_PROXY_USABLE':'CONDITIONAL_NOMINAL_LOAD_RANKING_ONLY','RESIDUAL_LEARNING_NEEDED':'HYPOTHESIS_TO_TEST','FORWARD_PREDICTION_BLOCKED':'FULL_CLOSED_LOOP_MOTION_TASK_CONTACT_NOT_CLOSED','actual_tracking_prediction':'UNKNOWN','actual_motion_margin_prediction':'UNKNOWN','task_feasibility_prediction':'UNKNOWN','physics_calls_intercepted':len(calls)}
put('PROXY_MODEL_RESULTS.json',result)
(P/'PHYSICS_MECHANISM_AUDIT.md').write_text('# 物理机制与信息边界审计\n\n零新增物理。见PROXY_MODEL_RESULTS.json的独立allocator重算与实际完整积分。事后使用estimated q/requested torque；事前重建只用已完成B的causal reference、commissioned估计与提议参数。没有使用目标H150未来真值/torque/receipt。历史36.53/37.92来自另一开发条件，本轮不移用作预测准确率。\n\n名义Human inverse_dynamics与allocator存在；legacy Predictor采用人为指数tracking衰减、12点segment积分和settling allowance，没有robot/cuff/contact闭环。该闭包可算负荷近似，不能保证真实motion/task。残差学习是否有用需真实预序验证。\n')
(P/'FORWARD_PROXY_VALIDATION.md').write_text('# 事前物理代理诊断\n\n当前仅一Human/一matched组B/H150，不能按3807个相邻点冒充独立样本。误差和符号见PROXY_MODEL_RESULTS.json；无未见状态泛化资格。完整tracking、native v/a/jerk、excursion/overshoot、原motion余量及contact/task预测无可验证闭包，标UNKNOWN。reference导数只作模型输出。\n\nPHYSICS_PROXY_USABLE=CONDITIONAL_NOMINAL_LOAD_RANKING_ONLY；RESIDUAL_LEARNING_NEEDED=HYPOTHESIS_TO_TEST；FORWARD_PREDICTION_BLOCKED=FULL_CLOSED_LOOP_MOTION_TASK_CONTACT_NOT_CLOSED。后续三臂只用近似作建议，资格由真实执行决定。\n')
put('audit/HISTORICAL_DIAGNOSIS_DONE.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'zero_new_physics':True,'diagnostic_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'inputs':{str(G/'source/results'/n/f):sc.sha(G/'source/results'/n/f) for n in ['D01R_B','D01R_H150'] for f in ['summary.json','trace.npz']}})
with (P/'RESEARCH_DECISION_LOG.jsonl').open('a') as f:f.write(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':'ZERO_NEW_PHYSICS_DIAGNOSIS','question':'名义模型是否闭合真实前向预测','actual':result['FORWARD_PREDICTION_BLOCKED'],'hypothesis':'局部负荷近似+学习残差可作有界排序建议','next_decision':'真实同链复现B/H150并验证fork后同权限三臂','evidence':'PROXY_MODEL_RESULTS.json','physical_attempts':0},ensure_ascii=False)+'\n')
print(json.dumps({'actual_delta':actual_delta,'predicted_delta':pred_delta,'zero_new_physics':True}),flush=True)
