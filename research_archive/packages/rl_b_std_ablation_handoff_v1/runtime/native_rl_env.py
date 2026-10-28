"""RL-B r1: two progress fractions at original native planner events.

This is a new action/decision contract, not inheritance of the legacy 50 ms
benchmark. Qualification must be established by the saved tests and physics.
"""
from pure_rl_env import PureCoordinationEnv,StopRollout
from common import put,digest
import numpy as np,time


class NativeProposalEnv(PureCoordinationEnv):
    def runtime_kwargs(self):
        return dict(native_proposal_callback=self._callback)

    def _refresh_action_status(self):
        life=self.capture.get('runtime',{}).get('plan_lifecycle')
        requests=[] if life is None else [x for x in life.records() if x['stage']=='TASK']
        resolved=[x for x in requests if x['outcome']!='PENDING']
        self.accepted=sum(x['outcome']=='ACTIVATED' for x in resolved)
        self.rejections=sum(x['outcome']!='ACTIVATED' for x in resolved)
        self.previous_rejected=float(bool(resolved) and resolved[-1]['outcome']!='ACTIVATED')
        return requests

    def _callback(self,phase,t,target,owned,*,observation,belief,interface,spec,task_state):
        self._stop_check();self.spec=spec
        # Past resolved admission is online causal information. Never expose
        # a pending proposal as already accepted or refresh its source age.
        self._refresh_action_status()
        if self.intent is None:self.intent=owned.q_rad.copy()
        bh=digest({'beta':belief.beta,'residual':belief.state_residual_weights_nm,'geometry':belief.geometry})
        if self.belief_hash is None:self.belief_hash=bh
        elif self.belief_hash!=bh:raise RuntimeError('FROZEN_COMMISSIONED_MODEL_DRIFT')
        obs=self._observation(phase,t,np.asarray(target),owned,observation,interface,task_state)
        self.events.put(('decision',obs,dict(phase=phase.value,task_s=t,potential=self.phi,
            J_F=self.force_integral,truth_in_actor=False,decision_contract='native_planner_event_v1')))
        started=time.perf_counter();action=self.actions.get(timeout=120.)
        self.decisions_wall.append(time.perf_counter()-started);self._stop_check()
        if action is None:raise StopRollout()
        self.previous_raw=np.asarray(action,dtype=float).copy()
        # Intent visualization only. Planner constructs and certifies the exact
        # internal-terminal candidate from this action in its immutable snapshot.
        span=np.abs(np.asarray(spec.outbound_goal_target_rad)-np.asarray(spec.start_return_target_rad))
        q=observation.as_array()[:2];distance=np.asarray(target)-q
        self.intent=q+np.sign(distance)*np.minimum(np.abs(distance),span*.2*(self.previous_raw+1.)*.5)
        self.rows.append(dict(action_id=len(self.rows),t=t,phase=phase.value,raw=self.previous_raw.copy(),
            source_sample_s=observation.sample_timestamp_s,intent_rad=self.intent.copy()))
        return self.previous_raw.copy()

    def metrics(self):
        result=super().metrics();runtime=self.capture.get('runtime',{})
        requests=self._refresh_action_status()
        records=runtime.get('rl_proposal_records',[])
        result.update(architecture='native_planner_event_v1',nominal_policy_period_s=None,
            decision_times_s=[r['task_s'] for r in records],accepted=self.accepted,rejections=self.rejections,
            action_definition='two fractions of original maximum progress per native planner event',
            qualification='PENDING_EXECUTION_AND_TASK_QUALIFICATION')
        if records:
            put(self.episode_dir/'native_rl_proposals.json',records)
            put(self.episode_dir/'native_rl_requests.json',requests)
        return result
