"""Offline only: analytic endpoint geometry, original replay and necessary-condition audit.
No stepping, no hook registration, no safety qualification.
"""
from pathlib import Path
import sys,os,json,time
from types import SimpleNamespace
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');sys.dont_write_bytecode=True
P=Path(__file__).resolve().parents[1];R=P/'runtime';sys.path[:0]=[str(P/'source'),str(R/'control'),str(R/'code')]
import study_common as sc
from acl2_shared import put,append,utc
import numpy as np
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.high_rom_v1 import deployable_prior
from traction_mpc_stage3.coupled import BED_HEIGHT_M,SLEEVE_HALF_LENGTH_M as L,SLEEVE_OUTER_RADIUS_M as RAD
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import RigidTableReferenceEnvelopeV1
from traction_mpc_stage5.full3d_adaptive_integration_v1.clearance_feedback import clearance_acceleration_correction,project_acceleration_halfspaces
B=json.loads((P.parent/'autonomous_coordination_learning_v2/history/CAUSAL_COMMISSIONED_BELIEF.json').read_text());G=PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in B['geometry'].items()});ENV=RigidTableReferenceEnvelopeV1(G)
MODEL=sc.rt.StateResidualHumanModel(G,np.array(B['beta']),deployable_prior(),residual_weights_nm=np.array(B['residual_weights_nm']))
def endpoints(q,dq):
 q=np.asarray(q);dq=np.asarray(dq);phi=q[0]-q[1];px,pz=G.plane_x_world[2],G.plane_z_world[2];az=px*np.cos(phi)+pz*np.sin(phi);ap=-px*np.sin(phi)+pz*np.cos(phi);root=np.sqrt(1-az*az)
 if root<1e-6:raise ValueError('RADIAL_PROJECTION_SINGULARITY')
 th=px*np.cos(q[0])+pz*np.sin(q[0]);tp=-px*np.sin(q[0])+pz*np.cos(q[0]);v=np.array([1.,-1.]);out=[]
 for sign in [-1,1]:
  c=G.cuff_distance_m+sign*L;d=c+RAD*az/root
  gap=float(ENV.cuff_centers(q)[0,2]+sign*L*az-RAD*root-BED_HEIGHT_M)
  grad=G.thigh_length_m*tp*np.array([1.,0.])+d*ap*v
  hess=-G.thigh_length_m*th*np.diag([1.,0.])+(-d*az+RAD*ap*ap/root**3)*np.outer(v,v)
  out.append(dict(sign=sign,gap=gap,gradient=grad,hessian=hess,velocity=float(grad@dq),curvature=float(dq@hess@dq)))
 return out

