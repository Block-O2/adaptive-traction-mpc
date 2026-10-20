"""Causal residual decisions at native B authority; no simulator input."""
from study_common import *
from representation import basis,fit,graph_action,TIMINGS
import numpy as np, pickle
from types import SimpleNamespace
from dataclasses import asdict
from traction_mpc_stage5.full3d_adaptive_integration_v1.online_planning import snapshot_task_call,execute_task_snapshot
from sac_env import normalized,feature_spec,canonical_hash

class ResidualInterface(gates.Interface):
 def __init__(self,teacher='B',policy=None,decision_callback=None,retain_reference=True):
  super().__init__();self.teacher=teacher;self.policy=policy;self.callback=decision_callback;self.labels=[];self.skips=[];self.retain_reference=retain_reference
  self.contract=read('SHARED_COORDINATION_ACTION_CONTRACT.json');self.K=self.contract['K'];self.bound=self.contract['residual_bounds'][1];TIMINGS[self.K]=self.contract['knot_fractions']
  self.previous=np.zeros(self.K);self.model_hash=None
  self.hist=json.loads((STUDY/'deps/HISTORICAL_NATIVE_GRAPH_ACTIONS.json').read_text())
  self.spatial=json.loads((STUDY/'deps/HISTORICAL_SPATIAL_GRAPH.json').read_text())
 def boundary(self,b):
  if self.retain_reference:super().boundary(b)
 def context(self,b):
  phase=b['task_state'].phase
  if phase not in (v2.TaskPhase.OUTBOUND,v2.TaskPhase.RETURN):return None,'HOLD_OR_NONMOVEMENT'
  # Only the existing serializable deployable planner/arguments are copied.
  clone,args=pickle.loads(snapshot_task_call(b['adaptive_planner'],b['arguments']))
  clone.planner.residual_spec={}
  original=clone.decide(**args)
  target=np.asarray(original.executed.target_q_rad)
  if np.max(np.abs(target-clone.planner.reference_phase_goal(phase)))<=1e-10:return None,'NATIVE_TERMINAL_OWNERSHIP'
  spec=b['spec'];start=np.asarray(spec.start_return_target_rad);goal=np.asarray(spec.outbound_goal_target_rad)
  origin,span=(start,goal-start) if phase is v2.TaskPhase.OUTBOUND else (goal,start-goal)
  p=(target-origin)/span;m=float(p.mean());d=float((p[0]-p[1])/2)
  start_m=float(np.mean((np.asarray(b['arguments']['current_reference_state'])[:2]-origin)/span))
  # B's certified soft initial reference may lie just before the registered
  # task start. The v2 graph domain remains [0,1]; this projects only its
  # origin, never a proposed action or physical reference.
  raw_start_m=start_m;start_m=max(0.,start_m)
  if not 0<=start_m<m<1:raise RuntimeError('INVALID_CAUSAL_CHUNK_DOMAIN:'+str((raw_start_m,m,phase.value)))
  belief=b['belief'];model=dict(beta=belief.beta,residual_weights_nm=belief.state_residual_weights_nm,geometry=asdict(belief.geometry),sequence=belief.sequence)
  h=canonical_hash(model)
  if self.model_hash is None:self.model_hash=h
  assert h==self.model_hash,'FROZEN_HUMAN_MODEL_DRIFT'
  ref=b['arguments']['current_reference_state'];interface=b['interface'];g=belief.geometry;t=float(b['physical_now']-b['task_start_time']);ts=b['task_state']
  raw=np.r_[b['observation'].as_array(),ref[:2],ref[2:],b['reference_acceleration'],belief.beta,belief.state_residual_weights_nm.ravel(),interface.measured_force_world_n,interface.measured_moment_world_nm,g.hip_plane_m,g.thigh_length_m,g.cuff_distance_m,[float(phase is q) for q in (v2.TaskPhase.OUTBOUND,v2.TaskPhase.HOLD,v2.TaskPhase.RETURN)],t,target,ts.phase_elapsed_s,ts.hold_elapsed_s,self.previous,[start_m,m],0.,max(0.,30.-t)]
  return dict(phase=phase.value,start_m=start_m,raw_reference_common_progress=raw_start_m,nominal_m=m,nominal_d=d,nominal_target=target.tolist(),observation=normalized(raw),task_s=t,model_hash=h),None
 def teacher_label(self,c,teacher=None):
  teacher=teacher or self.teacher
  if teacher=='B':return np.zeros(self.K)
  if teacher in ('catchup','reversal'):
   graph=gates.pattern(teacher,.01)[c['phase']]
   co,_=fit(self.K,graph,c['start_m'])
   expected=float(np.interp(c['nominal_m'],np.asarray(graph)[:,0],np.asarray(graph)[:,1]))
   weights=basis(self.K,np.array([c['nominal_m']]),c['start_m'])[0]
   co+=weights*(expected-weights@co)/(weights@weights)
   assert np.max(np.abs(co))<=self.bound,'PATTERN_OUTSIDE_FROZEN_ACTION_BOUNDS'
   return co/self.bound
  src=self.spatial[teacher]['targets'][c['phase']];grid=np.linspace(0,1,1001);base=src['nominal_B_native_target_graph']
  residual=np.interp(grid,src['m'],src['d'])-np.interp(grid,base['m'],base['d']);residual[[0,-1]]=0
  co,_=fit(self.K,np.column_stack([grid,residual]),c['start_m'])
  expected=float(np.interp(c['nominal_m'],src['m'],src['d'])-c['nominal_d'])
  weights=basis(self.K,np.array([c['nominal_m']]),c['start_m'])[0]
  co+=weights*(expected-weights@co)/(weights@weights)
  if np.max(np.abs(co))>self.bound+1e-12:raise RuntimeError('TEACHER_OUTSIDE_FROZEN_ACTION_BOUNDS')
  return co/self.bound
 def apply(self,b,c,a,label):
  a=np.asarray(a,float)
  if a.shape!=(self.K,) or np.any(np.abs(a)>1.+1e-6) or not np.all(np.isfinite(a)):raise ValueError('INVALID_SHARED_RESIDUAL_ACTION')
  self.action={c['phase']:graph_action(a*self.bound,c['start_m'])}
  b['planner'].residual_spec=self.action
  self.labels.append(dict(**c,action=a.copy(),teacher_label=np.asarray(label).copy(),graph=self.action,expected_delta=float(basis(self.K,np.array([c['nominal_m']]),c['start_m'])[0]@(a*self.bound))))
  self.previous=a.copy()
 def decision_boundary(self,b):
  c,reason=self.context(b)
  if c is None:
   self.skips.append(dict(phase=b['task_state'].phase.value,reason=reason));self.action={};b['planner'].residual_spec={};return
  label=self.teacher_label(c)
  a=label if self.policy is None else self.policy(c['observation'])
  if self.callback is not None:a=self.callback(c,label)
  self.apply(b,c,a,label)
 def finish(self,env,metric):
  if self.retain_reference:super().finish(env,metric)
  np.savez_compressed(env.episode_dir/'RESIDUAL_DECISIONS.npz',observations=np.asarray([r['observation'] for r in self.labels],np.float32).reshape(-1,55),actions=np.asarray([r['action'] for r in self.labels],np.float32).reshape(-1,self.K),teacher_labels=np.asarray([r['teacher_label'] for r in self.labels],np.float32).reshape(-1,self.K))
  save(metric['name']+'_DECISIONS.json',dict(rows=self.labels,skipped=self.skips,model_hash=self.model_hash,truth_firewall='only causal planner request snapshot, observation, reference, cuff and frozen estimated belief'))

def observation_contract():
 features=feature_spec()
 changes={45:'native_B_nominal_target_hip',46:'native_B_nominal_target_knee',49:'previous_residual_knot_1',50:'previous_residual_knot_2',51:'current_reference_common_progress',52:'native_B_nominal_target_common_progress',53:'unused_zero'}
 for i,name in changes.items():features[i]['name']=name
 save('OBSERVATION_CONTRACT.json',dict(dim=55,features=features,source='existing causal 55D stack, replace old absolute-action history with residual/history/native progress',oracle_future_inputs=False,normalization_fixed=True))
if __name__=='__main__':observation_contract()
