"""Causal structured multi-step search; all predictions use model arithmetic only."""
from study_common import *
import pickle
from coordination_adapter import snapshot_task_call
from representation import graph_action
from known_model import model
from interfaces import TableInterface
from traction_mpc_stage4 import estimator_v2 as model_accounting
def counted_prediction(function):
 def wrapper(self,*args,**kwargs):
  start=getattr(model_accounting,'RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS',0)
  try:return function(self,*args,**kwargs)
  finally:self.full_model_api_calls+=getattr(model_accounting,'RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS',0)-start
 return wrapper
def feature(c,table,count):
 r=read('KNOWN_MODEL_PARAMETERS.json')
 remaining=np.asarray(table).reshape(2,5,3).copy()
 for i,phase in enumerate(('OUTBOUND','RETURN')):remaining[i,:count[phase]]=0.
 return np.r_[c['observation'],c.get('richer_previous_residual',[0,0,0]),remaining.ravel(),[count['OUTBOUND']/5,count['RETURN']/5],np.asarray(r['beta'])/10.,[r['geometry']['thigh_length_m'],np.linalg.norm(r['geometry']['knee_to_cuff_in_cuff_m'])]].astype(np.float32)
class Predictor:
 def __init__(self):self.model=model();self.calls=0;self.schedule_calls=0;self.wall_s=0.;self.full_model_api_calls=0
 def wrench(self,q,dq,ddq):
  self.calls+=1;torque=self.model.inverse_dynamics(q,dq,ddq);return self.model.allocate_generalized_action(torque,q)['wrench_world']
 @counted_prediction
 def predict(self,b,c,table,count,horizon=3):
  start=time.monotonic();clone,args=pickle.loads(snapshot_task_call(b['adaptive_planner'],b['arguments']));table=np.asarray(table).reshape(2,5,3);counts=count.copy();x=np.asarray(args['current_deployable_state']).copy();ref=np.asarray(args['current_reference_state']).copy();phase=args['phase'];phase_s=float(args['phase_elapsed_s']);task_s=c['task_s'];total=0.;mom=0.;near=0.;terminal=None;durations=[];accepted=[];interior=0;phase_arrival={};phase_segments=0
  error=x-ref;last_residual=np.asarray(c.get('richer_previous_residual',[0,0,0])).copy()
  for step in range(16):
   if phase is TaskPhase.HOLD:
    duration=1.02;w=self.wrench(ref[:2],np.zeros(2),np.zeros(2));total+=np.linalg.norm(w[:3])*duration;mom+=np.linalg.norm(w[3:])*duration;task_s+=duration;phase=TaskPhase.RETURN;phase_s=0.;phase_segments=0;clone.planner.reset_phase();continue
   phasekey=phase.value;index=counts[phasekey];startq=np.asarray(clone.planner.spec.start_return_target_rad);goal=np.asarray(clone.planner.spec.outbound_goal_target_rad)
   origin,span=(startq,goal-startq) if phase is TaskPhase.OUTBOUND else (goal,startq-goal)
   start_m=max(0.,float(np.mean((ref[:2]-origin)/span)))
   action=table[('OUTBOUND','RETURN').index(phasekey),index] if index<5 else np.zeros(3)
   clone.planner.residual_spec={phasekey:graph_action(action*.2,start_m)} if start_m<1. else {}
   if step>0 and getattr(clone.planner,'causal_tracking_offset_clearance',False):
    # Future internal forecast nodes have predicted references, never fabricated
    # physical receipts. The first node retains the exact causal receipt snapshot.
    snapshot=dict(clone.planner.tracking_reference_snapshot)
    snapshot.update(source_state_rad_rad_s=x.copy(),q_ref_rad=ref[:2].copy(),dq_ref_rad_s=ref[2:].copy(),proposed_schedule_origin_rad_rad_s=ref.copy(),prediction_node_only=True)
    clone.planner.tracking_reference_snapshot=snapshot
   self.schedule_calls+=1
   decision=clone.decide(**dict(args,current_deployable_state=x,current_reference_state=ref,phase=phase,phase_elapsed_s=phase_s,phase_remaining_s=max(.001,10.-phase_s)))
   schedule=decision.executed.schedule
   if schedule is None:raise ValueError('MODEL_NO_FEASIBLE_CONTINUATION')
   endpoint=np.max(np.abs(decision.executed.target_q_rad-clone.planner.reference_phase_goal(phase)))<=1e-10
   # The graph is sampled once per native interior opportunity, not 3 controls.
   if not endpoint:counts[phasekey]+=1;interior+=1;last_residual=action.copy()
   segmentF=0.;segmentM=0.;n=12;dt=schedule.duration_s/n
   for t in np.arange(n)*dt:
    sample=schedule.sample(float(t));decay=np.exp(-4.*t/max(schedule.duration_s,.001));q=sample.q_rad+error[:2]*decay;dq=sample.dq_rad_s+error[2:]*decay;w=self.wrench(q,dq,sample.ddq_rad_s2);segmentF+=np.linalg.norm(w[:3])*dt;segmentM+=np.linalg.norm(w[3:])*dt
   total+=segmentF;mom+=segmentM;phase_s+=schedule.duration_s;task_s+=schedule.duration_s;durations.append(schedule.duration_s);accepted.append(decision.selection_mode)
   last=schedule.sample(schedule.duration_s);ref=np.r_[last.q_rad,last.dq_rad_s];error*=np.exp(-4.);x=ref+error
   # Minimum existing receipt/activation ownership tick is physical time,
   # not compute time. Do not let it vanish in the analytic continuation.
   phase_segments+=1
   if terminal is None and (interior>=horizon or endpoint):
    near=total;endc=dict(c);endc['task_s']=task_s;obs=np.asarray(c['observation']).copy();obs[:4]=sac_env.normalized(np.r_[x,np.zeros(51)])[:4];obs[4:8]=sac_env.normalized(np.r_[np.zeros(4),ref,np.zeros(47)])[4:8];obs[8:10]=last.ddq_rad_s2/sac_env.ACCELERATION
    terminal_wrench=self.wrench(x[:2],x[2:],last.ddq_rad_s2);obs[31:34]=terminal_wrench[:3]/200.;obs[34:37]=terminal_wrench[3:]/20.;obs[44]=task_s/30.;obs[47]=phase_s/10.;obs[54]=max(0.,30.-task_s)/30.;history_raw=np.zeros(55);history_raw[49:51]=last_residual[[0,2]];obs[49:51]=sac_env.normalized(history_raw)[49:51];obs[51]=max(0.,float(np.mean((ref[:2]-origin)/span)));obs[52]=min(1.,obs[51]+.2);obs[45:47]=(origin+span*obs[52])/sac_env.ROM;endc['observation']=obs;endc['richer_previous_residual']=last_residual
    terminal=dict(feature=feature(endc,table,counts),task_s=task_s,phase=phase.value,count=counts.copy(),state=x.copy(),reference=ref.copy(),interior_opportunities=interior)
   if endpoint:
    # Native pass-through executes a certified 40 ms bridge plus receipt ticks.
    # 50 ms per segment bounds the observed handoff, including phase-start
    # segments conservatively. This is feasibility metadata only: the shared
    # V_base arithmetic and existing Monte Carlo labels remain unchanged.
    phase_arrival[phase.value]=phase_s+.050*phase_segments
    wait=max(0.,9.005-phase_s);w=self.wrench(ref[:2],np.zeros(2),np.zeros(2));total+=np.linalg.norm(w[:3])*wait;mom+=np.linalg.norm(w[3:])*wait;task_s+=wait
    if phase is TaskPhase.RETURN:break
    phase=TaskPhase.HOLD;phase_s=0.;clone.planner.reset_phase()
  if terminal is None:raise ValueError('MODEL_HORIZON_UNREACHED')
  self.wall_s+=time.monotonic()-start
  # Motion endpoint is not physical task completion. Preserve a 0.5 s
  # completion/estimator-settling allowance, equal to the frozen task's HOLD
  # dwell scale; this bounds an observed preflight mismatch, not safety truth.
  return dict(near_cost=near,V_base=total-near,total_cost=total,model_moment=mom,terminal=terminal,predicted_durations=durations,selection_modes=accepted,predicted_phase_arrival_elapsed_s=phase_arrival,completion_settling_allowance_s=.5,matched_model_feasible=all(t+.5<=9.020+1e-9 for t in phase_arrival.values()))