def main():
 start=time.time();rng=np.random.default_rng(2026102204);errors=[];maxgrad=0.;maxcurve=0.;n=0
 for _ in range(2500):
  q=rng.uniform(np.radians([0.,0.]),np.radians([85.,110.]));dq=rng.uniform(-.6,.6,2)
  if abs(np.cos(q[0]-q[1]))<.1:continue
  es=endpoints(q,dq);errors.append(min(e['gap'] for e in es)-float(ENV.margins(q)['sleeve_m'][0]));n+=1
  h=1e-4
  for i,e in enumerate(es):
   grads=[]
   for v in np.eye(2):grads.append((endpoints(q+h*v,dq)[i]['gap']-endpoints(q-h*v,dq)[i]['gap'])/(2*h))
   maxgrad=max(maxgrad,float(np.max(abs(np.asarray(grads)-e['gradient']))))
   fd=(endpoints(q+h*dq,dq)[i]['gap']-2*e['gap']+endpoints(q-h*dq,dq)[i]['gap'])/h**2
   maxcurve=max(maxcurve,abs(fd-e['curvature']))
 cases=[]
 for ident in ['CORE_C_019','PPO_SCRATCH_TRAIN_0009']:
  d=json.loads((P.parent/'representation_execution_v3/analysis/forensics'/f'{ident}.json').read_text());c=d['guard'];ss=np.asarray(d['event_state']);a=np.array(c['requested_acceleration_rad_s2']);limits=np.array(c['joint_acceleration_box_rad_s2'])
  interface=SimpleNamespace(human_position_world_m=np.array([0.,0.,c['gap_m']+RAD+BED_HEIGHT_M]),human_rotation_world=np.eye(3),human_velocity_world_m_s=np.array([0.,0.,c['gap_velocity_m_s']]),human_angular_velocity_world_rad_s=np.zeros(3))
  corr,rep=clearance_acceleration_correction(MODEL,ss,a,interface,limits,response_s=c['response_s'],adverse_acceleration_m_s2=c['adverse_acceleration_m_s2']);errs={k:float(np.max(abs(np.array(rep[k])-np.array(c[k])))) for k in ['model_curvature_m_s2','model_gap_gradient_m_rad','correction_nm','required_gap_acceleration_m_s2']}
  ep=endpoints(ss[:2],ss[2:]);normals=np.array([e['gradient'] for e in ep]);curves=np.array([e['curvature'] for e in ep]);req=np.array([2*(1e-5-e['gap']-c['response_s']*e['velocity'])/c['response_s']**2+c['adverse_acceleration_m_s2'] for e in ep]);adj,feas=project_acceleration_halfspaces(a,normals,req-curves,limits)
  sensitivity=[]
  for h in [1e-3,1e-4,1e-5,1e-6,1e-7,1e-8]:
   q=ss[:2];dq=ss[2:];vs=np.array([[e['gap'] for e in endpoints(q+s*h*dq,dq)] for s in [-1,0,1]])
   sensitivity.append(dict(h_s=h,envelope_curvature=(vs[0].min()-2*vs[1].min()+vs[2].min())/h**2,endpoint_curvature_fd=(vs[0]-2*vs[1]+vs[2])/h**2))
  # Known original common gap/rate can be used conservatively for both, but
  # derivative/timing/command-error bounds remain unidentified.
  req_common=np.repeat(c['required_gap_acceleration_m_s2'],2);common_adj,common_feas=project_acceleration_halfspaces(a,normals,req_common-curves,limits)
  cases.append(dict(id=ident,state=ss,original_replay_errors=errs,original=c,analytic_model_endpoints=ep,model_only_dual_adjusted_acceleration=adj,model_only_dual_feasible=feas,model_only_dual_correction=MODEL.inverse_dynamics(ss[:2],ss[2:],adj)-MODEL.inverse_dynamics(ss[:2],ss[2:],a),common_scalar_dual_adjusted_acceleration=common_adj,common_scalar_dual_feasible=common_feas,finite_difference_sensitivity=sensitivity,causal_endpoint_replay='NOT_IDENTIFIED from minimum gap/rate sufficient scalars',physical_execution='NOT_RUN'))
 # Constructive failure of the response-endpoint inequality as a continuous
 # path certificate, even under exact constant gap acceleration.
 T=.08;adverse=1.5;g0=2e-5;v0=-.02;acc=2.;required=2*(1e-5-g0-T*v0)/T**2+adverse;tstar=-v0/acc
 counter=dict(g0_m=g0,v0_m_s=v0,T_s=T,adverse_m_s2=adverse,actual_constant_acceleration_m_s2=acc,required_m_s2=required,instantaneous_constraint_satisfied=acc>=required,horizon_gap_m=g0+T*v0+.5*acc*T*T,minimum_at_s=tstar,minimum_gap_m=g0+v0*tstar+.5*acc*tstar*tstar,gap_at_next_5ms_m=g0+v0*.005+.5*acc*.005**2,threshold_m=1e-5,scope='Scalar counterexample to response inequality sufficiency, not an assertion this trajectory occurred in plant')
 # Common measurement minimum has non-unique endpoint derivative completions.
 nonident=[]
 for az,azdot in [(0.,0.),(.001,.2),(-.001,-.2)]:
  center=cases[0]['original']['gap_m']+L*abs(az)+RAD*np.sqrt(1-az*az)+BED_HEIGHT_M;gv=cases[0]['original']['gap_velocity_m_s'];vz=gv-(-L*np.sign(az)+RAD*az/np.sqrt(1-az*az))*azdot
  nonident.append(dict(axis_z=az,axis_rate=azdot,center_z=center,center_velocity=vz,endpoint_gaps=[center+s*L*az-RAD*np.sqrt(1-az*az)-BED_HEIGHT_M for s in [-1,1]],endpoint_gap_rates=[vz+(s*L+RAD*az/np.sqrt(1-az*az))*azdot for s in [-1,1]]))
 out=dict(status='PASS_OFFLINE_ANALYSIS_CANDIDATE_NOT_PROMOTED',pointwise_samples=n,max_min_gap_equivalence_error_m=max(abs(np.array(errors))),max_gradient_fd_error=maxgrad,max_directional_curvature_fd_error=maxcurve,cases=cases,necessary_protection_counterexample=counter,nonunique_causal_endpoint_completions=nonident,physical_steps=0,wall_s=time.time()-start,gate=dict(geometry='POINTWISE_EQUIVALENCE_CONFIRMED',smoothness='LOCAL_ONLY_AWAY_FROM_VERTICAL_AXIS',model_instantaneous_halfspaces='EXACT_2D_PROJECTION_WITH_EMPTY_SET_FLAG',causal_derivative_error_bound='NOT_ESTABLISHED',post_filter_actuator_tracking_bound='NOT_ESTABLISHED',continuous_inter_sample_guarantee='NOT_ESTABLISHED',infeasible_stop_semantics='ORIGINAL_RETURNS_FLAG_AND_CLIPPED_COMMAND_NO_LOCAL_STOP',decision='NO_PHYSICAL_GUARD_REPLACEMENT; retain original and study deployable branch-aware prediction'))
 put('analysis/ENDPOINT_STUDY.json',out);append('RESEARCH_DECISIONS.jsonl',dict(utc=utc(),hypothesis='双光滑端点约束能否替代原反馈并保守保护',evidence='analysis/ENDPOINT_STUDY.json',result='点态等价与局部解析导数成立；时域/误差/执行保护缺口仍在，原函数也非不变性证明',decision='不晋级新guard；保持原执行，转向历史分支信息的前瞻预测与优化',followup='冻结局部传统分支响应预测器；新候选与新合法prefix验证',budget=dict(physics_cap=55,optimizer_per_arm_cap=8,validation_reserve=12)))
 print(sc.clean({k:out[k] for k in ['status','pointwise_samples','max_min_gap_equivalence_error_m','max_gradient_fd_error','max_directional_curvature_fd_error','wall_s','gate']}));print('COUNTEREXAMPLE',counter)
if __name__=='__main__':main()
