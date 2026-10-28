"""Same native environment with durable online tick and terminal accounting."""
from native_rl_env import NativeProposalEnv
from common import clean,put,ROOT
import json,os
class TrainingEvidenceEnv(NativeProposalEnv):
    def __init__(self,*args,episode_offset=0,**kwargs):
        self.tick_stream=None;self.episode_offset=episode_offset;self.episode_seed=None
        super().__init__(*args,**kwargs)
    def reset(self,*,seed=None,options=None):
        self.episode_seed=20261020+self.episode_offset+self.episode_index
        return super().reset(seed=self.episode_seed,options=options)
    def tick(self,t,interface,observation,task_state,spec):
        super().tick(t,interface,observation,task_state,spec)
        if self.tick_stream is None:
            self.tick_stream=(self.episode_dir/'online_tick_evidence.jsonl').open('w',buffering=65536)
            put(self.episode_dir/'public_reward_contract.json',{'start_return_target_rad':spec.start_return_target_rad,
                'outbound_goal_target_rad':spec.outbound_goal_target_rad,'hold_duration_s':spec.hold_duration_s,
                'reward_stage':self.reward_stage,'force_weight':.02 if self.reward_stage==1 else 1.,
                'acceleration_normalization_deg_s2':[300.,600.],'progress_weight':5.,'completion_bonus':20.,'failure_penalty':-10.,'variation_weight':.01})
        row={'task_s':t,'phase':task_state.phase.value,'phase_elapsed_s':task_state.phase_elapsed_s,'hold_elapsed_s':task_state.hold_elapsed_s,'online_estimated_state':observation.as_array(),
             'measured_force_world_n':interface.measured_force_world_n,'measured_moment_world_nm':interface.measured_moment_world_nm}
        self.tick_stream.write(json.dumps(clean(row),separators=(',',':'))+'\n')
        if round(t/.005)%100==0:self.tick_stream.flush()
    def metrics(self):
        value=super().metrics();runtime=self.capture.get('runtime',{});wall=runtime.get('wall_session')
        journal=None if wall is None else getattr(wall.native_states,'path',None)
        value.update(episode_seed=self.episode_seed,episode_number=self.episode_offset+self.episode_index,
                     motion_variation_penalty_integral=self.motion_variation,native_journal_file=None if journal is None else journal.relative_to(ROOT).as_posix())
        return value
    def step(self,action):
        result=super().step(action)
        if result[2] or result[3]:
            if self.tick_stream:self.tick_stream.flush()
            summary=self.summary or {}
            put(self.episode_dir/'terminal_physics_summary.json',{'status':summary.get('status'),'abort_reason':summary.get('abort_reason'),
                'task':summary.get('task'),'true_physics':summary.get('qualification',{}).get('true_physics'),
                'metrics':self.metrics(),'purpose':'training accounting only; no automatic heldout or learned-policy qualification'})
        return result
    def close(self):
        try:super().close()
        finally:
            if self.tick_stream is not None:self.tick_stream.close();self.tick_stream=None
