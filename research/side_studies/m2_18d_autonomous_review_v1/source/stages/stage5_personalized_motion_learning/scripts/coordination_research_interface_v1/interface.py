from common import *
from schedule import *
class CoordinationInterface:
 """One execution route for E chunks and V candidates, with retained fallback."""
 def __init__(self,actions=None,*,replay=True):
  self.replay_mode=replay;self.actions=actions or {};self.tapes={};self.phase=None;self.epoch=None;self.schedule=None;self.records=[];self.current_context=None
  if any(k not in ('OUTBOUND','RETURN') or a.phase!=k for k,a in self.actions.items()):raise ValueError('ONLY_PHASE_MATCHED_OUTBOUND_RETURN_ACTIONS_ALLOWED')
  z=np.load(L/'B_TAPE.npz')
  for phase in ('OUTBOUND','HOLD','RETURN'):
   m=z['phase']==phase;t=z['t'][m];q=z['q'][m];v=z['v'][m];a=z['a'][m]
   self.tapes[phase]=PhaseTape(phase,t-t[0],q,v,a,q[-1]-q[0] if phase!='HOLD' else self.tapes['OUTBOUND'].span)
 def reference(self,*,phase,physical_now,task_start_time,task_state,spec,belief,clearance,scheduler,owned,estimated_state,runtime):
  phase_name=phase.value
  self.current_context=dict(spec=spec,belief=belief,clearance=clearance,scheduler=scheduler,estimated_state=estimated_state,phase=phase)
  if self.phase!=phase_name:
   self.phase=phase_name;self.epoch=float(physical_now)
   action=None if phase_name=='HOLD' else self.actions.get(phase_name)
   self.schedule=DifferentialSchedule(self.tapes[phase_name],action,spec,phase)
   cert=certify(self.schedule,spec=spec,belief=belief,clearance=clearance,owned=owned,scheduler=scheduler,tracking_error=np.asarray(estimated_state[:2])-np.asarray(owned[0]))
   row=dict(event='PHASE_ACTIVATION',phase=phase_name,action=None if action is None else action.record(),certificate=cert)
   self.records.append(row)
   if not cert['feasible']:raise ValueError(json.dumps(clean(row)))
  return self.schedule.sample(physical_now-self.epoch-self.schedule.offset_s),self.schedule,self.epoch+self.schedule.offset_s
 def offer(self,action,physical_now):
  if self.phase=='HOLD':raise ValueError('HOLD_ACTION_DISABLED')
  ctx=self.current_context;s=float((physical_now-self.epoch)/self.tapes[self.phase].duration_s)
  if action.phase!=self.phase or abs(action.current_progress-s)>1e-9:raise ValueError('ACTION_PHASE_OR_TIMESTAMP_MISMATCH')
  current=self.schedule.sample(physical_now-self.epoch-self.schedule.offset_s)
  state=self.schedule.residual_state(physical_now-self.epoch)
  if np.max(np.abs(np.array(state)-np.array(action.current_state)))>1e-10:raise ValueError('RESIDUAL_C2_STATE_MISMATCH')
  proposed=DifferentialSchedule(self.tapes[self.phase],action,ctx['spec'],ctx['phase'],offset_s=physical_now-self.epoch)
  cert=certify(proposed,spec=ctx['spec'],belief=ctx['belief'],clearance=ctx['clearance'],owned=(current.q_rad,current.dq_rad_s,current.ddq_rad_s2),scheduler=ctx['scheduler'],tracking_error=ctx['estimated_state'][:2]-current.q_rad)
  row=dict(event='OFFER',phase=self.phase,action=action.record(),certificate=cert,status='ACCEPTED' if cert['feasible'] else 'REJECTED_RETAIN_CERTIFIED_CONTINUATION')
  self.records.append(row)
  if cert['feasible']:self.schedule=proposed
  return row
 def boundary(self,b):pass
 def decision_state(self,physical_now):
  if self.phase is None:raise ValueError('NO_OWNED_PHASE')
  t=float(physical_now-self.epoch);tape=self.tapes[self.phase];s=min(t/tape.duration_s,1.)
  base=tape.sample(t);p=(base.q_rad-tape.q[0])/tape.span
  residual_state=self.schedule.residual_state(t)
  return dict(version='coordination_research_state_v1',phase=self.phase,normalized_phase_clock=s,baseline_normalized_joint_progress=p,common_progress=float(np.mean(p)),baseline_coordination_lead=float((p[0]-p[1])/2),current_residual_state=residual_state,future_residual_knots=[] if self.schedule.action is None else [k for k in self.schedule.action.knots if k[0]>s],horizon_s=self.schedule.duration_s,knot_units='normalized phase clock',residual_units='normalized differential progress',feasible_current_amplitude_envelope=feasible_residual_envelope(p),causal_model=self.current_context['belief'].value_state_record(),estimated_state=self.current_context['estimated_state'],HOLD_action_enabled=self.phase!='HOLD')
 def finish(self,env,metric):save(metric['name']+'_interface.json',dict(records=self.records,actions={k:v.record() for k,v in self.actions.items()},metrics=metric))

def pattern(phase,kind,magnitude=.025):
 knots={'hip':((.3,magnitude),(.65,magnitude),(1.,0.)),
        'knee':((.3,-magnitude),(.65,-magnitude),(1.,0.)),
        'reversal':((.25,magnitude),(.65,-magnitude),(1.,0.)),
        'catchup':((.25,magnitude),(.55,0.),(1.,0.))}[kind]
 return ResidualAction(phase,0.,(0.,0.,0.),knots,1.,provenance='manual_'+kind)
if __name__=='__main__':run('B_tape_replay',CoordinationInterface())
