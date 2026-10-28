"""Saved-data proof of initial R1/R4 fork parity and pre-first-Adam samples."""
from pathlib import Path
import os,sys,json,hashlib
R=Path(__file__).resolve().parents[1];os.environ['IHEAR_RESEARCH_ROOT']=str(R);sys.path[:0]=[str(R/'scripts'),str(R/'runtime')]
from research_common import atomic,read,sha,now
from stream_json import read_evidence
import numpy as np

def evidence(p):
 with read_evidence(p,encoding='utf8') as f:return json.load(f)
def build():
 result=[]
 for seed in [1495656323,1630784693]:
  paths={v:next(iter((R/'runtime/jobs').glob(f'REWARD_{v}_*_seed{seed}_to010')),None) for v in ['R1','R4']}
  if not all(paths.values()):continue
  cfg={v:read(paths[v]/'EFFECTIVE_CONFIG.json') for v in paths};aud={v:read(paths[v]/'RESUME_AUDIT.json') for v in paths}
  required=['EFFECTIVE_CONFIG.json','RESUME_AUDIT.json','PENDING_RESUME_AUDIT.json']
  if not all((paths[v]/name).exists() for v in paths for name in required):
   result.append(dict(seed=seed,pass_=False,checks=dict(complete_initial_fork_evidence=False),reason='Incomplete branch before full restore; original failure retained'));continue
  checks=dict(full_policy_critic_Adam_RNG_counters=aud['R1']['actual']==aud['R4']['actual'],both_restore_pass=aud['R1']['pass_'] and aud['R4']['pass_'],same_parent=cfg['R1']['parent_checkpoint']==cfg['R4']['parent_checkpoint'],empty_pending=all(read(paths[v]/'PENDING_RESUME_AUDIT.json')['restored_transitions']==0 for v in paths))
  stripped={v:{k:w for k,w in cfg[v].items() if k not in ['job_id','branch','reward']} for v in paths};checks['only_reward_and_identity_config_difference']=stripped['R1']==stripped['R4']
  source={v:read(R/'jobs'/cfg[v]['job_id']/'SOURCE_IDENTITY.json') for v in paths};checks['same_worker_reward_source_bundle']=source['R1']['bundle_sha256']==source['R4']['bundle_sha256']
  first=[];prior_update=False
  for index in range(1,11):
   if prior_update:break
   run={v:paths[v]/f'episode_{index:03d}' for v in paths}
   if not all((run[v]/'RESULT.json').exists() for v in paths):break
   rows={v:read(run[v]/'RESULT.json') for v in paths};trans={v:evidence(run[v]/'RESEARCH_TRANSITIONS.json') for v in paths}
   parity={k:len(trans['R1'])==len(trans['R4']) and all(np.allclose(a[k],b[k],rtol=0,atol=1e-7) for a,b in zip(trans['R1'],trans['R4'])) for k in ['obs','next_obs','raw_action','action','mean','std','logp','value']}
   parity['same_pre_update_policy']=rows['R1']['policy_before']==rows['R4']['policy_before']
   parity['same_runtime_outcome']=all(rows['R1'][k]==rows['R4'][k] for k in ['status','success','abort_reason','task_s','JF','JM','native_steps'])
   first.append(dict(episode=index,checks=parity,pass_=all(parity.values()),R1_reward=rows['R1']['training_reward'],R4_reward=rows['R4']['training_reward'],updates_R1=rows['R1']['gradient_updates'],updates_R4=rows['R4']['gradient_updates']))
   prior_update=rows['R1']['gradient_updates']>0 or rows['R4']['gradient_updates']>0
  checks['pre_first_update_samples_equal']=bool(first) and all(x['pass_'] for x in first)
  result.append(dict(seed=seed,checks=checks,pass_=all(checks.values()),initial_state=aud['R1']['actual'],source_bundle=source['R1']['bundle_sha256'],pre_first_update_episodes=first,scope='Initial full learner identity and recorded pre-update execution parity only; subsequent reward-driven trajectories may diverge; not a portable physical fork or formal B/H150 live matched'))
 atomic(R/'audit/R1_R4_FORK_PARITY_AUDIT.json',dict(time_utc=now(),source_sha256=sha(Path(__file__)),cases=result,pass_=len(result)==2 and all(x['pass_'] for x in result),new_native_steps=0,new_optimizer_updates=0))
 return dict(cases=len(result),pass_=len(result)==2 and all(x['pass_'] for x in result))
if __name__=='__main__':print(json.dumps(build()))
