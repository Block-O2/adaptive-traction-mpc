"""Research smoke adapter: one physics owner thread, frozen scientific epochs.

Reward is deliberately zero: this qualifies an API, not a SAC reward contract.
No evaluation-only Human truth is exposed to the actor.
"""
from pathlib import Path
import queue,threading,json
import numpy as np
import gymnasium as gym
from . import runtime_online_v1 as rt
from ..task import TaskPhase

class StopSmoke(Exception):pass

class DirectOnlineSmokeEnv(gym.Env):
    metadata={'render_modes':[]}
    def __init__(self,output_dir,case,options,period_s=.02):
        self.output_dir=Path(output_dir);self._generation_case=case;self._options=options;self.period_s=period_s;self.episode_index=0
        self.action_space=gym.spaces.Box(-1.,1.,(2,),dtype=np.float64)
        self.observation_space=gym.spaces.Box(-np.inf,np.inf,(47,),dtype=np.float64)
        self.events=queue.Queue(maxsize=1);self.actions=queue.Queue(maxsize=1);self.thread=None;self.pending=None;self.last_obs=np.zeros(47);self.summary=None
        self.stop=threading.Event();self.step_count=0;self.observation_fields=['causal_estimated_q_dq[4]','owned_reference_q_dq_ddq[6]','estimated_beta[11]','estimated_residual_weights[10]','measured_force_moment[6]','estimated_effective_geometry[4]','phase_onehot[3]','elapsed_task_time[1]','nominal_soft_target[2]']
    def _callback(self,phase,t,target,owned,*,observation,belief,interface,spec):
        g=belief.geometry
        obs=np.r_[observation.as_array(),owned.q_rad,owned.dq_rad_s,owned.ddq_rad_s2,belief.beta,belief.state_residual_weights_nm.ravel(),interface.measured_force_world_n,interface.measured_moment_world_nm,g.hip_plane_m,g.thigh_length_m,g.cuff_distance_m,[float(phase is p) for p in (TaskPhase.OUTBOUND,TaskPhase.HOLD,TaskPhase.RETURN)],t,target].astype(np.float64)
        if not self.observation_space.contains(obs) or not np.all(np.isfinite(obs)):raise RuntimeError('INVALID_CAUSAL_GYM_OBSERVATION')
        if self.stop.is_set():raise StopSmoke()
        self.events.put(('decision',obs,dict(phase=phase.value,physics_task_s=t,model_sequence=belief.sequence,truth_exposed=False)))
        action=self.actions.get(timeout=30.)
        if action is None or self.stop.is_set():raise StopSmoke()
        intended=target+np.asarray(action)*.05
        bounds=np.asarray(spec.q_bounds_rad);bounded=np.clip(intended,bounds[:,0],bounds[:,1])
        self.last_action_modification=dict(requested_target_rad=intended.tolist(),realized_intention_rad=bounded.tolist(),ROM_modified=bool(np.any(intended!=bounded)))
        return bounded
    def _run(self):
        try:
            self.summary=rt.run_executed_case(self.episode_dir,qualification_case=self._generation_case,qualification_arm='continual_adaptive',simulate_planning_latency=True,formal_qualification=False,dev_a_recovery=True,dev_c_bumpless_transfer=False,dev_d_rigid_table_reference=True,autonomous_recovery_options=self._options,task_timeout_s=30.,runtime_capture={},execution_mode='SCIENTIFIC_SIMULATION',scientific_host_delay_s=0.,session_context={},online_command_period_s=self.period_s,online_target_callback=self._callback)
            self.events.put(('terminal',None,self.summary))
        except StopSmoke:self.events.put(('closed',None,{}))
        except BaseException as error:self.events.put(('error',None,dict(error=f'{type(error).__name__}:{error}')))
    def reset(self,*,seed=None,options=None):
        super().reset(seed=seed)
        if self.thread is not None:self.close()
        self.events=queue.Queue(maxsize=1);self.actions=queue.Queue(maxsize=1);self.stop=threading.Event();self.step_count=0
        self.episode_index+=1;self.episode_dir=self.output_dir/f'episode_{self.episode_index:03d}'
        self.thread=threading.Thread(target=self._run,name='single-CR12-physics-owner',daemon=False);self.thread.start()
        kind,obs,info=self.events.get(timeout=120.)
        if kind!='decision':raise RuntimeError('RESET_'+kind+str(info))
        self.pending=True;self.last_obs=obs;return obs,info
    def step(self,action):
        if not self.pending:raise RuntimeError('step requires reset and a nonterminal state')
        action=np.asarray(action,dtype=np.float64)
        if not self.action_space.contains(action):raise ValueError('INVALID_GYM_ACTION')
        self.actions.put(action);kind,obs,info=self.events.get(timeout=120.);self.step_count+=1
        if kind=='error':raise RuntimeError(info['error'])
        if kind=='decision':self.last_obs=obs;return obs,0.,False,False,{**info,'action_modification':getattr(self,'last_action_modification',{})}
        self.pending=False
        reason=info.get('abort_reason') or '';truncated='TIMEOUT' in reason
        terminated=not truncated
        return self.last_obs.copy(),0.,terminated,truncated,dict(status=info.get('status'),abort_reason=reason,physics_complete=info.get('status')=='COMPLETE',reward_scope='zero reward API smoke only')
    def close(self):
        self.stop.set()
        if self.thread is not None and self.thread.is_alive():
            if self.pending:
                try:self.actions.put_nowait(None)
                except queue.Full:pass
            self.thread.join(timeout=120.)
        if self.thread is not None and self.thread.is_alive():raise RuntimeError('PHYSICS_OWNER_FAILED_TO_JOIN')

__all__=['DirectOnlineSmokeEnv']
