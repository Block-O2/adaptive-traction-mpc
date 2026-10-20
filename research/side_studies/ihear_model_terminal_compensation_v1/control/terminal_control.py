"""Isolated bounded terminal acceleration intent before original safety transforms.

Only explicit causal estimated state, issued reference, model and task phase enter.
No direct motor command, plant state, future measurement or Human truth access.
"""
from dataclasses import replace
import numpy as np
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointMPCShadowContractV1

VERSION='terminal_acceleration_intent_v1'
def smooth(x):
 x=np.clip(x,0.,1.);return x*x*(3.-2.*x)

class TerminalIntent:
 def __init__(self,config):
  self.config=dict(config);self.last_time=None;self.last_delta=np.zeros(2);self.rows=[]
 def evaluate(self,*,state,qref,vref,aref,goal,phase,sample_s,now_s):
  x=np.asarray(state);qr=np.asarray(qref);vr=np.asarray(vref);ar=np.asarray(aref);goal=np.asarray(goal)
  finite=all(np.all(np.isfinite(v)) for v in [x,qr,vr,ar,goal])
  stale=not finite or not 0<=now_s-sample_s<.1-1e-12
  dt=.005 if self.last_time is None else sample_s-self.last_time
  if dt<=0 or dt>.010+1e-8:stale=True
  raw=np.zeros(2);near=0.;direction=0.;risk=0.
  if not stale and phase=='RETURN':
   # Spatial/velocity gate, with no absolute task-time trigger.
   near=float(smooth((np.radians(6.)-abs(qr[1]-goal[1]))/np.radians(4.)))
   mode=self.config['mode']
   if mode=='DAMPING':raw[1]=near*float(self.config['kd_fraction'])*22.*(vr[1]-x[3])
   if mode in ['PD','PDFF']:
    direction=float(smooth((-x[3]+np.radians(.2))/np.radians(.4)))
    stopdist=max(0.,-x[3])**2/(2*.35)
    risk=float(smooth((stopdist+np.radians(2.)-(x[1]-goal[1]))/np.radians(2.)))
    pd=float(self.config['kp_aux'])*(goal[1]-x[1])-float(self.config['kd_aux'])*x[3]
    raw[1]+=near*direction*risk*max(0.,pd)
   if mode in ['FF','PDFF']:raw+=near*float(self.config['ff_fraction'])*ar
  bound=float(self.config.get('acceleration_cap_rad_s2',.2));rate=float(self.config.get('rate_cap_rad_s3',1.0))
  clipped=np.clip(raw,-bound,bound)
  if stale:delta=np.zeros(2) # original stale safety still decides whether any command can execute
  else:delta=self.last_delta+np.clip(clipped-self.last_delta,-rate*dt,rate*dt)
  row=dict(version=VERSION,mode=self.config['mode'],sample_s=float(sample_s),now_s=float(now_s),phase=phase,estimated_state=x.copy(),issued_q_rad=qr.copy(),issued_dq_rad_s=vr.copy(),issued_ddq_rad_s2=ar.copy(),goal_rad=goal.copy(),near_gate=near,direction_gate=direction,risk_gate=risk,raw_delta_rad_s2=raw,delta_rad_s2=delta.copy(),saturated=bool(np.any(raw!=clipped)),rate_limited=bool(np.any(abs(clipped-self.last_delta)>rate*dt+1e-12)),stale=stale,truth_consumed=False)
  self.last_time=float(sample_s);self.last_delta=delta.copy();self.rows.append(row)
  return row

class TerminalControlContract(HumanWaypointMPCShadowContractV1):
 def command(self,**kw):
  intent=self.terminal_intent;frame=self.terminal_frame;original=kw.get('action_transform')
  observation=kw['observation'];state=observation.as_array();candidate=kw['mapped_waypoint'].candidate
  assert abs(observation.sample_timestamp_s-frame['sample_s'])<1e-9
  assert np.max(abs(candidate.q_waypoint_rad-frame['qref']))<1e-10
  row=intent.evaluate(state=state,**frame);delta=row['delta_rad_s2']
  def transform(x,a,u,stamp):
   assert abs(stamp-frame['sample_s'])<1e-9
   correction=self.human_model.mass_matrix(x[:2])@delta
   row.update(generalized_correction_nm=correction.copy(),original_PD_acceleration_rad_s2=a.copy(),augmented_acceleration_rad_s2=(a+delta).copy())
   action=u+correction
   if original is not None:action=original(x,a+delta,action,stamp)
   row['post_original_transform_action_nm']=action.copy()
   return action
  out=super().command(**{**kw,'action_transform':transform})
  row['original_executable_filter_metadata']=out.filter_result.metadata()
  return replace(out,desired_human_acceleration_rad_s2=out.desired_human_acceleration_rad_s2+delta)
 def contract_record(self):
  out=super().contract_record();out.update(version=VERSION,new_isolated_controller_contract=True,gains_tuned=self.terminal_intent.config['mode']=='DAMPING',original_B_control_law_unchanged=False,terminal_config=self.terminal_intent.config,reference_geometry_certificate_scope_unchanged=True,changed_action_rechecked_by_original_executable_filter_and_supervisor=True)
  return out

def bind_boundary(b,intent,candidate_hash):
 runtime=b['runtime'];contract=runtime['contract'];obs=b['observation'];r=b['reference']
 contract.__class__=TerminalControlContract;contract.terminal_intent=intent
 contract.terminal_frame=dict(qref=r.q_rad.copy(),vref=r.dq_rad_s.copy(),aref=r.ddq_rad_s2.copy(),goal=b['planner'].reference_phase_goal(b['task_state'].phase).copy(),phase=b['task_state'].phase.value,sample_s=float(obs.sample_timestamp_s),now_s=float(b['physical_now']))
 old=runtime.get('reference_progress_commit')
 def commit(receipt):
  if old is not None:old(receipt)
  row=intent.rows[-1]
  assert abs(receipt['source_sample_time_s']-row['sample_s'])<1e-9
  receipt['terminal_control_contract']=dict(version=VERSION,candidate_hash=candidate_hash,mode=intent.config['mode'],sample_s=row['sample_s'],delta_rad_s2=row['delta_rad_s2'].copy(),generalized_correction_nm=row['generalized_correction_nm'].copy(),fresh_actual_output_filter=True)
 runtime['reference_progress_commit']=commit
