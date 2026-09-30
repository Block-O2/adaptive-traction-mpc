"""Research-only target proposals and separate safe-candidate value ranking.

No plant/evaluation state is imported. Scheduling and hard checks are inherited
unchanged; fixed-schedule causal offset check matches frozen exploration v2.
"""
from __future__ import annotations
from copy import copy
from dataclasses import replace
import hashlib, json, os, pickle, time
import numpy as np
from traction_mpc_stage5.full3d_adaptive_integration_v1.terminal_reference import TerminalSetHumanWaypointPlannerV1
from traction_mpc_stage5.task import TaskPhase
from coordination_pacing_adapter_v1 import shape

SPEC_ENV='VALUE_LEARNING_RESEARCH_SPEC_V1'

def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'))
def digest(value): return hashlib.sha256(canonical(value).encode()).hexdigest()

def offset(s, descriptor):
 p=np.asarray(descriptor.get('parameters',[0.,.5,0.,0.,0.,0.,0.]),float)
 p=np.pad(p,(0,max(0,7-len(p))))
 # L1 is contained in L2, which is contained in L3. Added basis coefficients
 # have endpoint-zero smooth bumps at early/middle/late then two extra knots.
 delta=.5*p[0]*shape(s,float(p[1]))
 for weight,peak in zip(p[2:7],(.25,.5,.75,.375,.625)):
  delta+=.5*weight*shape(s,peak)
 return float(delta)

def make_path(baseline, start, goal, descriptor):
 result={}; horizon=descriptor.get('horizon','H3')
 for phase,source in baseline.items():
  origin=np.asarray(start if phase=='OUTBOUND' else goal,float)
  span=np.asarray(goal if phase=='OUTBOUND' else start,float)-origin
  result[phase]=[]
  for i,item in enumerate(source):
   base=np.asarray(item['target_q_rad'],float)
   s=float(np.mean((base-origin)/span))
   active=(i<len(source)-1 and not (phase=='RETURN' and horizon!='H4')
           and not (phase=='OUTBOUND' and horizon=='H1' and i>=1)
           and not (phase=='OUTBOUND' and horizon=='H2' and i>=3))
   delta=offset(s,descriptor) if active else 0.
   if phase=='RETURN' and descriptor.get('return_reverse',False): delta=-delta
   if descriptor.get('synchronous',False) and active: target=origin+s*span
   else: target=base+span*np.array([delta,-delta])
   result[phase].append({**item,'target_q_rad':target.tolist()})
 return result

def context_features(*,state,reference,belief,phase,elapsed,remaining,start,goal,
                     previous,descriptor,index,path,target,schedule):
 """Only deployable snapshot and causally declared policy memory are inputs."""
 state=np.asarray(state,float); reference=np.asarray(reference,float)
 start=np.asarray(start,float); goal=np.asarray(goal,float)
 origin=start if phase=='OUTBOUND' else goal
 end=goal if phase=='OUTBOUND' else start
 progress=(state[:2]-origin)/(end-origin)
 geom=belief.get('effective_geometry',{})
 vals=[]; names=[]
 def add(label,values):
  array=np.asarray(values,float).reshape(-1)
  vals.extend(array.tolist()); names.extend([f'{label}_{i}' for i in range(len(array))])
 add('estimated_state',state); add('reference_state',reference)
 add('start',start); add('goal',goal); add('phase',[phase==x for x in ('OUTBOUND','HOLD','RETURN')])
 add('time_context',[elapsed,remaining,index]); add('progress',progress)
 add('remaining_span',end-state[:2]); add('previous_executed_delta',previous)
 add('beta',belief.get('beta',[0]*11)); add('residual',belief.get('state_residual_weights_nm',np.zeros((2,5))))
 for key,n in [('origin_world_m',3),('plane_x_world',3),('joint_axis_world',3),('plane_z_world',3),('hip_plane_m',3),('thigh_length_m',1),('knee_to_cuff_in_cuff_m',3)]:
  add('geometry_'+key,geom.get(key,[0]*n))
 add('model_summary',[belief.get('residual_limit_nm',0),belief.get('dynamics_sample_count',0),belief.get('accepted_beta_update_count',0),belief.get('residual_update_count',0)])
 p=list(descriptor.get('parameters',[0,.5])); p=p+[0]*(7-len(p))
 add('continuation_parameters',p[:7]); add('continuation_horizon',[descriptor.get('horizon','H3')==x for x in ('H1','H2','H3','H4')])
 add('continuation_rule',[descriptor.get('return_reverse',False),descriptor.get('synchronous',False),descriptor.get('matched_duration_factor',1.3)])
 # Declared next targets are controller plan memory, not actual future states.
 future=path.get(phase,[])[index+1:index+4]
 for j in range(3):
  item=future[j] if j<len(future) else {'target_q_rad':end,'duration_s':0}
  add(f'continuation_target_{j}',item['target_q_rad']); add(f'continuation_duration_{j}',[item['duration_s']])
 add('candidate_target',target); add('candidate_delta',np.asarray(target)-state[:2])
 add('candidate_schedule',[schedule.duration_s]); add('candidate_terminal_velocity',schedule.candidate.dq_waypoint_rad_s)
 array=np.asarray(vals,float)
 if not np.all(np.isfinite(array)): raise ValueError('nonfinite deployable features')
 return array,names

