"""RL-B engineering prototype. No teacher, learned weights or optimized waypoint parameters.

Uses the original scientific native runtime through its existing online action hook.
This runtime's online representation does NOT establish B/H150 qualification parity.
One environment per process; physics is owned by one joined thread.
"""
from common import ROOT, SOURCE, load_config, clean, put, digest
import queue, threading, time, traceback, cProfile, pstats, gc
import numpy as np
import gymnasium as gym
from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime_sac_expert_v1 as rt
from traction_mpc_stage5.task import TaskPhase

class StopRollout(Exception):pass

class PureCoordinationEnv(gym.Env):
    metadata={'render_modes':[]}
    def __init__(self,output_dir,period_s=.05,reward_stage=1,retain_trace=False,profile=False):
        if period_s not in (.005,.01,.02,.05):raise ValueError('unsupported audited cadence')
        if reward_stage not in (1,2):raise ValueError('reward stage')
        self.output_dir=__import__('pathlib').Path(output_dir).resolve()
        if not self.output_dir.is_relative_to(ROOT):raise ValueError('outputs must stay in new study')
        self.period_s=period_s;self.reward_stage=reward_stage;self.retain_trace=retain_trace;self.profile=profile
        self.case,self.options=load_config();self.thread=None;self.episode_index=0
        self.action_space=gym.spaces.Box(-1.,1.,(2,),np.float32)
        self.observation_space=gym.spaces.Box(-np.inf,np.inf,(41,),np.float32)
        self.stop=threading.Event();self.pending=False
    def _initialize(self):
        self.events=queue.Queue(1);self.actions=queue.Queue(1);self.stop=threading.Event()
        self.pending=False;self.capture={'stop_check':self._stop_check};self.summary=None
        self.previous_raw=np.zeros(2);self.intent=None;self.previous_rejected=0.
        self.last_obs=np.zeros(41,np.float32);self.steps=0;self.rejections=0;self.accepted=0
        self.force_integral=0.;self.moment_integral=0.;self.force_peak=0.;self.moment_peak=0.
        self.tick_time=None;self.tick_force=0.;self.tick_moment=0.;self.last_phi=0.;self.phi=0.
        self.last_force=0.;self.motion_variation=0.;self.last_variation=0.;self.previous_dq=None
        self.phases=[];self.rows=[];self.last_phase=None;self.last_task_time=0.;self.terminal_reason=None
        self.reward_totals={'progress':0.,'completion':0.,'force':0.,'variation':0.}
        self.belief_hash=None;self.physics_at_reset=None;self.decisions_wall=[]
        self._next_resource_poll=0.
    def _stop_check(self):
        if self.stop.is_set():raise StopRollout('owned close request')
        # Resource telemetry is a host check, not a physics safety gate. Avoid
        # an NTFS stat per 0.25 ms native step; all original safety checks remain.
        now=time.monotonic()
        if now>=self._next_resource_poll:
            self._next_resource_poll=now+.25
            if (ROOT/'RESOURCE_STOP').exists():raise StopRollout('owned resource request')
    def transition_allowed(self,state):
        # Inherit the historical comparison timing floors, not a teacher trajectory.
        minimum=1. if state.phase is TaskPhase.HOLD else 9.
        return state.phase_elapsed_s>=minimum-1e-10
    def tick(self,t,interface,observation,task_state,spec):
        self._stop_check();q=observation.as_array()[:2];dq=observation.as_array()[2:]
        f=float(np.linalg.norm(interface.measured_force_world_n));m=float(np.linalg.norm(interface.measured_moment_world_nm))
        if self.tick_time is not None:
            dt=t-self.tick_time
            if dt < -1e-10:raise RuntimeError('NONCAUSAL_CLOCK')
            self.force_integral+=self.tick_force*dt;self.moment_integral+=self.tick_moment*dt
            if dt>0 and self.previous_dq is not None:
                # Integral squared estimated acceleration, with public task scale.
                self.motion_variation+=float(np.mean(((dq-self.previous_dq)/dt/np.radians([300.,600.]))**2))*dt
        self.previous_dq=dq.copy();self.tick_time=t;self.tick_force=f;self.tick_moment=m
        self.force_peak=max(self.force_peak,f);self.moment_peak=max(self.moment_peak,m);self.last_task_time=t
        if not self.phases or self.phases[-1]!=task_state.phase.value:self.phases.append(task_state.phase.value)
        start=np.asarray(spec.start_return_target_rad);goal=np.asarray(spec.outbound_goal_target_rad)
        progress=float(np.min(np.clip((q-start)/(goal-start),0.,1.)))
        if task_state.phase is TaskPhase.OUTBOUND:self.phi=progress
        elif task_state.phase is TaskPhase.HOLD:self.phi=1.+min(1.,task_state.hold_elapsed_s/spec.hold_duration_s)
        elif task_state.phase is TaskPhase.RETURN:
            self.phi=2.+float(np.min(np.clip((goal-q)/(goal-start),0.,1.)))
        elif task_state.phase is TaskPhase.COMPLETE:self.phi=3.
    def realized(self,row,target,owned,t):
        rejected=row['status'] not in ('ACCEPTED','IDENTICAL_CONTINUATION')
        self.rejections+=int(rejected);self.accepted+=int(not rejected);self.previous_rejected=float(rejected)
        self.rows.append(dict(t=t,raw=self.previous_raw.copy(),intent_rad=self.intent.copy(),
            executed_target_rad=target,status=row['status'],reason=row.get('reason'),
            first_reference_effect_s=row.get('first_reference_effect_s'),host_realization_ms=row.get('host_realization_ms',0.)))
    def _observation(self,phase,t,target,owned,observation,interface,task_state):
        # Sensor-boundary allowlist only. Never read plant qpos/qvel/native traces here.
        measurement=self.capture['runtime']['measurement_layer'].current
        age=float(observation.sample_timestamp_s-measurement.sample_time_s)
        raw=np.r_[observation.as_array()/np.radians([125.,125.,45.,75.]),
            measurement.robot_q_rad/np.pi,measurement.robot_dq_rad_s/np.pi,
            owned.q_rad/np.pi,owned.dq_rad_s/np.pi,owned.ddq_rad_s2/np.radians([300.,600.]),
            [float(phase is p) for p in (TaskPhase.OUTBOUND,TaskPhase.HOLD,TaskPhase.RETURN)],
            target/np.pi,[t/30.,task_state.phase_elapsed_s/10.],
            interface.measured_force_world_n/200.,interface.measured_moment_world_nm/20.,
            self.previous_raw,self.intent/np.pi,self.previous_rejected,age/.1].astype(np.float32)
        if raw.shape!=(41,) or not np.all(np.isfinite(raw)):raise RuntimeError('INVALID_CAUSAL_OBSERVATION')
        return raw
    def _callback(self,phase,t,target,owned,*,observation,belief,interface,spec,task_state):
        self._stop_check();self.spec=spec
        if self.intent is None:self.intent=owned.q_rad.copy()
        bh=digest({'beta':belief.beta,'residual':belief.state_residual_weights_nm,'geometry':belief.geometry})
        if self.belief_hash is None:self.belief_hash=bh
        elif self.belief_hash!=bh:raise RuntimeError('FROZEN_COMMISSIONED_MODEL_DRIFT')
        obs=self._observation(phase,t,np.asarray(target),owned,observation,interface,task_state)
        self.events.put(('decision',obs,dict(phase=phase.value,task_s=t,potential=self.phi,J_F=self.force_integral,truth_in_actor=False)))
        started=time.perf_counter();action=self.actions.get(timeout=120.)
        self.decisions_wall.append(time.perf_counter()-started)
        self._stop_check()
        if action is None:raise StopRollout()
        self.previous_raw=np.asarray(action,dtype=float).copy()
        # R2: original executor forbids references moving away from phase goal.
        # Map two free rate fractions toward the public current goal. This is
        # a disclosed monotonic-task prior, not an inherited coordination path.
        # a=-1 holds an intent, a=+1 uses its maximum allowed intent rate.
        rate=np.asarray(spec.task_joint_velocity_limit_rad_s)*self.options['reference_velocity_fraction']
        bounds=np.asarray(spec.q_bounds_rad)
        distance=np.asarray(target)-self.intent
        delta=np.sign(distance)*np.minimum(np.abs(distance),self.period_s*rate*(self.previous_raw+1.)*.5)
        self.intent=np.clip(self.intent+delta,bounds[:,0],bounds[:,1])
        return self.intent.copy()
    def _run(self):
        prof=cProfile.Profile() if self.profile else None
        try:
            if prof:prof.enable()
            self.summary=rt.run_executed_case(self.episode_dir,qualification_case=self.case,
                qualification_arm='commissioning_only',simulate_planning_latency=True,formal_qualification=False,
                dev_a_recovery=True,dev_c_bumpless_transfer=False,dev_d_rigid_table_reference=True,
                autonomous_recovery_options=self.options,task_timeout_s=30.,runtime_capture=self.capture,
                execution_mode='SCIENTIFIC_SIMULATION',scientific_host_delay_s=0.,session_context={},
                **self.runtime_kwargs(),sac_hooks=self)
            self.events.put(('terminal',None,self.summary))
        except StopRollout as e:self.events.put(('closed',None,{'reason':str(e)}))
        except BaseException as e:self.events.put(('error',None,dict(error=f'{type(e).__name__}:{e}',traceback=traceback.format_exc())))
        finally:
            if prof:
                prof.disable();prof.dump_stats(str(self.episode_dir/'profile.pstats'))
                stats=pstats.Stats(prof)
                rows=[dict(file=k[0],line=k[1],function=k[2],primitive_calls=v[0],calls=v[1],self_s=v[2],cumulative_s=v[3]) for k,v in stats.stats.items()]
                put(self.episode_dir/'profile.json',sorted(rows,key=lambda x:-x['self_s']))
    def runtime_kwargs(self):
        return dict(online_command_period_s=self.period_s,online_target_callback=self._callback)
    def reset(self,*,seed=None,options=None):
        super().reset(seed=seed);self.close();self._initialize();self.action_space.seed(seed)
        self.episode_index+=1;self.episode_dir=self.output_dir/f'episode_{self.episode_index:04d}'
        self.output_dir.mkdir(parents=True,exist_ok=True);self.host_start=time.perf_counter()
        self.thread=threading.Thread(target=self._run,name='pure-rl-native-owner',daemon=False);self.thread.start()
        kind,obs,info=self.events.get(timeout=240.)
        if kind!='decision':self.close();raise RuntimeError('RESET_'+kind+str(info))
        self.pending=True;self.last_obs=obs;self.last_phi=self.phi;self.last_force=self.force_integral
        self.physics_at_reset=float(self.capture['runtime']['plant'].data.time)
        self.reset_wall_s=time.perf_counter()-self.host_start
        return obs,info
    def _reward(self,success=False,failure=False):
        parts={'progress':5.*(self.phi-self.last_phi),'completion':20. if success else -10. if failure else 0.,
            'force':-(.02 if self.reward_stage==1 else 1.)*(self.force_integral-self.last_force)/100.,
            'variation':-.01*(self.motion_variation-self.last_variation)}
        self.last_phi=self.phi;self.last_force=self.force_integral;self.last_variation=self.motion_variation
        for k,v in parts.items():self.reward_totals[k]+=v
        return sum(parts.values()),parts
    def step(self,action):
        if not self.pending:raise RuntimeError('STEP_REQUIRES_RESET')
        action=np.asarray(action,np.float32)
        if not self.action_space.contains(action):raise ValueError('INVALID_ACTION')
        self.actions.put(action);kind,obs,info=self.events.get(timeout=180.);self.steps+=1
        if kind=='error':self.pending=False;raise RuntimeError(info['error']+'\n'+info['traceback'])
        if kind=='decision':
            self.last_obs=obs;r,parts=self._reward()
            return obs,r,False,False,{**info,'reward_parts':parts,'accepted':self.accepted,'rejections':self.rejections}
        self.pending=False
        if kind!='terminal':raise RuntimeError('UNEXPECTED_'+kind+str(info))
        self.thread.join(timeout=60.)
        reason=info.get('abort_reason') or '';success=info['status']=='COMPLETE'
        if success:self.phi=3.
        r,parts=self._reward(success,not success)
        # Explicit absorbing state: no stale pre-terminal measurement is
        # represented as a current physical state, and no timeout bootstrap.
        terminal=np.zeros(self.observation_space.shape,dtype=np.float32)
        result=self.metrics();result.update(reward_parts=parts,status=info['status'],abort_reason=reason,success=success)
        put(self.episode_dir/'episode_summary.json',result)
        put(self.episode_dir/'action_receipts.json',self.rows)
        # The 10 s phase and 30 s task deadlines are part of this finite-horizon
        # MDP (clock is observed): deadline failure is terminal, not bootstrap.
        actor_info={k:v for k,v in result.items() if k!='physical_evaluation_only'}
        return terminal,r,True,False,actor_info
    def metrics(self):
        runtime=self.capture.get('runtime',{});plant=runtime.get('plant');wall=runtime.get('wall_session')
        total_steps=round(float(plant.data.time)/rt.NOMINAL_PHYSICS_DT_S) if plant is not None else 0
        # Evaluation-only physical evidence. Never concatenated into actor observations.
        truth=None if plant is None else dict(human_q_rad=plant.data.qpos[plant.human_qpos_indices].copy(),
            human_dq_rad_s=plant.data.qvel[plant.human_dof_indices].copy(),ncon=int(plant.data.ncon),dt=plant.model.opt.timestep,
            human_qpos_indices=plant.human_qpos_indices,human_dof_indices=plant.human_dof_indices)
        return dict(rl_decisions=self.steps,task_s=self.last_task_time,native_steps_total=total_steps,
            task_native_steps=round(self.last_task_time/rt.NOMINAL_PHYSICS_DT_S),reset_wall_s=getattr(self,'reset_wall_s',None),
            host_wall_s=time.perf_counter()-self.host_start,force_integral_N_s=self.force_integral,force_peak_N=self.force_peak,
            moment_integral_Nm_s=self.moment_integral,moment_peak_Nm=self.moment_peak,phases=self.phases,
            accepted=self.accepted,rejections=self.rejections,reward_totals=self.reward_totals,belief_hash=self.belief_hash,
            physical_evaluation_only=truth,applied_receipts=0 if wall is None else sum(bool(r.get('applied')) for r in wall.applied_commands),
            actor_wait_wall_s=sum(self.decisions_wall),qualification='UNQUALIFIED_ENGINEERING_PROTOTYPE')
    def close(self):
        self.stop.set()
        if self.thread is not None and self.thread.is_alive():
            try:self.actions.put_nowait(None)
            except queue.Full:pass
            deadline=time.monotonic()+60.
            while self.thread.is_alive() and time.monotonic()<deadline:
                try:self.events.get(timeout=.1)
                except queue.Empty:pass
                self.thread.join(timeout=.1)
            if self.thread.is_alive():raise RuntimeError('OWNER_JOIN_FAILED')
        self.thread=None;self.pending=False
        # A runtime owns cyclic references to session/closures. Join its workers
        # first, then release it explicitly; no simulator state survives reset.
        self.capture={};self.summary=None
        gc.collect()