class SearchInterface(TableInterface):
 def __init__(self,method='P',seed=202610060,weights=None,prefix=None,value_scale=1.):
  super().__init__();self.method=method;self.rng=np.random.default_rng(seed);self.predictor=Predictor();self.search_rows=[];self.previous_plan=np.zeros((2,5,3));self.weights=weights;self.network=None;self.prefix=prefix or {}
  if 'G' in method or 'V' in method:
   from inference import Networks
   self.network=Networks(weights)
  self.value_scale=float(value_scale);assert .5<=self.value_scale<=1.5,'PILOT_CALIBRATION_BOUND'
 def choose(self,b,c):
  start=time.monotonic();phase=c['phase'];idx=self.count[phase]
  if phase in self.prefix and idx<len(self.prefix[phase]):
   action=np.asarray(self.prefix[phase][idx]);self.count[phase]+=1;self.apply(b,c,action,np.zeros(3));self.labels[-1].update(native_index=idx,legal_prefix=True,measured_prefix_J_F=b['sac_hooks'].force_integral,measured_prefix_M=b['sac_hooks'].moment_integral);return
  mean=self.previous_plan.copy();sd=.22;records=[];best=None;proposal=None
  if self.network is not None and 'G' in self.method:proposal=self.network.proposals(feature(c,np.zeros((2,5,3)),self.count))
  for generation in range(2):
   if not self.search_rows:
    carried=np.asarray(read('HISTORICAL_K3_DESIGN_REFERENCE.json')['table']).reshape(2,5,3);carried_source='qualified_unlearned_K3_seed'
   else:carried=self.previous_plan.copy();carried_source='remaining_plan'
   candidates=[(np.zeros((2,5,3)),'B'),(carried,carried_source)]
   for j in range(6):
    if proposal is not None and j<3:plan=proposal[j%len(proposal)].reshape(2,5,3)+self.rng.normal(0.,.08,(2,5,3));source='G'
    else:
     noise=self.rng.normal(0.,sd,(2,5,3));noise[:,1:]=.65*noise[:,:-1]+.35*noise[:,1:];plan=mean+noise;source='CEM'
    candidates.append((np.clip(plan,-1,1),source))
   current=[]
   for j,(plan,source) in enumerate(candidates):
    for p in ('OUTBOUND','RETURN'):plan[('OUTBOUND','RETURN').index(p),:self.count[p]]=self.previous_plan[('OUTBOUND','RETURN').index(p),:self.count[p]]
    try:
     pred=self.predictor.predict(b,c,plan,self.count)
     if not pred['matched_model_feasible']:raise ValueError('PREDICTED_R2_MATCHED_TIMING_INELIGIBLE:'+str(pred['predicted_phase_arrival_elapsed_s']))
     delta=0. if self.network is None or 'V' not in self.method else self.value_scale*self.network.value(pred['terminal']['feature']);score=pred['total_cost']+delta
     row=dict(generation=generation,index=j,source=source,plan=plan.copy(),score=score,deltaV=delta,prediction=pred,rejected=False);current.append(row)
     if best is None or score<best['score']:best=row
    except (ValueError,RuntimeError) as error:row=dict(generation=generation,index=j,source=source,plan=plan.copy(),rejected=True,reason=str(error))
    records.append(row)
   if current:
    elite=sorted(current,key=lambda x:x['score'])[:3];values=np.asarray([r['plan'] for r in elite]);mean=.5*mean+.5*values.mean(0);sd=max(.02,.5*sd+.5*float(values.std(0).mean()))
  selected=np.zeros((2,5,3)) if best is None else best['plan'];self.previous_plan=selected.copy();self.table=selected.copy();self.count[phase]+=1
  action=selected[('OUTBOUND','RETURN').index(phase),idx] if idx<5 else np.zeros(3);self.apply(b,c,action,np.zeros(3))
  self.labels[-1].update(native_index=idx,measured_prefix_J_F=b['sac_hooks'].force_integral,measured_prefix_M=b['sac_hooks'].moment_integral)
  self.search_rows.append(dict(context=c,count_before={**self.count,phase:idx},candidates=records,selected_source='B' if best is None else best['source'],selected_plan=selected,decision_wall_s=time.monotonic()-start,model_calls=self.predictor.calls,model_schedule_calls=self.predictor.schedule_calls))
 def finish(self,env,metric):
  super().finish(env,metric);save(metric['name']+'_SEARCH.json',dict(method=self.method,rows=self.search_rows,model_calls=self.predictor.calls,model_schedule_calls=self.predictor.schedule_calls,full_model_inverse_dynamics_calls=self.predictor.full_model_api_calls,model_wall_s=self.predictor.wall_s,network_calls=0 if self.network is None else self.network.calls,network_inference_s=0. if self.network is None else self.network.inference_s,information_condition='KNOWN_MODEL',continuation_version='native-certified-committed-K3-suffix-v1',online_physics_branches=0))