def snapshot_research_task_call(adaptive_planner,arguments):
 snapshot=copy(adaptive_planner); snapshot.planner=copy(adaptive_planner.planner)
 snapshot.planner.research_phase_index=sum(d.phase is arguments['phase'] for d in adaptive_planner.planner.decisions)
 snapshot.planner.decisions=[]; snapshot.belief_sequences_used=[]
 return pickle.dumps((snapshot,arguments),protocol=pickle.HIGHEST_PROTOCOL)

class ResearchPlanner(TerminalSetHumanWaypointPlannerV1):
 def __init__(self,*args,**kwargs):
  super().__init__(*args,**kwargs)
  self.research_spec=json.loads(os.environ[SPEC_ENV])
  self.research_model=None
  if self.research_spec.get('model_path'):
   from value_models import load_model
   self.research_model=load_model(self.research_spec['model_path'])

 def screen_target(self,target,item,label,kwargs):
  state=np.asarray(kwargs['current_deployable_state'],float)
  reference=np.asarray(kwargs['current_reference_state'],float)
  alternative=self._evaluate(label=label,state=state,reference_state=reference,
    phase=kwargs['phase'],phase_elapsed_s=kwargs['phase_elapsed_s'],phase_remaining_s=kwargs['phase_remaining_s'],
    action=np.asarray(target)-state[:2],execution_feasibility_checker=kwargs.get('execution_feasibility_checker'),
    value_state_or_belief=kwargs.get('value_state_or_belief'),candidate_value_evaluator=None)
  if not alternative.feasible: return alternative
  period=self.scheduler.reference_period_s
  duration=round(float(item['duration_s'])*float(self.research_spec.get('matched_duration_factor',1.3))/period)*period
  try:
   fixed=self.scheduler.plan_fixed_duration_reference_contract(current_q_hat_rad=reference[:2],current_dq_hat_rad_s=reference[2:],candidate=alternative.schedule.candidate,duration_s=duration,phase_elapsed_s=kwargs['phase_elapsed_s'])
  except ValueError as exc: return replace(alternative,feasible=False,rejection_reason='MATCHED_PACING_INFEASIBLE:'+str(exc))
  checker=kwargs.get('execution_feasibility_checker')
  screen={'evaluated':False,'feasible':True} if checker is None else dict(checker(fixed.candidate,fixed))
  if not screen.get('feasible',True):
   return replace(alternative,feasible=False,rejection_reason='MATCHED_PACING_INFEASIBLE:'+str(screen.get('rejection_reason')),schedule=fixed,execution_screen=screen)
  if getattr(self,'causal_tracking_offset_clearance',False):
   snapshot=self.tracking_reference_snapshot
   if not np.array_equal(state,np.asarray(snapshot['source_state_rad_rad_s'])): raise ValueError('tracking-reference snapshot state mismatch')
   error=state[:2]-np.asarray(snapshot['q_ref_rad']); velocity_error=state[2:]-np.asarray(snapshot['dq_ref_rad_s'])
   shifted=fixed.coefficients.copy(); shifted[:,0]+=error
   certificate=fixed.continuous_clearance_certificate
   lowers=certificate.get('combined_body_lowers_m') if isinstance(certificate,dict) else None
   nominal=float(min(lowers.values())) if lowers else float(self.scheduler.clearance_evaluator.certified_minimum(fixed.coefficients,fixed.duration_s))
   lower=float(self.scheduler.clearance_evaluator.certified_minimum(shifted,fixed.duration_s))
   if not np.all(np.isfinite(error)) or not np.isfinite(lower): raise ValueError('nonfinite causal tracking-offset clearance')
   causal={'source':'immutable request q estimate minus actual receipt-owned q reference at same sensor timestamp',
    'reference_snapshot':snapshot,'position_error_rad':error.copy(),'velocity_error_rad_s':velocity_error.copy(),
    'schedule_origin_q_rad':fixed.coefficients[:,0].copy(),'nominal_continuous_model_clearance_lower_m':nominal,
    'prediction':'constant observed position error added to full candidate reference path','future_error_bound_proven':False,
    'continuous_model_clearance_lower_m':lower,'required_lower_m':0.0,'feasible':lower>=0.0}
   screen={**screen,'causal_tracking_offset_clearance':causal}
   if not causal['feasible']: return replace(alternative,feasible=False,rejection_reason='MATCHED_PACING_INFEASIBLE:CAUSAL_TRACKING_OFFSET_CLEARANCE',schedule=fixed,execution_screen=screen)
  return replace(alternative,schedule=fixed,execution_screen=screen)

 def decide(self,**kwargs):
  started=time.perf_counter(); previous=self.previous_executed_delta_q_rad.copy()
  # Existing production proposals/scores remain available as logged comparator.
  original=super().decide(**kwargs)
  legacy_finish=time.perf_counter(); spec=self.research_spec; phase=kwargs['phase'].value
  if phase=='HOLD': return original
  index=getattr(self,'research_phase_index',sum(d.phase is kwargs['phase'] for d in self.decisions)-1)
  descriptor=spec.get('descriptor',{'parameters':[0,.5],'horizon':'H4'})
  descriptor={**descriptor,'matched_duration_factor':spec.get('matched_duration_factor',1.3)}
  baseline=spec['baseline_waypoints']
  path=spec.get('replay_targets') or make_path(baseline,self.start_rad,self.goal_rad,descriptor)
  source=path.get(phase,[])
  if index>=len(source): raise ValueError('RESEARCH_INFEASIBLE:baseline waypoint count exhausted')
  item=source[index]; base=np.asarray(item['target_q_rad'],float)
  target=base.copy()
  branch=spec.get('branch')
  if branch and branch['phase']==phase and branch['index']==index:
   span=(self.goal_rad-self.start_rad)*(1 if phase=='OUTBOUND' else -1)
   target+=span*np.array([branch['offset'],-branch['offset']])
  proposals=[('declared_path',target)]
  if spec.get('mode')=='VALUE_RANK' and index<len(source)-1:
   span=(self.goal_rad-self.start_rad)*(1 if phase=='OUTBOUND' else -1)
   offsets=spec.get('candidate_offsets',[-.04,-.02,0.,.02,.04,.06])
   proposals=[(f'local_{j}',base+span*np.array([delta,-delta])) for j,delta in enumerate(offsets)]
  proposal_finish=time.perf_counter()
  evaluations=[]; feature_ms=0.; features=[]
  continuation_id=digest({'descriptor':descriptor,'baseline':baseline,'rule':'frozen_declared_path_after_current_action'})
  for label,q in proposals:
   ev=self.screen_target(q,item,f'research_{phase.lower()}_{index:02d}_{label}',kwargs)
   if ev.feasible:
    before=time.perf_counter()
    x,names=context_features(state=kwargs['current_deployable_state'],reference=kwargs['current_reference_state'],belief=kwargs.get('value_state_or_belief') or {},
     phase=phase,elapsed=kwargs['phase_elapsed_s'],remaining=kwargs['phase_remaining_s'],start=self.start_rad,goal=self.goal_rad,previous=previous,
     descriptor=descriptor,index=index,path=path,target=q,schedule=ev.schedule)
    feature_ms+=1000*(time.perf_counter()-before)
    context={'schema':'research_decision_context_v1','features':x.tolist(),'feature_names':names,
      'belief':kwargs.get('value_state_or_belief'),'previous_executed_action':previous.tolist(),
      'continuation_id':continuation_id,'continuation_descriptor':descriptor,'continuation_rule':'frozen_declared_path_after_current_action',
      'path_index':index,'declared_remaining_targets':source[index+1:],
      'active_value_version':spec.get('model_version','ZERO'),'branch':branch,'action_provenance':label,'safety_truth_consumed':False}
    ev=replace(ev,execution_screen={**ev.execution_screen,'research_context':context})
    features.append((len(evaluations),x))
   evaluations.append(ev)
  screen_finish=time.perf_counter()
  admissible=[i for i,e in enumerate(evaluations) if e.feasible]
  if not admissible: raise ValueError('RESEARCH_INFEASIBLE:'+';'.join(str(e.rejection_reason) for e in evaluations))
  predicted=None
  if self.research_model is not None and spec.get('mode')=='VALUE_RANK':
   predicted=self.research_model.predict(np.stack([x for _,x in features]))
   if not np.all(np.isfinite(predicted)): raise ValueError('nonfinite learned cost ranking')
   selected=min(range(len(features)),key=lambda j:(float(predicted[j]),float(evaluations[features[j][0]].total_cost)))
   chosen_index=features[selected][0]
  else: chosen_index=admissible[0]
  inference_finish=time.perf_counter()
  chosen=evaluations[chosen_index]
  targets=np.stack([q for _,q in proposals]); dists=np.linalg.norm(targets[:,None]-targets[None,:],axis=-1)
  latency={'legacy_planner_ms':1000*(legacy_finish-started),'proposal_ms':1000*(proposal_finish-legacy_finish),
   'feature_ms':feature_ms,'feasibility_scheduling_ms':max(0.,1000*(screen_finish-proposal_finish)-feature_ms),
   'inference_selection_ms':1000*(inference_finish-screen_finish),'decision_total_ms':1000*(inference_finish-started),
   'candidate_count':len(proposals),'feasible_count':len(admissible),
   'target_pairwise_max_distance_rad':float(np.max(dists)),'target_pairwise_mean_distance_rad':float(np.mean(dists)),
   'scope':'research adapter through selected scheduled reference; downstream production command and activation validation measured by request lifecycle'}
  chosen=replace(chosen,execution_screen={**chosen.execution_screen,'research_latency':latency,
   'predicted_remaining_cost_n_s':None if predicted is None else float(predicted[admissible.index(chosen_index)]),
   'all_admissible_Q_n_s':None if predicted is None else predicted.tolist()})
  evaluations[chosen_index]=chosen
  decision=replace(original,executed=chosen,selection_mode='research_separate_value_ranking' if predicted is not None else 'research_declared_path',
   evaluations=original.evaluations+tuple(evaluations),runtime_ms=1000*(time.perf_counter()-started))
  self.decisions[-1]=decision; self.previous_executed_delta_q_rad=chosen.proposed_delta_q_rad.copy()
  return decision
