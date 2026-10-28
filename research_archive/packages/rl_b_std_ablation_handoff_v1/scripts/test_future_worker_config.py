"""Run the actual pure config validator extracted from future worker AST, no Torch/import/reset."""
from pathlib import Path
import ast,copy,json
from research_common import ROOT,atomic,now
source=(ROOT/'unattended/template/scripts/worker.py').read_text();tree=ast.parse(source);fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='validate_config');namespace={};exec(compile(ast.Module(body=[fn],type_ignores=[]),'<actual_future_worker_config_validator>','exec'),namespace);validate=namespace['validate_config']
base=json.loads((ROOT/'unattended/JOB_CONFIG_TEMPLATE.json').read_text())['config'];base.update(job_id='REWARD_R4_seed1495656323_to010',branch='REWARD_R4',parent_checkpoint='/declared/parent',reward='R4')
checks=dict(R4_branch_has_no_historical_global_protocol_dependency='REWARD_ROLLOUT_PROTOCOL_v1' not in source,cumulative_episode_metadata_uses_restored_actual_counter='training_episodes=model._episode_num' in source,ordinary_R4_10_episode_config_valid=validate(base))
for label,change in [('bad_scale',dict(std_initialization=.3)),('reinitialize_continuation_std',dict(start_episode=10,rollout_terminal_episode=20,std_initialization=.2)),('episode_cap',dict(episodes=100)),('mismatched_terminal_window',dict(rollout_terminal_episode=60)),('unsafe_job_path',dict(job_id='../escape'))]:
 cfg=dict(base,**change)
 try:validate(cfg);checks[label+'_rejected']=False
 except AssertionError:checks[label+'_rejected']=True
cfg=dict(base,std_initialization=.2);checks['declared_new_std_initialization_valid']=validate(cfg)
cfg=dict(base,aggregate_transitions=128,std_initialization=None);checks['declared_aggregate128_valid']=validate(cfg)
result=dict(time_utc=now(),checks=checks,pass_=all(checks.values()),new_physics=0,Adam=0,scope='Actual inactive worker pure config path; no policy initialization or training')
atomic(ROOT/'audit/FUTURE_WORKER_CONFIG_TESTS.json',result);print(json.dumps(result));assert result['pass_']
