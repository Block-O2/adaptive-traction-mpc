"""Single-Human causal SAC adapter, independent of simulation truth and previous evidence."""
from pathlib import Path
import sys, queue, threading, json, time, hashlib, traceback
import numpy as np
import gymnasium as gym
from dataclasses import asdict
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1/source');S=R/'stages/stage5_personalized_motion_learning'
for stage in ('stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning'):sys.path.insert(0,str(R/'stages'/stage/'src'))
from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime_sac_expert_v1 as rt
from traction_mpc_stage5.task import TaskPhase

ROM=np.radians(125.); VELOCITY=np.radians([45.,75.]); ACCELERATION=np.radians([300.,600.])
GAMMA_TIME_CONSTANT_S=150.
def gamma_for(period):return float(np.exp(-period/GAMMA_TIME_CONSTANT_S))
def canonical_hash(value):return hashlib.sha256(json.dumps(rt._jsonable(value),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def feature_spec():
    names=['estimated_hip_q','estimated_knee_q','estimated_hip_dq','estimated_knee_dq','reference_hip_q','reference_knee_q','reference_hip_dq','reference_knee_dq','reference_hip_ddq','reference_knee_ddq']
    scales=[ROM,ROM,*VELOCITY,ROM,ROM,*VELOCITY,*ACCELERATION]
    names += [f'estimated_beta_{i}' for i in range(11)]+[f'estimated_residual_{j}_{k}' for j in range(2) for k in range(5)]
    # Fixed conservative coefficient units; not statistics from any evaluation.
    scales += [10.]*11+[20.]*10
    names += [f'measured_force_world_{x}' for x in 'xyz']+[f'measured_moment_world_{x}' for x in 'xyz']+['estimated_hip_x','estimated_hip_z','estimated_thigh_length','estimated_cuff_distance','phase_outbound','phase_hold','phase_return','elapsed_task_s','soft_terminal_hip_q','soft_terminal_knee_q','elapsed_phase_s','hold_elapsed_s','previous_raw_hip_action','previous_raw_knee_action','previous_executed_hip_target','previous_executed_knee_target','previous_rejected','remaining_task_s']
    scales += [200.]*3+[20.]*3+[1.]*4+[1.]*3+[30.]+[ROM]*2+[10.,.5]+[1.]*5+[30.]
    assert len(names)==len(scales)==55
    return [dict(index=i,name=n,offset=0.,scale=float(v),clip=None,source='causal observer/reference/model/task history',evaluation_statistics_update=False) for i,(n,v) in enumerate(zip(names,scales))]
SCALES=np.array([x['scale'] for x in feature_spec()])
def normalized(raw):
    raw=np.asarray(raw,dtype=float)
    if raw.shape!=(55,) or not np.all(np.isfinite(raw)):raise RuntimeError('INVALID_CAUSAL_OBSERVATION')
    return (raw/SCALES).astype(np.float32)
def action_to_target(action,spec):
    bounds=np.asarray(spec.q_bounds_rad);return bounds[:,0]+.5*(np.asarray(action)+1.)*(bounds[:,1]-bounds[:,0])
def target_to_action(target,spec):
    bounds=np.asarray(spec.q_bounds_rad);return np.clip(2*(np.asarray(target)-bounds[:,0])/(bounds[:,1]-bounds[:,0])-1.,-1.,1.)
def potential(phase,q,spec,hold_elapsed):
    start=np.asarray(spec.start_return_target_rad);goal=np.asarray(spec.outbound_goal_target_rad)
    progress=float(np.mean(np.clip((np.asarray(q)-start)/(goal-start),0.,1.)))
    if phase is TaskPhase.OUTBOUND:return progress
    if phase is TaskPhase.HOLD:return 1.+min(1.,hold_elapsed/spec.hold_duration_s)
    if phase is TaskPhase.RETURN:return 2.+(1.-progress)
    return 3. if phase is TaskPhase.COMPLETE else 0.

class StopRollout(Exception):pass
class SACExpertEnv(gym.Env):
    metadata={'render_modes':[]}
    def __init__(self,output_dir,case,options,period_s=.05,scope='NATIVE',retain_trace=False):
        self.output_dir=Path(output_dir);self.case=case;self.options=options;self.period_s=period_s;self.scope=scope;self.retain_trace=retain_trace
        self.action_space=gym.spaces.Box(-1.,1.,(2,),np.float32);self.observation_space=gym.spaces.Box(-np.inf,np.inf,(55,),np.float32)
        self.thread=None;self.pending=False;self.episode_index=0;self.stop=threading.Event();self.capture={};self._initialize()
    def _initialize(self):
        self.events=queue.Queue(1);self.actions=queue.Queue(1);self.pending=False;self.step_count=0;self.summary=None;self.last_obs=np.zeros(55,np.float32)
        self.previous_raw=np.zeros(2);self.previous_executed=np.zeros(2);self.previous_rejected=0.;self.last_row={};self.force_integral=0.;self.moment_integral=0.;self.force_peak=0.;self.moment_peak=0.
        self.tick_time=None;self.tick_force=0.;self.tick_moment=0.;self.last_decision_force=0.;self.last_decision_potential=0.;self.last_rejections=0;self.rejections=0;self.fallbacks=0;self.raw_max=np.zeros(55);self.model_hash=None;self.model_record=None
        self.action_records=[];self.runtime_records=[];self.reward_total=0.;self.reward_parts=dict(force=0.,shaping=0.,completion=0.,failure=0.,rejection=0.);self.capture={};self.last_state=None
    def transition_allowed(self,state):
        minimum=1. if state.phase is TaskPhase.HOLD else 9.
        return self.scope=='NATIVE' or state.phase_elapsed_s>=minimum-1e-10
    def tick(self,t,interface,observation,task_state,spec):
        f=float(np.linalg.norm(interface.measured_force_world_n));m=float(np.linalg.norm(interface.measured_moment_world_nm))
        if self.tick_time is not None:
            dt=t-self.tick_time
            if dt < -1e-10:raise RuntimeError('NONCAUSAL_COST_CLOCK')
            self.force_integral+=self.tick_force*dt;self.moment_integral+=self.tick_moment*dt
        self.tick_time=t;self.tick_force=f;self.tick_moment=m;self.force_peak=max(self.force_peak,f);self.moment_peak=max(self.moment_peak,m)
        self.last_state=(task_state.phase,observation.as_array()[:2].copy(),task_state.hold_elapsed_s,spec)
    def realized(self,row,target,owned,t):
        rejected=row['status'] not in ('ACCEPTED','IDENTICAL_CONTINUATION')
        self.rejections+=int(rejected);self.fallbacks+=int(rejected and target is not None);self.previous_rejected=float(rejected)
        self.previous_executed=np.zeros(2) if target is None else target_to_action(target,self.spec)
        self.last_row=dict(raw=self.previous_raw.tolist(),executed=self.previous_executed.tolist(),status=row['status'],reason=row.get('reason'),task_s=t,fallback=bool(rejected and target is not None),full_chain_ms=(time.perf_counter_ns()-self.decision_ready_ns)/1e6,realization_validation_ms=float(row.get('host_realization_ms',0.)))
        self.action_records.append(self.last_row)
        self.runtime_records.append(float(row.get('host_realization_ms',0.)))
    def _observation(self,phase,t,target,owned,observation,belief,interface,task_state):
        g=belief.geometry
        raw=np.r_[observation.as_array(),owned.q_rad,owned.dq_rad_s,owned.ddq_rad_s2,belief.beta,belief.state_residual_weights_nm.ravel(),interface.measured_force_world_n,interface.measured_moment_world_nm,g.hip_plane_m,g.thigh_length_m,g.cuff_distance_m,[float(phase is p) for p in (TaskPhase.OUTBOUND,TaskPhase.HOLD,TaskPhase.RETURN)],t,target,task_state.phase_elapsed_s,task_state.hold_elapsed_s,self.previous_raw,self.previous_executed,self.previous_rejected,max(0.,30.-t)]
        self.raw_max=np.maximum(self.raw_max,np.abs(raw));return normalized(raw)
    def _callback(self,phase,t,target,owned,*,observation,belief,interface,spec,task_state):
        self.spec=spec;self.soft_target=np.asarray(target).copy();self.owned=owned
        model=dict(beta=belief.beta,residual_weights_nm=belief.state_residual_weights_nm,geometry=asdict(belief.geometry),sequence=belief.sequence)
        key=canonical_hash(model)
        if self.model_hash is None:self.model_hash=key;self.model_record=rt._jsonable(model)
        elif key!=self.model_hash:raise RuntimeError('FROZEN_HUMAN_MODEL_DRIFT')
        obs=self._observation(phase,t,target,owned,observation,belief,interface,task_state)
        phi=potential(phase,observation.as_array()[:2],spec,task_state.hold_elapsed_s)
        if self.stop.is_set():raise StopRollout()
        info=dict(phase=phase.value,physics_task_s=t,model_hash=key,model_sequence=belief.sequence,potential=phi,J_F_running=self.force_integral,rejections=self.rejections,truth_exposed=False,action_record=self.last_row)
        self.decision_ready_ns=time.perf_counter_ns()
        self.events.put(('decision',obs,info))
        action=self.actions.get()
        if action is None or self.stop.is_set():raise StopRollout()
        self.previous_raw=np.asarray(action).copy()
        return action_to_target(action,spec)
    def _run(self):
        try:
            self.summary=rt.run_executed_case(self.episode_dir,qualification_case=self.case,qualification_arm='commissioning_only',simulate_planning_latency=True,formal_qualification=False,dev_a_recovery=True,dev_c_bumpless_transfer=False,dev_d_rigid_table_reference=True,autonomous_recovery_options=self.options,task_timeout_s=30.,runtime_capture=self.capture,execution_mode='SCIENTIFIC_SIMULATION',scientific_host_delay_s=0.,session_context={},online_command_period_s=self.period_s,online_target_callback=self._callback,sac_hooks=self)
            self.events.put(('terminal',None,self.summary))
        except StopRollout:self.events.put(('closed',None,{}))
        except BaseException as error:self.events.put(('error',None,dict(error=f'{type(error).__name__}:{error}',traceback=traceback.format_exc())))
    def reset(self,*,seed=None,options=None):
        super().reset(seed=seed)
        if self.thread is not None:self.close()
        self._initialize();self.stop=threading.Event();self.episode_index+=1
        self.episode_dir=self.output_dir/f'episode_{self.episode_index:05d}';self.episode_dir.mkdir(parents=True,exist_ok=False);self.host_start=time.monotonic()
        self.thread=threading.Thread(target=self._run,name='single-CPU-MuJoCo-owner',daemon=False);self.thread.start()
        kind,obs,info=self.events.get(timeout=180.)
        if kind!='decision':raise RuntimeError('RESET_'+kind+str(info))
        self.pending=True;self.last_obs=obs;self.last_decision_force=info['J_F_running'];self.last_decision_potential=info['potential'];return obs,info
    def _reward(self,phi,success,failure):
        parts=dict(force=-(self.force_integral-self.last_decision_force)/100.,shaping=5.*(gamma_for(self.period_s)*phi-self.last_decision_potential),completion=500. if success else 0.,failure=-1000. if failure else 0.,rejection=-.2*(self.rejections-self.last_rejections))
        self.last_decision_force=self.force_integral;self.last_decision_potential=phi;self.last_rejections=self.rejections
        for k,v in parts.items():self.reward_parts[k]+=v
        reward=sum(parts.values());self.reward_total+=reward;return reward,parts
    def step(self,action):
        if not self.pending:raise RuntimeError('STEP_REQUIRES_LIVE_EPISODE')
        action=np.asarray(action,dtype=np.float32)
        if not self.action_space.contains(action):raise ValueError('INVALID_ACTION')
        self.actions.put(action);kind,obs,info=self.events.get(timeout=180.);self.step_count+=1
        if kind=='error':self.pending=False;raise RuntimeError(info['error']+'\n'+info['traceback'])
        if kind=='decision':
            self.last_obs=obs;reward,parts=self._reward(info['potential'],False,False)
            return obs,reward,False,False,{**info,'reward_decomposition':parts}
        self.pending=False
        if kind!='terminal':raise RuntimeError('UNEXPECTED_EVENT_'+kind)
        reason=info.get('abort_reason') or '';success=info['status']=='COMPLETE';timeout='TIMEOUT' in reason
        # Terminal observation is an explicit absorbing policy state, not stale pre-action state.
        terminal=self.last_obs.copy();terminal[41:44]=0.;terminal[54]=0.
        reward,parts=self._reward(0.,success,not success)
        result=dict(status=info['status'],abort_reason=reason,physics_complete=success,success=success,J_F=self.force_integral,force_peak=self.force_peak,moment_integral=self.moment_integral,moment_peak=self.moment_peak,duration_s=info['task']['physics_duration_s'],rejections=self.rejections,fallbacks=self.fallbacks,model_hash=self.model_hash,steps=self.step_count,host_s=time.monotonic()-self.host_start,reward_total=self.reward_total,reward_decomposition=parts,reward_totals=self.reward_parts,scope=self.scope)
        # Compact policy-rate action evidence, never full training physics traces.
        np.savez_compressed(self.episode_dir/'SAC_ACTOR_ACTIONS.npz',raw_action=np.asarray([r['raw'] for r in self.action_records],np.float32).reshape(-1,2),executed_action=np.asarray([r['executed'] for r in self.action_records],np.float32).reshape(-1,2),task_s=np.asarray([r['task_s'] for r in self.action_records],np.float32),status=np.asarray([r['status'] for r in self.action_records]),rejection_reason=np.asarray([r.get('reason') or '' for r in self.action_records]),fallback=np.asarray([r['fallback'] for r in self.action_records],bool))
        result.update(minimum_clearance_m=info['task'].get('minimum_session_clearance_m_deployable'),minimum_true_clearance_m_evaluation_only=info['task'].get('minimum_true_physical_clearance_m_evaluation_only'),physical_rom_violation_steps_evaluation_only=info.get('qualification',{}).get('true_physics',{}).get('rom_violation_steps'),physical_contact_steps_evaluation_only=info.get('qualification',{}).get('true_physics',{}).get('shank_bed_contact_steps'),physical_success_rank='pending unchanged independent scientific evaluator; causal completion is unranked',action_evidence=str((self.episode_dir/'SAC_ACTOR_ACTIONS.npz').relative_to(R)))
        return terminal,reward,not timeout,timeout,result
    def close(self):
        self.stop.set()
        if self.thread is not None and self.thread.is_alive():
            try:self.actions.put_nowait(None)
            except queue.Full:pass
            # Drain outstanding event so a stopping physics owner can finish.
            deadline=time.monotonic()+180.
            while self.thread.is_alive() and time.monotonic()<deadline:
                try:self.events.get(timeout=.1)
                except queue.Empty:pass
                self.thread.join(timeout=.1)
        if self.thread is not None and self.thread.is_alive():raise RuntimeError('PHYSICS_OWNER_JOIN_FAILED')
        self.capture={};self.thread=None;self.pending=False

def load_case_options():
    case=json.loads((S/'configs/high_rom_v1/high_rom_nominal_sync_120_v1.json').read_text())
    old=json.loads((S/'docs/adaptive_human_online_interface_v1/EXPERIMENT_CONTRACT.json').read_text())
    return case,json.loads((R/old['options_path']).read_text())
