from pathlib import Path
import importlib.util,json
from research_common import ROOT,atomic,sha,now
T=ROOT/'unattended/template';p=T/'scripts/rewards.py';spec=importlib.util.spec_from_file_location('inactive_reward_definitions',p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
versions={}
for name,cfg in module.VERSIONS.items():
 out=ROOT/'unattended/reward_versions'/name/'CONFIG.json';atomic(out,cfg);versions[name]=dict(config=str(out.relative_to(ROOT)),config_sha256=sha(out),full_source_sha256=sha(p),status='PROPOSED_NOT_TRAINED' if name=='R4' else 'HISTORICAL_FORMULA_REFERENCE')
atomic(ROOT/'unattended/REWARD_VERSION_MANIFEST.json',dict(time_utc=now(),source=str(p.relative_to(ROOT)),source_sha256=sha(p),versions=versions,training_this_stage=0))
ppo=dict(lr=.0003,gamma=1.,gae_lambda=.95,n_epochs=4,batch_size=16,clip_range=.2,clip_range_vf=None,normalize_advantage=True,ent_coef=0.,vf_coef=.5,max_grad_norm=.5,target_kl=None,rollout='aggregate64',aggregate_transitions=64,complete_episodes_only=True,merge_singleton_tail=True,actor_observation_dims=41,action_dims=2,raw_action_density_before_execution_clip=True,terminal_flush_per_declared_endpoint=True,durable_pending_each_episode=True)
atomic(ROOT/'unattended/PPO_CONFIG_VERSIONS.json',dict(time_utc=now(),versions={'CHECKPOINT_STD':dict(ppo,std_initialization=None),'STD_INIT_0p2':dict(ppo,std_initialization=.2,std_learnable=True,pending_cross_distribution_reuse=False,Adam='inherited after verified full restore'),'H2_AGG128':dict(ppo,std_initialization=None,aggregate_transitions=128)},worker_source_sha256=sha(T/'scripts/worker.py'),status='INACTIVE_NO_TRAINING_THIS_STAGE'))
job=dict(job_id='REPLACE_UNIQUE_ID',branch='REPLACE_REGISTERED_BRANCH',seed=1495656323,parent_checkpoint='REPLACE_WITH_EXACT_CHECKPOINT_FROM_NEXT_PARENT_CHECKPOINTS_JSON',start_episode=0,episodes=10,mode='training',learning_rate=.0003,rollout='aggregate64',aggregate_transitions=64,reward='R1',target_kl=None,rollout_terminal_episode=10,std_initialization=None,carry_complete_pending=True,durable_pending_each_episode=True)
atomic(ROOT/'unattended/JOB_CONFIG_TEMPLATE.json',dict(status='TEMPLATE_ONLY_NOT_EXECUTABLE_WITH_PLACEHOLDERS',config=job))
atomic(ROOT/'unattended/EXPERIMENT_STATE_TEMPLATE.json',dict(status='PREPARED',phase='AWAITING_NEXT_STAGE_EXPLICIT_START',t0_utc=None,hard_stop_utc=None,owned_processes=[],attempts=[],native_steps=0,optimizer_steps=0,old_PID_or_timestamps_copied=False))
print('inactive R0-R4 and PPO/job/state definitions versioned')
