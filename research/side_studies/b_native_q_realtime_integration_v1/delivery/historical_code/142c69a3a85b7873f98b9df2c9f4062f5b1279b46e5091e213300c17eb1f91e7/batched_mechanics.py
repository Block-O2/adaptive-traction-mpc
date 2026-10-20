"""C2: structured math batching of the same 21 native mechanics samples."""
import time,math,numpy as np
EVENTS=[];INSTALLED=False
def install(request):
 global INSTALLED
 if request.get('public_version')!='C2' or INSTALLED:return
 INSTALLED=True
 from traction_mpc_stage5.architecture_recovery_v2 import phase3_human_waypoint as ph
 from traction_mpc_stage4.estimator_v2 import dynamic_regressor_row
 from traction_mpc_stage3.human import soft_limit_torque
 original=ph.AdaptiveMechanicsScreenV22.evaluate
 shadow=request.get('execution_mode')=='SCIENTIFIC_SIMULATION'
 def evaluate(self,belief,candidate,schedule):
  t=time.monotonic_ns();model=belief.human_model();samples=[schedule.sample(float(x)) for x in np.linspace(0.,schedule.duration_s,self.sample_count)];q=np.stack([s.q_rad for s in samples]);dq=np.stack([s.dq_rad_s for s in samples]);ddq=np.stack([s.ddq_rad_s2 for s in samples]);states=np.concatenate([q,dq],axis=1)
  residual=model.state_residual_nm(states);reg=np.stack([dynamic_regressor_row(a,b,c) for a,b,c in zip(q,dq,ddq)]);actions=reg@np.asarray(model.beta,dtype=float)-np.stack([soft_limit_torque(a,b,model.rom_human) for a,b in zip(q,dq)])+residual
  force_map=np.stack([model.geometry.translational_jacobian_world(a).T for a in q]);orth=np.array([1.,1.])/math.sqrt(2.);moment_map=np.array([1.,-1.]);projected=np.matmul(force_map.transpose(0,2,1),orth);denom=np.sum(projected*projected,axis=1)
  if np.any(denom<=1e-18):raise RuntimeError('estimated rigid-cuff allocation is singular')
  force=projected*np.matmul(actions,orth)[:,None]/denom[:,None];remaining=actions-np.matmul(force_map,force[:,:,None])[:,:,0];my=np.matmul(remaining,moment_map)/(moment_map@moment_map);moment=-my[:,None]*model.geometry.joint_axis_world;f=np.linalg.norm(force,axis=1);m=np.linalg.norm(moment,axis=1)
  finite=bool(np.all(np.isfinite(actions)) and np.all(np.isfinite(f+m)));pf=float(np.max(f));pm=float(np.max(m));pr=float(np.max(np.abs(residual)));feasible=finite and pf<=self.force_limit_n+1e-9 and pm<=self.moment_limit_nm+1e-9
  out=dict(evaluated=True,feasible=bool(feasible),rejection_reason=None if feasible else 'adaptive_model_mechanics_limit',belief_sequence=belief.sequence,candidate_label=candidate.label,model='frozen_v2_2_state_residual_human_model',sample_count=self.sample_count,peak_force_n=pf,peak_moment_nm=pm,peak_state_residual_nm=pr,force_limit_n=self.force_limit_n,moment_limit_nm=self.moment_limit_nm,deployable_truth_consumed=False)
  close=abs(pf-self.force_limit_n-1e-9)<1e-8 or abs(pm-self.moment_limit_nm-1e-9)<1e-8
  elapsed=(time.monotonic_ns()-t)/1e6;errors=None
  if shadow or close:
   scalar=original(self,belief,candidate,schedule);errors={k:abs(out[k]-scalar[k]) for k in ('peak_force_n','peak_moment_nm','peak_state_residual_nm')}
   if shadow:
    assert out['feasible']==scalar['feasible'] and max(errors.values())<=1e-10,'BATCHED_MECHANICS_NOT_EQUIVALENT'
   if close:out=scalar
  EVENTS.append(dict(belief_sequence=belief.sequence,candidate_label=candidate.label,sample_count=self.sample_count,batch_ms=elapsed,shadow=shadow,scalar_peak_errors=errors,near_threshold_scalar_fallback=close,all_force_moment_finite_checks_retained=True,batched_inverse_dynamics_component_count=self.sample_count,scalar_inverse_dynamics_API_calls_in_batch=0))
  return out
 ph.AdaptiveMechanicsScreenV22.evaluate=evaluate
