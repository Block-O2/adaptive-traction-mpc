"""Online causal history. Never reads plant, truth, scorer or future receipts."""
import numpy as np
from v5_tail_features import capture as base_capture
GUARD=dict(calls=0,active=0,unsatisfied=0,max_correction=0.)
def install_guard_tap():
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import clearance_feedback as cf
 original=cf.clearance_acceleration_correction
 def tap(*args,**kw):
  result,record=original(*args,**kw)
  GUARD['calls']+=1;GUARD['active']+=int(record.get('active',False));GUARD['unsatisfied']+=int(not record.get('constraint_satisfied',True));GUARD['max_correction']=max(GUARD['max_correction'],float(np.linalg.norm(result)))
  return result,record
 cf.clearance_acceleration_correction=tap
class History:
 def __init__(self):
  self.last=None;self.last_acc=None;self.jf=0.;self.jm=0.;self.n=0;self.peak_v=np.zeros(2);self.peak_a=np.zeros(2);self.peak_j=np.zeros(2);self.qmin=None;self.qmax=None
 def update(self,b):
  now=float(b['physical_now']);obs=np.asarray(b['observation'].as_array());force=float(np.linalg.norm(b['interface'].measured_force_world_n));moment=float(np.linalg.norm(b['interface'].measured_moment_world_nm))
  if self.last is not None:
   t,old,of,om=self.last;dt=now-t
   if dt<=1e-10:return
   self.jf+=of*dt;self.jm+=om*dt;acc=(obs[2:]-old[2:])/dt;self.peak_a=np.maximum(self.peak_a,abs(acc))
   if self.last_acc is not None:self.peak_j=np.maximum(self.peak_j,abs((acc-self.last_acc)/dt))
   self.last_acc=acc
  self.peak_v=np.maximum(self.peak_v,abs(obs[2:]));self.qmin=obs[:2].copy() if self.qmin is None else np.minimum(self.qmin,obs[:2]);self.qmax=obs[:2].copy() if self.qmax is None else np.maximum(self.qmax,obs[:2]);self.last=(now,obs.copy(),force,moment);self.n+=1
 def values(self,study):
  return {'history_measured_JF_N_s':[self.jf],'history_measured_JM_Nm_s':[self.jm],'history_estimated_peak_velocity_rad_s':self.peak_v,'history_estimated_peak_acceleration_rad_s2':self.peak_a,'history_estimated_peak_jerk_rad_s3':self.peak_j,'history_estimated_q_min_rad':np.zeros(2) if self.qmin is None else self.qmin,'history_estimated_q_max_rad':np.zeros(2) if self.qmax is None else self.qmax,'history_guard_counts':[GUARD['calls'],GUARD['active'],GUARD['unsatisfied']],'history_guard_peak_correction_Nm':[GUARD['max_correction']],'history_context_rejections':[len(study.skips)],'history_samples':[self.n]}
def capture(b,study,h):
 z=base_capture(b,study,h);vals=study.risk_history.values(study);elapsed=float(b['physical_now']-b['task_start_time']);vals['contract_time_remaining_s']=[max(0.,30.-elapsed)]
 vals['committed_policy_onehot']=[study.active_policy_tag==p for p in ['B','BEST','HANDOFF','PATTERN','COMPOSE','BLEND']]
 for name,value in vals.items():
  a=np.asarray(value,float).ravel();z['feature_names'] += [name+'_'+str(i) for i in range(len(a))];z['features'] += a.tolist()
 z.update(continuation_policy='commit selected frozen library policy at every subsequent decision; original guard/admission/fallback',committed_policy=study.active_policy_tag,causal_history_definition='measured wrench left integral; observer backward differences at existing 5ms boundaries, not native evaluation truth',original_motion_gate_known='full native gate remains final authority; estimated extrema are not exact native eligibility')
 assert np.isfinite(z['features']).all()
 return z
