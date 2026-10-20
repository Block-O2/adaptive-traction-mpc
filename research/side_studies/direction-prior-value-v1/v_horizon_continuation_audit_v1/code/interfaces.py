from study_common import *
import coordination_adapter as ca
import representation as rep
class TableInterface(ca.ResidualInterface):
 def __init__(self,table=None):
  super().__init__(teacher='B');self.K=3;self.previous=np.zeros(3);rep.TIMINGS[3]=[.1,.4,.7]
  self.table=np.zeros((2,5,3)) if table is None else np.asarray(table).reshape(2,5,3);self.count={'OUTBOUND':0,'RETURN':0}
 def context(self,b):
  previous=self.previous;self.previous=previous[[0,2]]
  try:c,reason=super().context(b)
  finally:self.previous=previous
  if c is not None:
   c['richer_previous_residual']=previous.tolist();c['observation_role']='causal 55D plus explicit K3 residual history'
  return c,reason
 def choose(self,b,c):
  phase=c['phase'];i=self.count[phase];self.count[phase]+=1
  a=self.table[('OUTBOUND','RETURN').index(phase),i] if i<5 else np.zeros(3)
  self.apply(b,c,a,np.zeros(3));self.labels[-1].update(native_index=i,measured_prefix_J_F=b['sac_hooks'].force_integral,measured_prefix_M=b['sac_hooks'].moment_integral)
 def terminal_value_context(self,b):
  # Logger-only context at an existing B-owned terminal request. It creates
  # no action authority and uses exactly the causal observation normalization.
  import pickle
  clone,args=pickle.loads(ca.snapshot_task_call(b['adaptive_planner'],b['arguments']));clone.planner.residual_spec={};target=np.asarray(clone.decide(**args).executed.target_q_rad)
  phase=b['task_state'].phase;spec=b['spec'];start=np.asarray(spec.start_return_target_rad);goal=np.asarray(spec.outbound_goal_target_rad);origin,span=(start,goal-start) if phase is TaskPhase.OUTBOUND else (goal,start-goal);p=(target-origin)/span;raw_start=float(np.mean((np.asarray(args['current_reference_state'])[:2]-origin)/span));belief=b['belief'];g=belief.geometry;ref=args['current_reference_state'];ts=b['task_state'];t=float(b['physical_now']-b['task_start_time']);measured=b['interface']
  raw=np.r_[b['observation'].as_array(),ref[:2],ref[2:],b['reference_acceleration'],belief.beta,belief.state_residual_weights_nm.ravel(),measured.measured_force_world_n,measured.measured_moment_world_nm,g.hip_plane_m,g.thigh_length_m,g.cuff_distance_m,[float(phase is q) for q in (TaskPhase.OUTBOUND,TaskPhase.HOLD,TaskPhase.RETURN)],t,target,ts.phase_elapsed_s,ts.hold_elapsed_s,self.previous[[0,2]],[max(0.,raw_start),float(p.mean())],0.,max(0.,30.-t)]
  return dict(phase=phase.value,start_m=max(0.,raw_start),raw_reference_common_progress=raw_start,nominal_m=float(p.mean()),nominal_d=float((p[0]-p[1])/2),nominal_target=target.tolist(),observation=sac_env.normalized(raw),task_s=t,model_hash=self.model_hash,richer_previous_residual=self.previous.tolist(),observation_role='causal55D plus explicit K3 residual history',value_sample_role='B-owned native terminal request; no action issued')
 def decision_boundary(self,b):
  self.last_physical_time_s=float(b['physical_now'])
  c,reason=self.context(b)
  if c is None:self.skips.append(dict(phase=b['task_state'].phase.value,reason=reason));self.action={};b['planner'].residual_spec={};return
  self.choose(b,c)
 def finish(self,env,metric):
  Interface.finish(self,env,metric)
  save(metric['name']+'_DECISIONS.json',dict(rows=self.labels,skipped=self.skips,K=3,model_hash=self.model_hash))
class ProbeInterface(TableInterface):
 def __init__(self,table=None):
  super().__init__(table);self.probes=[]
 def choose(self,b,c):
  if not self.probes:
   from planning import Predictor
   predictor=Predictor();t=time.monotonic()
   for name,plan in [('B',np.zeros((2,5,3))),('nonzero',self.table.copy())]:
    try:pred=predictor.predict(b,c,plan,self.count);self.probes.append(dict(name=name,prediction=pred))
    except Exception as error:self.probes.append(dict(name=name,error=str(error)))
   save('MODEL_PROBE.json',dict(rows=self.probes,host_s=time.monotonic()-t,model_calls=predictor.calls,schedule_calls=predictor.schedule_calls))
  super().choose(b,c)
